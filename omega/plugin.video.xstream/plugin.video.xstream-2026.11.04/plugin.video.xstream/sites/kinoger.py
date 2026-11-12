# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showGenre:     48 Stunden
# showEntries:    6 Stunden
# showSeasons:    6 Stunden
# showEpisodes:   4 Stunden

import re
import html
from urllib.parse import urlencode
import xbmcgui

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui


SITE_IDENTIFIER = 'kinoger'
SITE_NAME = 'KinoGer'
BUILD_ID = 'kinoger-direct-meinecloud-2026-07-10-v2'
SITE_ICON = 'kinoger.png'
logger.info('KinoGer build loaded: %s' % BUILD_ID)

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain') or 'kinoger.fun'
if DOMAIN in ('kinoger.com', 'kinoger.to'):
    DOMAIN = 'kinoger.fun'  # Aktuelle funktionierende Domain
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')  # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)  # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN
URL_KINO = URL_MAIN + '/aktuelle-kinofilme-im-kino/'
URL_MOVIES = URL_MAIN + '/kinofilme-online/'
URL_SERIES = URL_MAIN + '/serienstream-deutsch/'


MEINECLOUD_MOVIE = 'https://meinecloud.click/movie/%s'


def _normalize_urls(text):
    """Extract external http(s) URLs from HTML/JSON/JS responses."""
    if not text:
        return []
    text = html.unescape(text).replace('\\/', '/').replace('\\u0026', '&')
    urls = re.findall(r"https?://[^\s\"'<>]+", text, re.I)
    cleaned = []
    seen = set()
    blocked_parts = (
        'meinecloud.click/static/', 'meinecloud.click/assets/',
        'google.com/', 'gstatic.com/', 'cloudflare.com/',
        'schema.org/', 'w3.org/', 'jquery', '.css', '.js',
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico'
    )
    for url in urls:
        url = url.rstrip(');,]}>\\')
        low = url.lower()
        if any(part in low for part in blocked_parts):
            continue
        if 'meinecloud.click/movie/' in low:
            continue
        if url not in seen:
            seen.add(url)
            cleaned.append(url)
    return cleaned


def _resolve_meinecloud_movie(imdb_id, referer=''):
    """Fetch Meinecloud movie page and return embedded hoster URLs."""
    if not imdb_id:
        return []
    try:
        req = cRequestHandler(MEINECLOUD_MOVIE % imdb_id, caching=False, ignoreErrors=True)
        if referer:
            req.addHeaderEntry('Referer', referer)
        content = req.request()
        urls = _normalize_urls(content)
        logger.info('-> [KinoGer]: Meinecloud %s returned %d hoster links' % (imdb_id, len(urls)))
        return urls
    except Exception as exc:
        logger.error('-> [KinoGer]: Meinecloud request failed for %s: %s' % (imdb_id, exc))
        return []


def _build_hoster(url, quality='720'):
    """Create an xStream-compatible hoster dictionary."""
    if not url or url.startswith('/vod/'):
        return None
    try:
        name = cParser.urlparse(url)
        if not name or name.lower() in ('youtube.com', 'youtu.be'):
            return None
        if cConfig().isBlockedHoster(name)[0]:
            return None
        return {
            'link': url,
            'name': name,
            'displayedName': '%s [I][%sp][/I]' % (name, quality),
            'quality': quality
        }
    except Exception as exc:
        logger.error('-> [KinoGer]: Cannot build hoster for %s: %s' % (url, exc))
        return None


def load():  # KinoGer Hauptmenue
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.kinoger.lastSearchText')
    oGui = cGui()
    for title, url in (
        ('Neu hinzugefügt', URL_MAIN + '/'),
        ('Aktuell im Kino', URL_KINO),
        ('Filme', URL_MOVIES),
    ):
        params = ParameterHandler()
        params.setParam('sUrl', url)
        oGui.addFolder(cGuiElement(title, SITE_IDENTIFIER, 'showEntries'), params)
    oGui.addFolder(cGuiElement('Genres', SITE_IDENTIFIER, 'showGenre'))
    oGui.addFolder(cGuiElement('Archiv', SITE_IDENTIFIER, 'showArchive'))
    params = ParameterHandler()
    params.setParam('sUrl', URL_SERIES)
    oGui.addFolder(cGuiElement('Serien', SITE_IDENTIFIER, 'showEntries'), params)
    oGui.addFolder(cGuiElement('Suche', SITE_IDENTIFIER, 'showSearch'))
    oGui.setEndOfDirectory()


def showArchive():
    # Das DLE-Archiv gruppiert nach Hinzufuegedatum, nicht Erscheinungsjahr.
    # Jahres-URLs ohne Monatsuntermenue verwenden.
    from datetime import datetime
    oGui = cGui()
    for year in range(datetime.now().year, 2013, -1):
        params = ParameterHandler()
        params.setParam('sUrl', URL_MAIN + '/%d/' % year)
        oGui.addFolder(cGuiElement(str(year), SITE_IDENTIFIER, 'showEntries'), params)
    oGui.setEndOfDirectory()


def showGenre():
    oGui = cGui()
    oRequest = cRequestHandler(URL_MAIN)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48
    sHtmlContent = oRequest.request()
    # Sidebar-Kategorien enthalten normalerweise keinen <b>-Tag.
    pattern = r'<li\s+class=["\']links["\'][^>]*>\s*<a\s+href=["\']([^"\']+)["\'][^>]*>\s*<img[^>]*>\s*(?:<b>)?\s*([^<]+)'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        oGui.showInfo()
        return
    excluded = ('alle filme', 'kinofilme', 'serien', 'serie', 'kinofilme im kino',
                'demnächst im kino', 'demnaechst im kino', 'erwachsene', 'erotikfilme',
                'tv shows')
    seen = set()
    for sUrl, sName in aResult:
        sName = html.unescape(sName).strip()
        if sName.casefold() in excluded:
            continue
        if not sUrl.startswith('http'):
            sUrl = URL_MAIN + '/' + sUrl.lstrip('/')
        if sUrl in seen:
            continue
        seen.add(sUrl)
        params = ParameterHandler()
        params.setParam('sUrl', sUrl)
        oGui.addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    oGui.setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    if sSearchText:
        # KinoGer/DLE verwendet fuer die Suche GET-Parameter (kein POST).
        search_url = URL_MAIN + '/index.php?' + urlencode({
            'do': 'search',
            'subaction': 'search',
            'story': sSearchText,
            'titleonly': '3',
            'submit': 'submit',
        })
        oRequest = cRequestHandler(search_url, ignoreErrors=(sGui is not False))
    sHtmlContent = oRequest.request()
    # Pattern: <div class="title"><div class="begin"><img.../> <a href="URL">Name (Year)</a></div></div>
    # ... gefolgt von <div class="content_text"><img src="THUMB" .../>BESCHREIBUNG<br><br
    pattern = r'<div class="title">\s*<div class="begin"><img[^>]*class="img"[^>]*/>\s*<a href="([^"]+)">([^<]+)</a>.*?<div class="content_text">.*?<img src="([^"]+)"[^>]*alt="[^"]*"[^>]*>(.+?)<br><br'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui:
            oGui.showInfo()
        return

    total = len(aResult)
    isTvshow = True if 'serienstream' in entryUrl else False  # Default basierend auf URL
    for sUrl, sName, sThumbnail, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        # Serien werden via "Staffel" im Titel oder /serienstream-deutsch/-URL erkannt
        isTvshow = True if 'staffel' in sName.lower() or 'serienstream' in entryUrl else False
        # Jahr aus Name extrahieren: "Der Super Mario Galaxy Film (2026)"
        sYear = ''
        isYear, aYear = cParser.parse(sName, r'(.*?)\s+\((\d{4})\)')
        if isYear and aYear:
            sName, sYear = aYear[0]
            sName = sName.strip()
        # Extra-Tags wie "*English*" oder "*Subbed*" rausziehen
        sName = re.sub(r'\s*\*[^*]+\*\s*', ' ', sName).strip()
        if sThumbnail.startswith('/'):
            sThumbnail = URL_MAIN + sThumbnail
        # Beschreibung aus dem Dummy-Block (alles vor dem Genre/Quality-Block)
        sDesc = sDummy
        # Erstes <div ...></div> (text-align right) raus
        sDesc = re.sub(r'<div[^>]*></div>', '', sDesc).strip()
        # Quality aus <b>(HD)</b>
        sQual = ''
        isQual, aQual = cParser.parseSingleResult(sDummy, r'<b>\(([^)]+)\)</b>')
        if isQual:
            sQual = aQual

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        oGuiElement.setThumbnail(sThumbnail)
        if sYear:
            oGuiElement.setYear(sYear)
        if sDesc:
            oGuiElement.setDescription(sDesc[:500])  # Beschreibung trimmen
        if sQual:
            oGuiElement.setQuality(sQual)
        params.setParam('entryUrl', sUrl)
        params.setParam('searchTitle', sName)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui:
        # Pagination: <a href="URL">vorwaerts + ...</a> am Ende des Navigation-Blocks
        # Findet auf Movie-Listings + Genre. Search hat keine Pagination auf kinoger.my
        if not sSearchText:
            isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, r'href="([^"]+)">vorw')
            if isMatchNextPage:
                params.setParam('sUrl', sNextUrl)
                oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showSeasons():
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sName = params.getValue('searchTitle')
    sThumb = params.getValue('thumbnail') if params.exist('thumbnail') else ''
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()
    # Staffel-Nummern aus den Episoden-IDs ziehen: <li id="serie-{STAFFEL}_{EPISODE}">
    pattern = r'<li id="serie-(\d+)_\d+">'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)

    # meinecloud-Fallback: alte DLE-Pattern leer (z.B. neue Serien wie Stranger Things
    # haben Daten nur via meinecloud serials.php Endpoint). Bei 0 Treffern
    # IMDB-ID extrahieren und meinecloud-Resolver fragen.
    if not aResult:
        _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
        sImdbId = aImdb[0] if aImdb else ''
        if sImdbId:
            episodes = []
            if episodes:
                aResult = [str(ep['season']) for ep in episodes]

    if not aResult:
        cGui().showInfo()
        return

    # Unique Staffeln
    seasons = sorted(set(aResult), key=int)
    for sStaffel in seasons:
        oGuiElement = cGuiElement(cConfig().getLocalizedString(30512) + ' %s' % sStaffel, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setSeason(sStaffel)
        if sThumb:
            oGuiElement.setThumbnail(sThumb)
        params.setParam('entryUrl', sUrl)
        params.setParam('staffel', sStaffel)
        params.setParam('searchTitle', sName)
        cGui().addFolder(oGuiElement, params, True)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sName = params.getValue('searchTitle')
    sStaffel = params.getValue('staffel')
    sThumb = params.getValue('thumbnail') if params.exist('thumbnail') else ''
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4  # 4 Stunden
    sHtmlContent = oRequest.request()
    # Pattern: <li id="serie-{STAFFEL}_{EPISODE}"><a href="#">Episoden N</a><ul...>HOSTER_BLOCK</ul></li>
    pattern = r'<li id="serie-' + re.escape(sStaffel) + r'_(\d+)"><a href="#">[^<]+</a>\s*<ul[^>]*>(.*?)</ul>\s*</li>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)

    # meinecloud-Fallback: alte DLE-Pattern leer. IMDB-ID extrahieren, meinecloud
    # fragen, Episoden der Staffel rausfiltern. Synthetischer hosterBlock
    # mit data-link='...' damit showHosters() unveraendert weiterarbeitet.
    aMeinecloudEpisodes = []
    if not aResult:
        _, aImdb = cParser.parse(sHtmlContent, r'(tt\d{7,9})')
        sImdbId = aImdb[0] if aImdb else ''
        if sImdbId:
            try:
                iStaffel = int(sStaffel)
            except (TypeError, ValueError):
                iStaffel = 0
            allEps = []
            aMeinecloudEpisodes = [ep for ep in allEps if ep['season'] == iStaffel]
            aMeinecloudEpisodes.sort(key=lambda ep: ep['episode'])
            # Tupel-Format kompatibel: (episode_str, synthetischer_hoster_block)
            aResult = [
                (str(ep['episode']), 'data-link="%s"' % ep['url'])
                for ep in aMeinecloudEpisodes
            ]

    if not aResult:
        cGui().showInfo()
        return

    total = len(aResult)
    for i, (sEpisode, sHosterBlock) in enumerate(aResult):
        # meinecloud-Mode: Episode-Titel aus den Dict-Daten verwenden, sonst Standard
        if aMeinecloudEpisodes:
            ep = aMeinecloudEpisodes[i]
            sEpTitle = '%s - S%sE%s — %s' % (sName, sStaffel.zfill(2), sEpisode.zfill(2), ep['title'])
        else:
            sEpTitle = '%s - S%sE%s' % (sName, sStaffel.zfill(2), sEpisode.zfill(2))
        oGuiElement = cGuiElement(sEpTitle, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setMediaType('episode')
        oGuiElement.setSeason(sStaffel)
        oGuiElement.setEpisode(sEpisode)
        if sThumb:
            oGuiElement.setThumbnail(sThumb)
        params.setParam('hosterBlock', sHosterBlock)
        params.setParam('searchTitle', sName)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    params = ParameterHandler()

    # Serien-Episoden liefern den alten Hosterblock direkt.
    sHosterBlock = params.getValue('hosterBlock') if params.exist('hosterBlock') else ''
    sPageUrl = params.getValue('entryUrl') if params.exist('entryUrl') else ''
    sHtmlContent = ''

    if sHosterBlock:
        _, direct_urls = cParser.parse(sHosterBlock, r'data-link="([^"]+)"')
    else:
        if not sPageUrl:
            return []
        sHtmlContent = cRequestHandler(sPageUrl, caching=False, ignoreErrors=True).request()
        _, direct_urls = cParser.parse(sHtmlContent, r'data-link="([^"]+)"')

        # Aktuelle kinoger.fun-Filmseiten: IMDb-ID auslesen und Meinecloud direkt abrufen.
        if not direct_urls:
            imdb_match = re.search(r'(tt\d{7,10})', sHtmlContent or '')
            if imdb_match:
                direct_urls = _resolve_meinecloud_movie(imdb_match.group(1), referer=sPageUrl)

        # Legacy-Fallback für ältere show(...)-Blöcke.
        if not direct_urls:
            _, direct_urls = cParser.parse(sHtmlContent, r"show[^>]\d,[^>][^>]'([^']+)'")

    # Falls ein Meinecloud-Link selbst eingebettet ist, dessen Antwort expandieren.
    expanded = []
    for url in direct_urls or []:
        url = html.unescape(url).replace('\\/', '/')
        if 'meinecloud.click/movie/' in url:
            imdb_match = re.search(r'(tt\d{7,10})', url)
            expanded.extend(_resolve_meinecloud_movie(imdb_match.group(1), referer=sPageUrl) if imdb_match else [])
        else:
            expanded.append(url)

    seen = set()
    for url in expanded:
        if url in seen:
            continue
        seen.add(url)
        hoster = _build_hoster(url)
        if hoster:
            hosters.append(hoster)

    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.kinoger.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText:
            return
        win.setProperty('xstream.kinoger.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_MAIN + '/', oGui, sSearchText)
