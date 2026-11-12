# -*- coding: utf-8 -*-
# Python 3
# FilmPalast.one - xStream Site Plugin
# HTML-Struktur identisch zu topstreamfilm.live

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from resources.lib.wrappers.meinecloud import (
    resolveMeinecloudSerial, expandHosterList, buildHosterFromUrl,
    isPlatformUrl, platformImdbId, packSourceUrls, unpackSourceUrls
)
import html as _html
import re
import base64
import json
import datetime
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urljoin


def _normalise_stream_link(link):
    link = _html.unescape((link or "").strip()).replace("\\/", "/")
    if link.startswith("//"):
        link = "https:" + link
    return link if link.startswith("http") else ""


def _decode_data_link(value):
    """MeineCloud data-link: Klartext- oder Base64-URL normalisieren."""
    value = _html.unescape((value or "").strip())
    direct = _normalise_stream_link(value)
    if direct:
        return direct
    try:
        raw = value.replace(" ", "+")
        raw += "=" * (-len(raw) % 4)
        decoded = base64.b64decode(raw).decode("utf-8", "ignore").strip()
        return _normalise_stream_link(decoded)
    except Exception:
        return ""


def _episode_data_link(html, episode):
    """Bevorzugt data-episode-Zuordnung; Reihenfolge nur als Fallback."""
    try:
        ep = str(int(episode))
    except Exception:
        ep = str(episode or "1")
    patterns = [
        r'data-episode=["\']?' + re.escape(ep) + r'["\']?[^>]*data-link=["\']([^"\']+)',
        r'data-link=["\']([^"\']+)["\'][^>]*data-episode=["\']?' + re.escape(ep) + r'["\']?',
    ]
    for pattern in patterns:
        m = re.search(pattern, html or "", flags=re.I | re.S)
        if m:
            link = _decode_data_link(m.group(1))
            if link:
                return link
    links = re.findall(r'data-link=["\']([^"\']+)["\']', html or "", flags=re.I)
    links = [_decode_data_link(x) for x in links]
    links = [x for x in links if x and "youtube" not in x.lower()]
    if not links:
        return ""
    try:
        idx = max(0, int(episode) - 1)
    except Exception:
        idx = 0
    return links[idx] if idx < len(links) else links[0]

SITE_IDENTIFIER = 'filmpro'
SITE_NAME = 'FilmPro'
SITE_ICON = 'filmpro.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'filmpalast.one')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)

URL_MAIN   = 'https://' + DOMAIN
URL_NEW    = URL_MAIN + '/'
URL_MOVIES = URL_MAIN + '/filme'
URL_KINO   = URL_MAIN + '/kinofilme'
URL_SERIES = URL_MAIN + '/serien'
URL_SOON   = URL_MAIN + '/trends'
URL_SEARCH = URL_MAIN + '/suche?q=%s'

SCRAPER_SETTINGS = f'''
            <group id="filmpro" label="30729">
                <setting id="plugin_filmpro" type="boolean" label="30050" help="30411">
                    <level>0</level>
                    <default>True</default>
                    <control type="toggle"/>
                </setting>
                <setting id="global_search_filmpro" type="boolean" label="30052">
                    <level>0</level>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_filmpro">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_filmpro_checkDomain" type="boolean" label="30277">
                    <visible>false</visible>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_filmpro">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_filmpro">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_filmpro.domain" type="string" label="30278" help="">
                    <level>0</level>
                    <default>filmpalast.one</default>
                    <constraints>
                        <allowempty>true</allowempty>
                    </constraints>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_filmpro">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_filmpro">false</dependency>
                    </dependencies>
                    <control type="edit" format="string">
                        <heading>30278</heading>
                    </control>
                </setting>
                <setting id="plugin_filmpro_status" type="string" label="Dummy" help="">
                    <visible>false</visible>
                    <default>true</default>
                    <control type="toggle"/>
                </setting>
            </group>
'''


def load():
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()

    # --- Hauptmenü ---
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement('Im Kino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_NEW)
    cGui().addFolder(cGuiElement('Neu', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_SOON)
    cGui().addFolder(cGuiElement('Trends', SITE_IDENTIFIER, 'showEntries'), params)
    cGui().addFolder(cGuiElement('Filme', SITE_IDENTIFIER, 'showMovieMenu'), params)
    cGui().addFolder(cGuiElement('Serien', SITE_IDENTIFIER, 'showSeriesMenu'), params)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)
    cGui().setEndOfDirectory()


def showMovieMenu():
    """Untermenü: Filme"""
    params = ParameterHandler()

    params.setParam('sUrl', URL_MOVIES)
    cGui().addFolder(cGuiElement('Alle Filme', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement('Im Kino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_SOON)
    cGui().addFolder(cGuiElement('Trends', SITE_IDENTIFIER, 'showEntries'), params)
    cGui().addFolder(cGuiElement('Nach Genre', SITE_IDENTIFIER, 'showGenre'), params)
    cGui().addFolder(cGuiElement('Nach Jahr', SITE_IDENTIFIER, 'showYears'), params)
    cGui().addFolder(cGuiElement('Nach Land', SITE_IDENTIFIER, 'showCountry'), params)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)
    cGui().setEndOfDirectory()


def showSeriesMenu():
    """Untermenü: Serien"""
    params = ParameterHandler()

    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement('Alle Serien', SITE_IDENTIFIER, 'showEntries'), params)
    cGui().addFolder(cGuiElement('Nach Genre', SITE_IDENTIFIER, 'showSeriesGenre'), params)
    cGui().addFolder(cGuiElement('Nach Jahr', SITE_IDENTIFIER, 'showYears'), params)
    cGui().addFolder(cGuiElement('Nach Land', SITE_IDENTIFIER, 'showCountry'), params)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)
    cGui().setEndOfDirectory()


# Die Kategorien entsprechen den Navigationslinks der aktuellen FilmPalast-Seite.
_FILMPRO_GENRES = [
    ('Action', 'action'), ('Abenteuer', 'abenteuer'), ('Animation', 'animation'),
    ('Dokumentarfilm', 'dokumentarfilm'), ('Drama', 'drama'),
    ('Familie', 'familie'), ('Fantasy', 'fantasy'), ('Historie', 'historie'),
    ('Horror', 'horror'), ('Komödie', 'komoedie'), ('Krimi', 'krimi'),
    ('Liebesfilm', 'liebesfilm'), ('Mystery', 'mystery'),
    ('Science Fiction', 'science-fiction'), ('Thriller', 'thriller'),
    ('Western', 'western'), ('Reality', 'reality'), ('Kids', 'kids'),
    ('Sci-Fi & Fantasy', 'sci-fi-fantasy'), ('War & Politics', 'war-politics')
]


def _category_menu(items):
    gui = cGui()
    for name, path in items:
        params = ParameterHandler()
        params.setParam('sUrl', URL_MAIN + path)
        gui.addFolder(cGuiElement(name, SITE_IDENTIFIER, 'showEntries'), params)
    gui.setEndOfDirectory()


def showSeriesGenre():
    _category_menu([(name, '/genre/' + slug) for name, slug in _FILMPRO_GENRES
                    if slug in ('drama', 'fantasy', 'mystery', 'reality',
                                'sci-fi-fantasy', 'krimi', 'komoedie',
                                'thriller', 'kids', 'war-politics')])


def showGenre():
    _category_menu([(name, '/genre/' + slug) for name, slug in _FILMPRO_GENRES])


def showCountry():
    _category_menu([
        ('USA', '/land/usa'), ('Deutschland', '/land/germany'),
        ('Kanada', '/land/canada'), ('Italien', '/land/italy'),
        ('Frankreich', '/land/frankreich'), ('Spanien', '/land/spanien'),
        ('China', '/land/china'), ('Japan', '/land/japan'),
        ('Belgien', '/land/belgien'), ('Österreich', '/land/austria'),
        ('Indien', '/land/indien'), ('Südkorea', '/land/suedkorea'),
    ])


def showYears():
    current_year = datetime.datetime.now().year
    _category_menu([(str(year), '/jahr/%d' % year)
                    for year in range(current_year, 1989, -1)])


def _parse_filmpalast_cards(markup):
    """Liest die serverseitig gerenderten <a class="cv">-Filmkarten."""
    cards = []
    seen = set()
    for match in re.finditer(r'<a\b([^>]*\bclass=["\'][^"\']*\bcv\b[^"\']*["\'][^>]*)>(.*?)</a\s*>',
                             markup or '', flags=re.I | re.S):
        attrs, body = match.groups()
        link_match = re.search(r'\bhref=["\']([^"\']+)', attrs, re.I)
        if not link_match:
            continue
        link = urljoin(URL_MAIN + '/', _html.unescape(link_match.group(1)))
        if '/stream/' not in link or link in seen:
            continue
        seen.add(link)
        title_match = re.search(r'<div\b[^>]*class=["\'][^"\']*\bcv-t\b[^"\']*["\'][^>]*>(.*?)</div>', body, re.I | re.S)
        attr_title = re.search(r'\btitle=["\']([^"\']+)', attrs, re.I)
        title = (re.sub(r'<[^>]+>', '', title_match.group(1)) if title_match else
                 (attr_title.group(1) if attr_title else ''))
        title = _html.unescape(title).strip()
        if not title:
            continue
        img = re.search(r'<img\b[^>]*\bsrc=["\']([^"\']+)', body, re.I)
        thumb = urljoin(URL_MAIN + '/', _html.unescape(img.group(1))) if img else ''
        meta = re.search(r'<div\b[^>]*class=["\'][^"\']*\bcv-m\b[^"\']*["\'][^>]*>(.*?)</div>', body, re.I | re.S)
        meta_text = _html.unescape(re.sub(r'<[^>]+>', '', meta.group(1))).strip() if meta else ''
        year = re.search(r'\b(?:19|20)\d{2}\b', meta_text)
        series = bool(re.search(r'class=["\'][^"\']*\btag-serie\b', body, re.I) or
                      re.search(r'\bStaffel(?:n)?\b', meta_text, re.I))
        cards.append((link, thumb, title, year.group(0) if year else '', series))
    return cards


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText=False):
    gui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl') or URL_NEW
    entryUrl = urljoin(URL_MAIN + '/', entryUrl)
    try:
        request = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
        request.cacheTime = 60 * 30
        markup = request.request() or ''
    except Exception as exc:
        logger.info('FilmPro: Fehler beim Abruf %s: %s' % (entryUrl, exc))
        if not sGui:
            gui.showInfo()
        return

    cards = _parse_filmpalast_cards(markup)
    if sSearchText:
        query = re.sub(r'\s*\(\d{4}\)\s*$', '', str(sSearchText)).strip().casefold()
        if query:
            cards = [card for card in cards if query in card[2].casefold()]
    if not cards:
        logger.info('FilmPro: Keine Filmkarten auf %s erkannt' % entryUrl)
        if not sGui:
            gui.showInfo()
            gui.setEndOfDirectory()
        return

    total = len(cards)
    for link, thumbnail, name, year, is_series in cards:
        item = cGuiElement(name + (' - (%s)' % year if year else ''),
                           SITE_IDENTIFIER, 'showSeasons' if is_series else 'showHosters')
        item.setMediaType('tvshow' if is_series else 'movie')
        if thumbnail:
            item.setThumbnail(thumbnail)
            item.setFanart(thumbnail)
        if year:
            item.setYear(year)
        item_params = ParameterHandler()
        item_params.setParam('entryUrl', link)
        item_params.setParam('sName', name)
        item_params.setParam('sThumbnail', thumbnail)
        item_params.setParam('sDesc', '')
        gui.addFolder(item, item_params, is_series, total)

    if not sGui and not sSearchText and not sSearchPageText:
        # Next.js-Seiten verwenden keine alte wp-pagenavi-Struktur.
        next_link = re.search(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>\s*(?:Weiter|Nächste|Next|»|›)\s*</a>',
                              markup, re.I)
        if next_link:
            next_url = urljoin(entryUrl, _html.unescape(next_link.group(1)))
            if next_url != entryUrl:
                next_params = ParameterHandler()
                next_params.setParam('sUrl', next_url)
                gui.addNextPage(SITE_IDENTIFIER, 'showEntries', next_params)
        gui.setView('tvshows' if '/serien' in entryUrl else 'movies')
        gui.setEndOfDirectory()


def _filmpro_series_data(entryUrl):
    """Serienfolgen ueber den vorhandenen, funktionierenden Meinecloud-Wrapper."""
    sHtml = cRequestHandler(entryUrl).request() or ''
    imdb = platformImdbId(sHtml)
    if not imdb:
        logger.info('FilmPro: keine IMDb-ID fuer Serie %s' % entryUrl)
        return []
    return resolveMeinecloudSerial(imdb, referer=entryUrl, siteHtml=sHtml)


def showSeasons():
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    episodes = _filmpro_series_data(entryUrl)
    seasons = sorted(set(ep['season'] for ep in episodes))
    if not seasons:
        cGui().showInfo()
        return
    for season in seasons:
        item = cGuiElement('Staffel %d' % season, SITE_IDENTIFIER, 'showEpisodes')
        item.setMediaType('season')
        item.setSeason(season)
        thumb = params.getValue('sThumbnail')
        if thumb:
            item.setThumbnail(thumb)
        desc = params.getValue('sDesc')
        if desc:
            item.setDescription(desc)
        item_params = ParameterHandler()
        item_params.setParam('entryUrl', entryUrl)
        item_params.setParam('sThumbnail', thumb)
        item_params.setParam('sDesc', desc)
        item_params.setParam('season', str(season))
        cGui().addFolder(item, item_params, True, len(seasons))
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    season = str(params.getValue('season'))
    episodes = [ep for ep in _filmpro_series_data(entryUrl) if str(ep['season']) == season]
    if not episodes:
        cGui().showInfo()
        return
    for ep in episodes:
        item = cGuiElement('E%d - %s' % (ep['episode'], ep.get('title', 'Episode')),
                           SITE_IDENTIFIER, 'showEpisodeHosters')
        item.setMediaType('episode')
        item.setSeason(ep['season'])
        item.setEpisode(ep['episode'])
        thumb = params.getValue('sThumbnail')
        if thumb:
            item.setThumbnail(thumb)
        desc = params.getValue('sDesc')
        if desc:
            item.setDescription(desc)
        ep_params = ParameterHandler()
        ep_params.setParam('entryUrl', entryUrl)
        ep_params.setParam('meinecloud_url', packSourceUrls(ep.get('urls', [])))
        cGui().addFolder(item, ep_params, False, len(episodes))
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showEpisodeHosters():
    params = ParameterHandler()
    urls = unpackSourceUrls(params.getValue('meinecloud_url'))
    hosters = []
    for url in urls:
        item = buildHosterFromUrl(url)
        if item:
            hosters.append(item)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def showHosters():
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sHtml = cRequestHandler(entryUrl, caching=False).request() or ''
    raw = []
    for tag in re.findall(r'<iframe\b[^>]*>', sHtml, flags=re.I | re.S):
        m = re.search(r'\bsrc\s*=\s*["\']([^"\']+)', tag, flags=re.I)
        if m:
            link = _normalise_stream_link(m.group(1))
            if link:
                raw.append(link)
    # Auch direkt im HTML eingebettete Plattform-Links beruecksichtigen.
    for link in re.findall(r'https?://[^"\'\s<>]+(?:meinecloud|devideosrc)[^"\'\s<>]*', sHtml, re.I):
        if isPlatformUrl(link):
            raw.append(link)
    expanded = expandHosterList(raw, referer=entryUrl)
    hosters = []
    seen = set()
    for url in expanded:
        item = buildHosterFromUrl(url)
        if item and item['link'] not in seen:
            seen.add(item['link'])
            hosters.append(item)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    # Den dekodierten Embed-Link unverändert an ResolveURL weiterreichen.
    # Die bereits angepasste dropload.py übernimmt dr0pstream/dropload.
    return [{'streamUrl': sUrl, 'resolved': False}]

def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_SEARCH % cParser.quotePlus(sSearchText), oGui, sSearchText)


def showSearchPage():
    params          = ParameterHandler()
    sNextPage       = params.getValue('sNextPage')
    sPageLast       = params.getValue('sPageLast')
    sHeading        = cConfig().getLocalizedString(30282) + str(sPageLast)
    sSearchPageText = cGui().showKeyBoard(sHeading=sHeading)
    if not sSearchPageText: return
    sNextSearchPage = sNextPage.split('page/')[0].strip() + 'page/' + sSearchPageText + '/'
    showEntries(sNextSearchPage)
    cGui().setEndOfDirectory()
