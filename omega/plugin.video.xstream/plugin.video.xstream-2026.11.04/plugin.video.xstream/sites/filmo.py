# -*- coding: utf-8 -*-
# Filmo.to - xStream_mod Kodi 21 Python 3 site plugin
import html
from concurrent.futures import ThreadPoolExecutor
import json
import re
import time
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlparse
from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.gui.gui import cGui
from resources.lib.config import cConfig

SITE_IDENTIFIER = 'filmo'
SITE_NAME = 'Filmo'
SITE_ICON = 'filmo.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'filmo.to')
URL_MAIN = 'https://' + DOMAIN.strip('/').replace('https://','').replace('http://','')
URL_MOVIES = URL_MAIN + '/movies'
URL_POPULAR = URL_MAIN + '/popular'
URL_GENRES = URL_MAIN + '/genres'

if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False

def _clean_title(value):
    import unicodedata
    value = unicodedata.normalize('NFKD', str(value or '').lower())
    return re.sub(r'[^a-z0-9]', '', value.encode('ascii', 'ignore').decode('ascii'))


def _request(url, caching=True):
    try:
        return cRequestHandler(url, caching=caching).request() or ''
    except Exception as exc:
        logger.error('Filmo request failed: %s' % exc)
        return ''


def _menu(title, fn, url=None):
    params = ParameterHandler()
    if url:
        params.setParam('sUrl', url)
    cGui().addFolder(cGuiElement(title, SITE_IDENTIFIER, fn), params)


def load():
    _menu('Top Kinofilme', 'showEntries', URL_MAIN + '/collections/top-kinofilme')
    _menu('Neu bei Filmo, Netflix & Co.', 'showEntries', URL_MAIN + '/collections/neu-bei-filmo-disney-co')
    _menu('Neue Filme', 'showEntries', URL_MOVIES)
    _menu('Beliebte Filme', 'showEntries', URL_POPULAR)
    _menu('Alle Filme', 'showEntries', URL_MOVIES)
    _menu('Filmsammlungen', 'showCollections', URL_MAIN + '/collections')
    _menu('Genres', 'showGenres', URL_GENRES)
    _menu('Land', 'showCountries', URL_MOVIES)
    _menu('Erscheinungsjahr', 'showYears', URL_MOVIES)
    _menu('Suche', 'showSearch')
    cGui().setEndOfDirectory()


def showCollections():
    """Show the individual collections, not the posters within them."""
    page = _request(URL_MAIN + '/collections')
    pattern = (r'<a\b(?=[^>]*\bclass=["\'][^"\']*collection-index-card)'
               r'(?=[^>]*\bhref=["\']([^"\']+))[^^>]*>(.*?)</a>')
    seen = set()
    for url, block in re.findall(pattern, page, re.I | re.S):
        title = re.search(r'collection-index-card__title[^>]*>(.*?)</', block, re.I | re.S)
        if not title:
            continue
        url = urljoin(URL_MAIN, html.unescape(url))
        if url in seen:
            continue
        seen.add(url)
        label = html.unescape(re.sub(r'<[^>]+>', '', title.group(1))).strip()
        if label:
            _menu(label, 'showEntries', url)
    if not seen:
        cGui().showInfo()
    cGui().setEndOfDirectory()


def _movie_year(movie_url):
    """Movie cards contain no year; read release metadata from the detail page."""
    body = _request(movie_url)
    if not body:
        return ''
    patterns = (
        r'<meta[^>]+(?:itemprop|name)=["\'](?:datePublished|release_date|releaseDate)["\'][^>]+content=["\']((?:19|20)\d{2})',
        r'["\'](?:datePublished|release_date|releaseDate|release_year|releaseYear)["\']\s*:\s*["\']?((?:19|20)\d{2})',
        r'(?:Erscheinungsjahr|Erscheinungsdatum|Release Year|Release Date)[^<]{0,120}?(?:<[^>]+>\s*){0,3}((?:19|20)\d{2})',
        r'<time[^>]+datetime=["\']((?:19|20)\d{2})',
    )
    for pattern in patterns:
        match = re.search(pattern, body, re.I | re.S)
        if match:
            return match.group(1)
    return ''


def showGenres():
    page = _request(URL_MOVIES)
    matches = re.findall(r'<a[^>]+href=["\']([^"\']*/genres/[^"\']+)["\'][^>]*>\s*<span[^>]*>([^<]+)</span>', page, re.I | re.S)
    seen = set()
    for url, label in matches:
        url = urljoin(URL_MAIN, html.unescape(url))
        if url in seen: continue
        seen.add(url)
        _menu(html.unescape(label).strip(), 'showEntries', url)
    cGui().setEndOfDirectory()


def _select_options(field):
    page = _request(URL_MOVIES)
    match = re.search(r'<select[^>]*name=["\']%s["\'][^>]*>(.*?)</select>' % field, page, re.I | re.S)
    if not match: return []
    return [(html.unescape(v), html.unescape(re.sub('<[^>]+>', '', label)).strip()) for v, label in re.findall(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>', match.group(1), re.I | re.S) if v]


def _filter_menu(field):
    for value, label in _select_options(field):
        _menu(label, 'showEntries', URL_MOVIES + '?' + urlencode({field:value}))
    cGui().setEndOfDirectory()


def showCountries():
    _filter_menu('country')


def showYears():
    _filter_menu('year')


def _cards(page):
    # Listing HTML: <a href="/movies/slug" class="movie-poster-grid-card"> ... <img ...> ... <div class="...__title">Name</div>
    pattern = r'<a\b(?=[^>]*\bclass=["\'][^"\']*movie-poster-grid-card)[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
    # Some templates put href before class, so use lookaheads for both.
    pattern = r'<a\b(?=[^>]*\bclass=["\'][^"\']*movie-poster-grid-card)(?=[^>]*\bhref=["\']([^"\']+))[^^>]*>(.*?)</a>'
    for url, block in re.findall(pattern, page, re.I | re.S):
        title = re.search(r'movie-poster-grid-card__title[^>]*>(.*?)</', block, re.I | re.S)
        img = re.search(r'<img[^>]+src=["\']([^"\']+)', block, re.I | re.S)
        if not title: continue
        yield urljoin(URL_MAIN, html.unescape(url)), html.unescape(re.sub('<[^>]+>', '', title.group(1))).strip(), urljoin(URL_MAIN, html.unescape(img.group(1))) if img else ''


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    gui = sGui if sGui else cGui()
    params = ParameterHandler()
    url = entryUrl or params.getValue('sUrl') or URL_MOVIES
    page = _request(url)
    items = list(_cards(page))
    if not items:
        if not sGui: gui.showInfo()
        return
    # Fetch detail-page release years concurrently to keep list loading responsive.
    # Missing years are never guessed and never appended twice.
    with ThreadPoolExecutor(max_workers=8) as pool:
        years = list(pool.map(_movie_year, [movie_url for movie_url, _, _ in items]))
    for (movie_url, title, poster), year in zip(items, years):
        if sSearchText and sSearchText.lower() not in title.lower():
            continue
        title = re.sub(r'\s+-\s+\((?:19|20)\d{2}\)$', '', title).strip()
        display_title = '%s - (%s)' % (title, year) if year else title
        item = cGuiElement(display_title, SITE_IDENTIFIER, 'showHosters')
        item.setMediaType('movie')
        if year:
            item.setYear(int(year))
        if poster:
            item.setThumbnail(poster)
        item_params = ParameterHandler()
        item_params.setParam('entryUrl', movie_url)
        gui.addFolder(item, item_params, False, len(items))
    if not sGui:
        match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']next["\']', page, re.I)
        if not match:
            match = re.search(r'<a[^>]+rel=["\']next["\'][^>]+href=["\']([^"\']+)', page, re.I)
        if match:
            next_params = ParameterHandler()
            next_params.setParam('sUrl', urljoin(url, html.unescape(match.group(1))))
            gui.addNextPage(SITE_IDENTIFIER, 'showEntries', next_params)
        gui.setView('movies')
        gui.setEndOfDirectory()


def showSearch():
    text = cGui().showKeyBoard(sHeading='Filmo Suche')
    if text:
        showEntries(URL_MOVIES + '?search=' + quote_plus(text), sSearchText=text)
    else:
        cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    """xStream global/TMDb provider-search entry point (no keyboard or GUI close)."""
    query = str(sSearchText or '').strip()
    if not query:
        return
    # Search provider listings; xStream applies mode-specific result filtering.
    showEntries(URL_MOVIES + '?search=' + quote_plus(query),
                sGui=oGui, sSearchText=query)


class source:
    MAX_DETAIL_PROBES = 8
    MAX_SEARCH_LINKS = 12
    MAX_SOURCES_PER_SCRAPER = 10
    MAX_RESOLVE_PROBES = 12
    MAX_PROCESS_SECONDS = 10

    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = DOMAIN
        self.domain = str(self.domain or 'filmo.to').replace('https://', '').replace('http://', '').strip().strip('/')
        self.base_link = 'https://' + self.domain
        self.sources = []
        self._seen = set()
        self._session = None

    def _log(self, message, level=0):
        # Zusatzdiagnose im stabilen Build deaktiviert.
        pass

    def _fetch(self, url, caching=True, timeout=6):
        try:
            req = cRequestHandler(url, caching=caching)
            req.requestTimeout = timeout
            req.cacheTime = 60 * 60 * 3
            req.addHeaderEntry('Referer', self.base_link + '/')
            req.addHeaderEntry('Accept', 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8')
            req.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.7')
            return req.request() or ''
        except Exception as exc:
            self._log('Request-Fehler %s: %s' % (url, str(exc)[:180]), 0)
            return ''

    @staticmethod
    def _slug(value):
        raw = html.unescape(str(value or '')).strip().lower()
        # Common German transliterations used by slug generators.
        raw = raw.replace('ä', 'a').replace('ö', 'o').replace('ü', 'u').replace('ß', 'ss')
        raw = raw.replace('&', ' und ')
        raw = re.sub(r"['’`]", '', raw)
        raw = re.sub(r'[^a-z0-9]+', '-', raw).strip('-')
        return raw

    @staticmethod
    def _title_from_page(body):
        if not body:
            return ''
        patterns = (
            r'<h1[^>]*>(.*?)</h1>',
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
            r'<title[^>]*>(.*?)</title>',
        )
        for pattern in patterns:
            match = re.search(pattern, body, re.I | re.S)
            if not match:
                continue
            value = re.sub(r'<[^>]+>', ' ', match.group(1))
            value = html.unescape(re.sub(r'\s+', ' ', value)).strip()
            value = re.sub(r'\s+(?:jetzt\s+)?kostenlos\s+streamen.*$', '', value, flags=re.I)
            value = re.sub(r'\s*[–|-]\s*Filmo\s*$', '', value, flags=re.I)
            if value:
                return value
        return ''

    @staticmethod
    def _years_from_page(body):
        if not body:
            return set()
        years = set()
        # Prefer explicit release/date metadata over arbitrary years in plot text.
        for pattern in (
            r'Erscheinungsdatum.{0,220}?\b((?:19|20)\d{2})\b',
            r'"datePublished"\s*:\s*"((?:19|20)\d{2})',
            r'"release_date"\s*:\s*"((?:19|20)\d{2})',
            r'\b((?:19|20)\d{2})\b[^<]{0,80}(?:FSK|Ab\s+\d+|\d+\s*(?:h|min))',
        ):
            for match in re.findall(pattern, body, re.I | re.S):
                years.add(str(match))
        return years

    def _valid_detail(self, body, titles, year):
        page_title = self._title_from_page(body)
        page_clean = _clean_title(page_title)
        wanted = {_clean_title(t) for t in titles if t}
        wanted.discard('')
        if not page_clean or page_clean not in wanted:
            return False, page_title, self._years_from_page(body)

        years = self._years_from_page(body)
        target = str(year or '')
        if target and target not in years:
            return False, page_title, years
        return True, page_title, years

    @staticmethod
    def _quality(context):
        value = html.unescape(str(context or '')).upper()
        if '2160' in value or re.search(r'\b4K\b', value):
            return '4K'
        if '1440' in value:
            return '1440p'
        if '1080' in value:
            return '1080p'
        if '720' in value:
            return '720p'
        if 'WEB' in value or 'BLURAY' in value or 'HD' in value:
            return 'HD'
        if 'CAM' in value or 'TELESYNC' in value or re.search(r'\bTS\b', value):
            return 'CAM'
        return 'SD'

    def _extract_movie_links(self, body):
        links = []
        seen = set()
        if not body:
            return links
        for href in re.findall(r'(?:href|data-href)\s*=\s*["\']([^"\']+)["\']', body, re.I):
            href = html.unescape(href).replace('\\/', '/')
            if '/movies/' not in href:
                continue
            full = urljoin(self.base_link + '/', href)
            if full in seen:
                continue
            seen.add(full)
            links.append(full)
            if len(links) >= self.MAX_SEARCH_LINKS:
                break
        return links

    def _candidate_detail_urls(self, titles):
        result = []
        seen = set()
        for title in titles:
            slug = self._slug(title)
            if not slug:
                continue
            # Exact slug is overwhelmingly the common Filmo route. Small numeric
            # suffix range handles duplicate slugs such as /whistle-1.
            for suffix in ('', '-1', '-2'):
                url = self.base_link + '/movies/' + slug + suffix
                if url not in seen:
                    seen.add(url)
                    result.append(url)
                    if len(result) >= self.MAX_DETAIL_PROBES:
                        return result
        return result

    def _search_fallback(self, titles):
        urls = []
        seen = set()
        for title in titles[:2]:
            q = quote_plus(str(title))
            # Filmo's public search UI has changed query naming before. Probe a
            # few harmless GET variants and only accept /movies/ links later.
            for search_url in (
                self.base_link + '/search?q=' + q,
                self.base_link + '/search?query=' + q,
                self.base_link + '/search?search=' + q,
                self.base_link + '/movies?search=' + q,
            ):
                body = self._fetch(search_url)
                for movie_url in self._extract_movie_links(body):
                    if movie_url in seen:
                        continue
                    seen.add(movie_url)
                    urls.append(movie_url)
                    if len(urls) >= self.MAX_SEARCH_LINKS:
                        return urls
        return urls

    @staticmethod
    def _clean(value):
        value = html.unescape(str(value or ''))
        value = re.sub(r'<[^>]+>', ' ', value)
        return re.sub(r'\s+', ' ', value).strip()

    @staticmethod
    def _attr_raw(fragment, name):
        match = re.search(r'\b%s=["\']([^"\']+)["\']' % re.escape(name), fragment or '', re.I | re.S)
        return html.unescape(match.group(1)).strip() if match else ''

    def _csrf(self, body):
        match = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']*)', body or '', re.I | re.S)
        return html.unescape(match.group(1)).strip() if match else ''

    def _mint_endpoint(self, body):
        match = re.search(r'"openMint"\s*:\s*"([^"]+)"', body or '', re.I)
        if not match:
            return self.base_link + '/n'
        return html.unescape(match.group(1)).replace('\\/', '/').replace('\\u0026', '&')

    def _provider_chips(self, body):
        """Read German Filmo provider buttons including the full badge block."""
        chips = []
        seen = set()
        page = body or ''
        starts = list(re.finditer(r'(?is)<[^>]+data-provider-chip\b[^>]*>', page))
        for idx, match in enumerate(starts):
            opening = match.group(0)
            payload = self._attr_raw(opening, 'data-p')
            if not payload or payload in seen:
                continue
            seen.add(payload)

            # A provider chip contains nested spans.  Matching only up to the first
            # closing tag cuts off the BluRay/720p badges, so use the text up to the
            # next chip (bounded to keep parsing cheap).
            next_start = starts[idx + 1].start() if idx + 1 < len(starts) else min(len(page), match.start() + 5000)
            fragment = page[match.start():next_start]
            if len(fragment) > 5000:
                fragment = fragment[:5000]

            before = page[max(0, match.start() - 2200):match.start()]
            lang_match = list(re.finditer(r'provider-row__lang[^>]*>(.*?)</', before, re.I | re.S))
            language_text = self._clean(lang_match[-1].group(1)) if lang_match else ''
            if language_text and not ('deutsch' in language_text.lower() or language_text.lower() in ('de', 'ger', 'german')):
                continue

            label = self._attr_raw(opening, 'aria-label')
            if not label:
                name = re.search(r'provider-chip__name[^>]*>(.*?)</', fragment, re.I | re.S)
                label = self._clean(name.group(1)) if name else ''

            metadata = [self._clean(x) for x in re.findall(r'provider-chip__metadata-tag[^>]*>(.*?)</', fragment, re.I | re.S)]
            quality_hint = self._clean(re.sub(r'<[^>]+>', ' ', fragment))
            link_id = self._attr_raw(opening, 'data-movie-link-id')
            quality = self._quality(' '.join(metadata + [quality_hint]))
            self._log('Chip id=%s hoster=%s quality=%s' % (link_id or '-', label or '-', quality))
            chips.append({'p': payload, 'id': link_id, 'hoster': label,
                          'metadata': metadata, 'quality_hint': quality_hint})
        return chips

    def _prime_browser_page(self, page_url):
        """Load the movie page once and keep its cookies/CSRF/data-p values together."""
        try:
            import requests
            if self._session is None:
                self._session = requests.Session()
            ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:155.0) Gecko/20100101 Firefox/155.0'
            headers = {
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'de,en-US;q=0.9,en;q=0.8',
                'Referer': self.base_link + '/',
                'Connection': 'close',
            }
            response = self._session.get(page_url, headers=headers, timeout=6, allow_redirects=True)
            if response.status_code != 200:
                self._log('Provider-Seite HTTP=%s' % response.status_code, 0)
                return '', '', []
            fresh_body = response.text or ''
            endpoint = self._mint_endpoint(fresh_body)
            csrf = self._csrf(fresh_body)
            chips = self._provider_chips(fresh_body)
            return endpoint, csrf, chips
        except Exception as exc:
            self._log('Provider-Seite Fehler: %s' % str(exc)[:180], 0)
            return '', '', []

    def _mint(self, endpoint, payload, csrf, referer, chip_id='', chip_no=0):
        """Mint exactly this chip's data-p, then open the returned /n/<token>."""
        try:
            import requests
            if self._session is None:
                self._session = requests.Session()

            ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:155.0) Gecko/20100101 Firefox/155.0'
            headers = {
                'User-Agent': ua,
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'de,en-US;q=0.9,en;q=0.8',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_link,
                'Referer': referer,
                'Connection': 'close',
            }
            if csrf:
                headers['X-CSRF-TOKEN'] = csrf

            response = self._session.post(
                endpoint,
                json={'p': str(payload or '')},
                headers=headers,
                timeout=6,
                allow_redirects=False,
            )
            tag = '#%s id=%s' % (chip_no or '-', chip_id or '-')
            self._log('Mint Browser-Flow %s HTTP=%s' % (tag, response.status_code))

            location = str(response.headers.get('Location') or '').strip()
            if location:
                location = urljoin(endpoint, location)
                host = (urlparse(location).hostname or '').lower()
                own = (self.domain.lower()[4:] if self.domain.lower().startswith('www.') else self.domain.lower())
                if host and host != own and not host.endswith('.' + own):
                    return location

            if response.status_code not in (200, 201, 301, 302):
                return ''
            try:
                data = response.json() or {}
            except Exception:
                data = {}

            for key in ('url', 'href', 'location', 'redirect'):
                target = str(data.get(key) or '').strip()
                if not target:
                    continue
                target = urljoin(endpoint, target)
                host = (urlparse(target).hostname or '').lower()
                own = (self.domain.lower()[4:] if self.domain.lower().startswith('www.') else self.domain.lower())
                if host and host != own and not host.endswith('.' + own):
                    return target

            token = str(data.get('x') or data.get('token') or '').strip()
            if not token:
                self._log('Mint ohne URL/Token %s keys=%s' %
                          (tag, ','.join(sorted(data.keys()))[:120]), 0)
                return ''

            token_url = endpoint.rstrip('/') + '/' + quote_plus(token)
            jump_headers = {
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': headers['Accept-Language'],
                'Referer': referer,
                'Connection': 'close',
            }
            own = (self.domain.lower()[4:] if self.domain.lower().startswith('www.') else self.domain.lower())
            current = token_url
            jump = None
            for hop in range(5):
                jump = self._session.get(current, headers=jump_headers, timeout=6, allow_redirects=False)
                location = str(jump.headers.get('Location') or '').strip()
                self._log('Mint Token-GET %s hop=%s HTTP=%s redirect=%s' %
                          (tag, hop + 1, jump.status_code, 'ja' if location else 'nein'))
                if not location:
                    break
                target = urljoin(current, location)
                target_host = (urlparse(target).hostname or '').lower()
                if target.startswith(('http://', 'https://')) and target_host != own and not target_host.endswith('.' + own):
                    return target
                current = target

            if jump is None:
                return ''

            final = str(jump.url or current or '').strip()
            host = (urlparse(final).hostname or '').lower()
            if final.startswith(('http://', 'https://')) and host != own and not host.endswith('.' + own):
                return final

            text = jump.text or ''
            for pattern in (
                r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)',
                r'(?:window\.)?location\.(?:replace|assign)\(\s*["\']([^"\']+)',
                r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=\s*["\']?([^"\'>\s]+)',
                r'<iframe[^>]+src=["\']([^"\']+)',
            ):
                match = re.search(pattern, text, re.I | re.S)
                if not match:
                    continue
                target = urljoin(final, html.unescape(match.group(1)).strip())
                target_host = (urlparse(target).hostname or '').lower()
                if target.startswith(('http://', 'https://')) and target_host != own and not target_host.endswith('.' + own):
                    return target

            # The Filmo mint token is one-shot.  Do not request token_url a second
            # time: Byse returns HTTP 200 on the first GET and a repeat is already
            # invalid (404).  Inspect the body of that *first* response instead.
            if jump.status_code == 200:
                first_text = jump.text or ''
                # Besides the usual navigation constructs, accept explicit absolute
                # external URLs embedded in attributes / JSON-ish page data.
                candidates = []
                for pattern in (
                    r"window\.location(?:\.href)?\s*=\s*[\"\']([^\"\']+)",
                    r"(?:window\.)?location\.(?:replace|assign)\(\s*[\"\']([^\"\']+)",
                    r"<meta[^>]+http-equiv=[\"\']refresh[\"\'][^>]+(?:content=[\"\'][^\"\']*?url=|url=)\s*[\"\']?([^\"\'>\s]+)",
                    r"<iframe[^>]+src=[\"\']([^\"\']+)",
                    r"<a\b[^>]*\bhref=[\"\']([^\"\']+)",
                    r"[\"\'](?:url|href|location|redirect|src)[\"\']\s*:\s*[\"\']([^\"\']+)",
                    r"(https?://[^\"\'<>\s\\]+)",
                ):
                    candidates.extend(re.findall(pattern, first_text, re.I | re.S))
                for raw_target in candidates:
                    target = urljoin(final or token_url, html.unescape(str(raw_target)).strip().replace('\\/', '/'))
                    target_host = (urlparse(target).hostname or '').lower()
                    if (target.startswith(('http://', 'https://')) and target_host and
                            target_host != own and not target_host.endswith('.' + own)):
                        self._log('Mint 200-Body %s extern=%s' % (tag, target_host))
                        return target
                self._log('Mint 200-Body %s ohne externes Ziel len=%s' %
                          (tag, len(first_text)), 0)
        except Exception as exc:
            self._log('Mint-Fehler #%s id=%s: %s' %
                      (chip_no or '-', chip_id or '-', str(exc)[:180]), 0)
        return ''

    def _extract_streams(self, body, year, page_url):
        """List Filmo chips cheaply; mint the selected chip only at playback.

        This follows xShip's source/resolve split: source discovery never spends a
        mint token.  The playback resolver reloads the detail page in one fresh
        session so CSRF, cookies and data-p belong together.
        """
        chips = self._provider_chips(body)
        self._log('Provider-Chips: %d (Deferred-Mint)' % len(chips))

        for chip_no, chip in enumerate(chips, 1):
            if len(self.sources) >= self.MAX_SOURCES_PER_SCRAPER:
                break

            hoster = str(chip.get('hoster') or SITE_NAME).strip() or SITE_NAME
            quality_context = ' '.join((chip.get('metadata') or []) + [chip.get('quality_hint') or ''])
            quality = self._quality(quality_context)

            # data-p can be session-bound, therefore do not persist the payload
            # itself.  Persist the chip position and reload a fresh copy in resolve().
            deferred = 'xship-filmo://mint?' + urlencode({
                'page': page_url,
                'chip': chip_no - 1,
                'id': chip.get('id') or '',
                'hoster': hoster,
            })
            self.sources.append({
                'source': hoster,
                'quality': quality,
                'language': 'de',
                'url': deferred,
                'direct': False,
                'prioHoster': 100,
                'info': str(year or ''),
            })
            self._log('Deferred-Quelle #%d id=%s: %s [%s]' %
                      (chip_no, chip.get('id') or '-', hoster, quality))



def showHosters():
    params = ParameterHandler()
    url = params.getValue('entryUrl')
    if not url: return []
    resolver = source()
    page = resolver._fetch(url, caching=False)
    chips = resolver._provider_chips(page)
    result = []
    for index, chip in enumerate(chips[:10]):
        name = str(chip.get('hoster') or 'Filmo').strip()
        if cConfig().isBlockedHoster(name.lower())[0]: continue
        quality = resolver._quality(' '.join((chip.get('metadata') or []) + [chip.get('quality_hint') or '']))
        deferred = 'xstream-filmo://mint?' + urlencode({'page':url, 'chip':index, 'id':chip.get('id') or '', 'hoster':name})
        result.append({'link':deferred, 'name':name.lower(), 'displayedName':'%s [I][%s][/I]' % (name, quality), 'quality':quality})
    if result: result.append('getHosterUrl')
    return result


def getHosterUrl(sUrl=False):
    if not sUrl: return []
    if not sUrl.startswith('xstream-filmo://mint?'):
        return [{'streamUrl':sUrl, 'resolved':False}]
    try:
        query = parse_qs(urlparse(sUrl).query)
        page_url = (query.get('page') or [''])[0]
        index = int((query.get('chip') or ['0'])[0])
        wanted_id = (query.get('id') or [''])[0]
        wanted_name = (query.get('hoster') or [''])[0]
        if not page_url.startswith(URL_MAIN + '/movies/'): return []
        resolver = source()
        endpoint, csrf, chips = resolver._prime_browser_page(page_url)
        chip = chips[index] if 0 <= index < len(chips) else None
        if chip is None or (wanted_name and chip.get('hoster','').lower() != wanted_name.lower()):
            chip = next((c for c in chips if (not wanted_id or c.get('id') == wanted_id) and (not wanted_name or c.get('hoster','').lower() == wanted_name.lower())), None)
        if not chip: return []
        target = resolver._mint(endpoint, chip.get('p'), csrf, page_url, chip_id=chip.get('id'), chip_no=index+1)
        return [{'streamUrl':target, 'resolved':False}] if target else []
    except Exception as exc:
        logger.error('Filmo hoster resolution failed: %s' % exc)
        return []
