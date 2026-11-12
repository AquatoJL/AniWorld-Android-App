# -*- coding: utf-8 -*-
# Python 3

# Always pay attention to the translations in the menu!
# Sprachauswahl für Hoster enthalten.
# Ajax Suchfunktion enthalten.
# HTML LangzeitCache hinzugefügt

# 2022-12-06 Heptamer  - Suchfunktion überarbeitet
# 2026-12-29 viewIT    - Hotfix wegen V2 von Serienstream
# 2026-02-02 SatBandit - Hotfix wegen V2 von Serienstream
# 2026-03-29 merge     - Patterns an aktuelles HTML angepasst, Referenz-Logik integriert

import ast
import re
import json
import xbmcgui
import xbmc
from html import unescape
from urllib.parse import quote_plus

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser, cUtil
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'aniworld'
SITE_NAME = 'AniWorld'
SITE_ICON = 'serienstream.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)

if DOMAIN == '186.2.175.111':
    URL_MAIN = 'http://' + DOMAIN
    REFERER  = 'http://' + DOMAIN
    proxy    = 'true'
else:
    URL_MAIN = 'https://' + DOMAIN
    REFERER  = 'https://' + DOMAIN
    proxy    = 'false'

URL_SERIES       = URL_MAIN + '/animes'
URL_NEW_SERIES   = URL_MAIN              # Neue Serien: new-shows-slider auf der Startseite
URL_NEW_EPISODES = URL_MAIN + '/neue-episoden'  # Existiert laut Footer!
URL_POPULAR      = URL_MAIN + '/beliebte-animes'
URL_LOGIN        = URL_MAIN + '/login'
URL_SEARCH       = URL_MAIN + '/search?q='
URL_SEARCH_API   = URL_MAIN + '/api/search/suggest?q='

# Die manuell ausgewählte SerienStream-Adresse wird nicht durch DNS-Bypass überschrieben.

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _abs_url(url):
    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return URL_MAIN + url if url.startswith('/') else URL_MAIN + '/' + url


def _normalize_series_root(url):
    if not url:
        return ''
    full = _abs_url(url).split('?', 1)[0].split('#', 1)[0].replace('\\/', '/').rstrip('/')
    full = re.sub(r'/staffel-\d+(?:/.*)?$', '', full)
    full = re.sub(r'/episode-\d+(?:/.*)?$', '', full)
    return full


def _norm_search_text(value):
    value = (value or '').lower()
    value = re.sub(r'[^a-z0-9]+', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return value


def _search_title_match(query, title):
    q = _norm_search_text(query)
    if not q:
        return False
    t = ' ' + _norm_search_text(title) + ' '
    return (' ' + q + ' ') in t


def extractPoster(sHtml):
    """Extrahiert das Serien-Poster aus der Detailseite.
    Bevorzugt Desktop-Container (col-lg-2), Fallback: show-cover-mobile."""
    sThumbnail = ''
    match = re.search(r'class="[^"]*col-lg-2[^"]*">.*?<img[^>]+data-src="([^"]+)"', sHtml, re.DOTALL)
    if not match:
        match = re.search(r'class="[^"]*show-cover-mobile[^"]*">.*?<img[^>]+data-src="([^"]+)"', sHtml, re.DOTALL)
    if match:
        sThumbnail = match.group(1).strip()
        if sThumbnail.startswith('/'):
            sThumbnail = URL_MAIN + sThumbnail
        sThumbnail = sThumbnail.replace('format=webp', 'format=jpg').replace('format=avif', 'format=jpg')
    return sThumbnail


# ---------------------------------------------------------------------------
# Hauptmenü
# ---------------------------------------------------------------------------

def load():
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('serienstream.lastSearchText')
    username = cConfig().getSetting('serienstream.user')
    password = cConfig().getSetting('serienstream.pass')
    if username == '' or password == '':
        xbmcgui.Dialog().notification(
            cConfig().getLocalizedString(30241),
            cConfig().getLocalizedString(30264),
            xbmcgui.NOTIFICATION_WARNING,
            8000
        )
    else:
        params = ParameterHandler()
        params.setParam('sUrl', URL_NEW_SERIES)
        cGui().addFolder(cGuiElement('Neue Serien', SITE_IDENTIFIER, 'showNewSeries'), params)

        params = ParameterHandler()
        params.setParam('sUrl', URL_NEW_EPISODES)
        cGui().addFolder(cGuiElement('Neue Folgen', SITE_IDENTIFIER, 'showNewEpisodes'), params)

        # Tab-Sektionen (section-0 bis section-3) auf der Startseite
        for sLabel, sSection in [
            ('Gerade im Trend',        'tab:section-1'),
            ('Wöchentliche Favoriten', 'tab:section-2'),
            ('Meistbewertete Serien',  'tab:section-3'),
        ]:
            params = ParameterHandler()
            params.setParam('sSection', sSection)
            cGui().addFolder(cGuiElement(sLabel, SITE_IDENTIFIER, 'showTrendSection'), params)

        # Discover-Blöcke (h4-Überschriften in #discover-blocks)
        for sLabel, sSection in [
            ('Geheimtipps',       'discover:Geheimtipps'),
            ('Suchtgefahr',       'discover:Suchtgefahr'),
            ('Die Beliebtesten',  'discover:Die Beliebtesten'),
            ('Aktuell beliebt',   'discover:Aktuell beliebt'),
        ]:
            params = ParameterHandler()
            params.setParam('sSection', sSection)
            cGui().addFolder(cGuiElement(sLabel, SITE_IDENTIFIER, 'showTrendSection'), params)

        params = ParameterHandler()
        params.setParam('sUrl', URL_POPULAR)
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30519), SITE_IDENTIFIER, 'showBeliebte'), params)

        params = ParameterHandler()
        params.setParam('sUrl', URL_SERIES + '?by=genre')
        cGui().addFolder(cGuiElement('Genre', SITE_IDENTIFIER, 'showGenreMenu'), params)

        params = ParameterHandler()
        params.setParam('sUrl', URL_SERIES)
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30518), SITE_IDENTIFIER, 'showAllSeries'), params)

        params = ParameterHandler()
        params.setParam('sUrl', URL_SERIES + '?by=alpha')
        cGui().addFolder(cGuiElement('A-Z', SITE_IDENTIFIER, 'showAZMenu'), params)

        params = ParameterHandler()
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)

        cGui().setEndOfDirectory()


# ---------------------------------------------------------------------------
# Neue Serien  (/neu)
# ---------------------------------------------------------------------------

def showNewSeries(entryUrl=False, sGui=False):
    """Zeigt Neue Serien von der Startseite (new-shows-slider / Hero-Bereich)."""
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()

    sHtmlContent = cRequestHandler(URL_MAIN, caching=True).request()
    if not sHtmlContent:
        if not sGui: oGui.showInfo()
        return

    sHtml = re.sub(r'\s+', ' ', sHtmlContent)

    # Versuch 1: new-shows-slider Sektion mit <article class="continue-card">
    # Bilder hier: <img src="..."> (kein data-src!)
    clean = []
    seen  = set()

    match_section = re.search(r'class="[^"]*new-shows-slider[^"]*"(.*?)</section>', sHtml, re.DOTALL)
    if match_section:
        fragment = match_section.group(1)
        cards = re.findall(r'<article[^>]*class="[^"]*continue-card[^"]*"[^>]*>(.*?)</article>', fragment, re.DOTALL)
        for card in cards:
            link_match = re.search(r'href="(/serie/[^"]+)"', card)
            img_match  = re.search(r'<img\s+src="([^"]+)"[^>]*alt="([^"]+)"', card)
            if not link_match or not img_match:
                continue
            sLink  = link_match.group(1)
            sThumb = img_match.group(1)
            sTitle = img_match.group(2)
            if sLink in seen or 'data:image' in sThumb:
                continue
            seen.add(sLink)
            clean.append((sLink, sThumb, unescape(sTitle).strip()))

    # Versuch 2: Hero-Bereich — <a href="/serie/..."> mit ## Titel und Backdrop-Bild
    if not clean:
        hero_items = re.findall(
            r'href="(/serie/[^"]+)"[^>]*>.*?'
            r'(?:backdrop/hero[^"]+|backdrop/tile[^"]+)"[^>]*alt="([^"]+)".*?'
            r'##\s*([^\n<]+)',
            sHtml, re.DOTALL
        )
        for sLink, sAlt, sTitle in hero_items:
            if sLink in seen:
                continue
            seen.add(sLink)
            # Backdrop-Tile als Thumbnail (bessere Qualität als Hero)
            thumb_match = re.search(
                r'href="' + re.escape(sLink) + r'".*?backdrop/tile[^"]+\?format=jpg"',
                sHtml
            )
            sThumb = thumb_match.group(0).split('"')[-2] if thumb_match else ''
            clean.append((sLink, sThumb, unescape(sTitle.strip())))

    # Versuch 3: Alle /serie/ Links mit Backdrop-Tile Bildern von der Startseite
    if not clean:
        pairs = re.findall(
            r'href="(/serie/[^"]+)"[^>]*>\s*(?:[^<]*<[^>]*>)*?[^<]*(?:## )?([A-Za-z0-9][^<\n]{2,50})',
            sHtml
        )
        tile_imgs = re.findall(r'src="([^"]*backdrop/tile[^"]*format=jpg[^"]*)"[^>]*alt="([^"]+)"', sHtml)
        tile_map  = {unescape(alt).strip(): url for url, alt in tile_imgs}
        for sLink, sTitle in pairs:
            sTitle = unescape(sTitle.strip()).strip('#').strip()
            if not sTitle or sLink in seen:
                continue
            seen.add(sLink)
            clean.append((sLink, tile_map.get(sTitle, ''), sTitle))
            if len(clean) >= 20:
                break

    if not clean:
        if not sGui: oGui.showInfo()
        return

    total = len(clean)
    for sLink, sThumb, sTitle in clean:
        sFullUrl   = _abs_url(sLink)
        sFullThumb = _abs_url(sThumb) if sThumb else ''
        if sFullThumb:
            sFullThumb = sFullThumb.replace('format=webp', 'format=jpg').replace('format=avif', 'format=jpg')

        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        if sFullThumb:
            oGuiElement.setThumbnail(sFullThumb)

        p = ParameterHandler()
        p.setParam('sUrl',       sFullUrl)
        p.setParam('sName',      sTitle)
        p.setParam('sThumbnail', sFullThumb)
        oGui.addFolder(oGuiElement, p, True, total)

    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def _showCardsFromHtml(oGui, sHtml, sGui=False):
    """Fallback: extrahiert show-card Blöcke mit data-src Poster."""
    pattern = r'href="(/serie/[^"]+)"[^>]*class="[^"]*show-card[^"]*".*?data-src="([^"]+)"[^>]*alt="([^"]+)"'
    aResult = re.findall(r'(?s)' + pattern, sHtml)
    if not aResult:
        pattern2 = r'<a[^>]*class="[^"]*show-card[^"]*"[^>]*href="(/serie/[^"]+)".*?data-src="([^"]+)"[^>]*alt="([^"]+)"'
        aResult = re.findall(r'(?s)' + pattern2, sHtml)
    seen  = set()
    total = len(aResult)
    for sLink, sThumb, sTitle in aResult:
        if sLink in seen:
            continue
        seen.add(sLink)
        sFullUrl   = _abs_url(sLink)
        sFullThumb = _abs_url(sThumb)
        oGuiElement = cGuiElement(unescape(sTitle).strip(), SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        if sFullThumb:
            oGuiElement.setThumbnail(sFullThumb)
        p = ParameterHandler()
        p.setParam('sUrl',  sFullUrl)
        p.setParam('sName', unescape(sTitle).strip())
        oGui.addFolder(oGuiElement, p, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


# ---------------------------------------------------------------------------
# Neue Folgen  (Startseite - Tab "Neueste Episoden")
# ---------------------------------------------------------------------------

def showNewEpisodes(entryUrl=False, sGui=False):
    oGui  = sGui if sGui else cGui()
    params = ParameterHandler()
    iPage = int(params.getValue('iPage') or 1)

    oRequest = cRequestHandler(URL_MAIN, ignoreErrors=(sGui is not False))
    oRequest.cacheTime = 60 * 60 * 1  # 1h Cache
    sHtmlContent = oRequest.request()
    if not sHtmlContent:
        if not sGui: oGui.showInfo()
        return

    sHtml = re.sub(r'\s+', ' ', sHtmlContent)

    # Alle Episode-URLs der Startseite: /serie/slug/staffel-X/episode-Y
    raw = re.findall(r'href="(/serie/([^/]+)/staffel-(\d+)/episode-(\d+))"', sHtml)

    if not raw:
        if not sGui: oGui.showInfo()
        return

    seen  = set()
    items = []
    for sPath, sSlug, sSeason, sEpisode in raw:
        if sPath in seen:
            continue
        seen.add(sPath)
        sTitle = unescape(sSlug.replace('-', ' ')).title()
        items.append((sPath, sTitle, int(sSeason), int(sEpisode)))

    # Seite ausschneiden
    iStart     = (iPage - 1) * PAGE_SIZE
    iEnd       = iStart + PAGE_SIZE
    page_items = items[iStart:iEnd]
    total      = len(page_items)

    for sPath, sTitle, iSeason, iEpisode in page_items:
        sDisplay   = '%s - S%02dE%02d' % (sTitle, iSeason, iEpisode)
        sEpUrl     = _abs_url(sPath)
        sSeriesUrl = re.sub(r'/staffel-\d+/episode-\d+$', '', sEpUrl)

        # Poster + Beschreibung mit 1h Cache
        sThumbnail = ''
        sDesc      = ''
        try:
            oThumbReq = cRequestHandler(sSeriesUrl, caching=True)
            oThumbReq.cacheTime = 60 * 60 * 1
            sDetailHtml = oThumbReq.request()
            if sDetailHtml:
                sThumbnail = extractPoster(sDetailHtml)
                match_desc = re.search(r'<span[^>]*class="description-text"[^>]*>(.*?)</span>', sDetailHtml, re.DOTALL)
                if match_desc:
                    sDesc = unescape(re.sub(r'<[^>]*>', '', match_desc.group(1))).strip()
                if not sDesc:
                    match_meta = re.search(r'name="description"\s+content="([^"]+)"', sDetailHtml)
                    if match_meta:
                        sDesc = unescape(match_meta.group(1)).strip()
        except Exception:
            pass

        oGuiElement = cGuiElement(sDisplay, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setMediaType('episode')
        oGuiElement.setTVShowTitle(sTitle)
        oGuiElement.setSeason(iSeason)
        oGuiElement.setEpisode(iEpisode)
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if sDesc:
            oGuiElement.setDescription(sDesc)

        p = ParameterHandler()
        p.setParam('sUrl',         sEpUrl)
        p.setParam('entryUrl',     sSeriesUrl)
        p.setParam('sName',        sTitle)
        p.setParam('sThumbnail',   sThumbnail)
        p.setParam('sDescription', sDesc)
        oGui.addFolder(oGuiElement, p, False, total)

    # Nächste Seite
    if iEnd < len(items):
        p = ParameterHandler()
        p.setParam('iPage', str(iPage + 1))
        oGui.addNextPage(SITE_IDENTIFIER, 'showNewEpisodes', p)

    if not sGui:
        oGui.setView('episodes')
        oGui.setEndOfDirectory()


# ---------------------------------------------------------------------------
# Beliebte Serien
# ---------------------------------------------------------------------------

def showBeliebte(sGui=False):
    oGui = sGui if sGui else cGui()
    sHtmlContent = cRequestHandler(URL_POPULAR, caching=True).request()
    if not sHtmlContent:
        if not sGui: oGui.showInfo()
        return
    sHtmlContent = re.sub(r'\s+', ' ', sHtmlContent)

    titles = re.findall(r'<(?:h2|h3)[^>]*>(.*?)</(?:h2|h3)>', sHtmlContent)
    for sTitle in titles:
        sCleanTitle = re.sub(r'<[^>]*>', '', sTitle).strip()
        sCleanTitle = ''.join(c for c in sCleanTitle if ord(c) < 128).strip()
        if not sCleanTitle or any(x in sCleanTitle for x in ['Kategorien', 'durchsuchen', 'Entdecken']):
            continue
        oGuiElement = cGuiElement(sCleanTitle, SITE_IDENTIFIER, 'showSectionContent')
        p = ParameterHandler()
        p.setParam('sSectionTitle', sCleanTitle)
        oGui.addFolder(oGuiElement, p)

    if not sGui:
        oGui.setEndOfDirectory()


def showTrendSection():
    """Zeigt eine Trend-Sektion von der Startseite.
    sSection Format:
      'tab:section-1'     -> Tab-Pane mit id="section-1" (Gerade im Trend etc.)
      'discover:Suchtgefahr' -> Discover-Block mit h4 Überschrift (Geheimtipps, Suchtgefahr etc.)
    """
    params   = ParameterHandler()
    sSection = params.getValue('sSection')
    iPage    = int(params.getValue('iPage') or 1)
    oGui     = cGui()

    oRequest = cRequestHandler(URL_MAIN, caching=True)
    oRequest.cacheTime = 60 * 60 * 4
    sHtmlContent = oRequest.request()
    if not sHtmlContent:
        oGui.showInfo()
        return

    sHtml = re.sub(r'\s+', ' ', sHtmlContent)
    clean = []
    seen  = set()

    if sSection.startswith('tab:'):
        sId = sSection[4:]
        match = re.search(r'id="' + re.escape(sId) + r'"[^>]*>(.*?)(?=id="section-\d+"|</div> </div> </section>|$)', sHtml, re.DOTALL)
        if match:
            fragment = match.group(1)
            # Titel aus h3 title="..." holen, Link aus href="/serie/..."
            items = re.findall(
                r'href="(/serie/[^"]+)"[^>]*>.*?<h3[^>]*title="([^"]+)"',
                fragment, re.DOTALL
            )
            for sLink, sTitle in items:
                sLink = re.sub(r'/staffel-\d+.*$', '', sLink)
                if sLink in seen: continue
                seen.add(sLink)
                # Kein hochwertiges Bild direkt verfügbar -> per Detail-Request holen
                clean.append((_abs_url(sLink), unescape(sTitle).strip(), ''))

    elif sSection.startswith('discover:'):
        sHeading = sSection[9:]
        escaped  = re.escape(sHeading)
        match = re.search(
            r'<h4[^>]*>\s*' + escaped + r'\s*</h4>.*?<ul[^>]*class="[^"]*discover-list[^"]*"[^>]*>(.*?)</ul>',
            sHtml, re.DOTALL
        )
        if match:
            fragment = match.group(1)
            items = re.findall(
                r'href="(/serie/[^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>',
                fragment, re.DOTALL
            )
            for sLink, sTitle in items:
                if sLink in seen: continue
                seen.add(sLink)
                # channel/thumb ist zu klein -> per Detail-Request hochauflösendes Bild holen
                clean.append((_abs_url(sLink), unescape(sTitle).strip(), ''))

    if not clean:
        oGui.showInfo()
        return

    # Pagination
    iStart     = (iPage - 1) * PAGE_SIZE
    iEnd       = iStart + PAGE_SIZE
    page_items = clean[iStart:iEnd]
    total      = len(page_items)

    for sFullUrl, sTitle, sThumb in page_items:
        # Kein Poster im HTML -> per Detail-Request holen
        if not sThumb or 'data:image' in sThumb:
            try:
                oThumbReq = cRequestHandler(sFullUrl, caching=True)
                oThumbReq.cacheTime = 60 * 60 * 24
                sDetailHtml = oThumbReq.request()
                if sDetailHtml:
                    sThumb = extractPoster(sDetailHtml)
            except Exception:
                sThumb = ''

        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        if sThumb:
            oGuiElement.setThumbnail(sThumb)
        p = ParameterHandler()
        p.setParam('sUrl',       sFullUrl)
        p.setParam('sName',      sTitle)
        p.setParam('sThumbnail', sThumb)
        oGui.addFolder(oGuiElement, p, True, total)

    if iEnd < len(clean):
        p = ParameterHandler()
        p.setParam('sSection', sSection)
        p.setParam('iPage',    str(iPage + 1))
        oGui.addNextPage(SITE_IDENTIFIER, 'showTrendSection', p)

    oGui.setView('tvshows')
    oGui.setEndOfDirectory()


def showSectionContent():
    params      = ParameterHandler()
    sTargetTitle = params.getValue('sSectionTitle')
    oGui = cGui()

    sHtmlContent = cRequestHandler(URL_POPULAR, caching=True).request()
    if not sHtmlContent:
        oGui.showInfo()
        return
    sHtmlContent = re.sub(r'\s+', ' ', sHtmlContent)

    find_section = r'<(?:h2|h3)[^>]*>[^<]*' + re.escape(sTargetTitle) + r'.*?</(?:h2|h3)>(.*?)(?=<h2|<h3|$)'
    match = re.search(find_section, sHtmlContent)
    if match:
        sFragment = match.group(1)
        pattern   = r'href="(/serie/[^"]+)".*?<img.*?(?:data-src|src)="([^"]+)".*?alt="([^"]+)"'
        items     = re.findall(pattern, sFragment)
        seen_links = set()
        for sLink, sThumb, sName in items:
            sName       = unescape(sName).strip()
            sSeriesLink = sLink.split('/staffel-')[0]
            if sSeriesLink in seen_links:
                continue
            seen_links.add(sSeriesLink)
            if 'data:image/gif' in sThumb:
                continue
            sThumb = _abs_url(sThumb)
            oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
            oGuiElement.setThumbnail(sThumb)
            p = ParameterHandler()
            p.setParam('sUrl',       _abs_url(sSeriesLink))
            p.setParam('sName',      sName)
            p.setParam('sThumbnail', sThumb)
            oGui.addFolder(oGuiElement, p)

    oGui.setEndOfDirectory()


# ---------------------------------------------------------------------------
# Genre-Menü
# ---------------------------------------------------------------------------


def showGenreMenu():
    """Genre-Liste aus der Startseite extrahieren (/genre/xxx Links)."""
    oGui = cGui()

    # Genres direkt von der Startseite laden (color-list)
    sHtmlContent = cRequestHandler(URL_MAIN, caching=True).request()
    if not sHtmlContent:
        oGui.showInfo()
        return

    # Neue Struktur 2026: <a href="/genre/abenteuer" class="btn btn-sm">Abenteuer</a>
    results = re.findall(r'href="(/genre/([^"]+))"[^>]*>\s*([^<]+)\s*</a>', sHtmlContent)

    seen = set()
    for sPath, sSlug, sRawName in results:
        sName = unescape(sRawName).strip()
        if not sName or sPath in seen:
            continue
        seen.add(sPath)
        p = ParameterHandler()
        p.setParam('sUrl',       _abs_url(sPath))
        p.setParam('sGenreLabel', sName)
        oGui.addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showGenreEntries'), p)

    oGui.setEndOfDirectory()


PAGE_SIZE = 20  # Serien pro Seite

def showGenreEntries():
    """Zeigt Serien einer Genre-Seite (/genre/xxx)."""
    params       = ParameterHandler()
    sUrl         = params.getValue('sUrl')   # z.B. https://s.to/genre/abenteuer
    iPage        = int(params.getValue('iPage') or 1)
    oGui = cGui()

    sHtmlContent = cRequestHandler(sUrl).request()
    if not sHtmlContent:
        oGui.showInfo()
        return

    sHtml = re.sub(r'\s+', ' ', sHtmlContent)

    # series-item Liste oder show-card Layout
    items = re.findall(r'<li[^>]*class="[^"]*series-item[^"]*"[^>]*>[\s\S]*?<a[^>]+href="(/serie/[^"]+)"[^>]*>([^<]+)</a>', sHtml)
    if not items:
        items = re.findall(r'<a[^>]+href="(/serie/[^"]+)"[^>]*class="[^"]*show-card[^"]*"[^>]*>[\s\S]*?<img[^>]+alt="([^"]+)"', sHtml)

    seen  = set()
    clean = []
    for sLink, sName in items:
        if sLink in seen:
            continue
        seen.add(sLink)
        clean.append((_abs_url(sLink), unescape(sName).strip()))

    if not clean:
        oGui.showInfo()
        return

    iStart     = (iPage - 1) * PAGE_SIZE
    iEnd       = iStart + PAGE_SIZE
    page_items = clean[iStart:iEnd]
    total      = len(page_items)

    for sFullUrl, sName in page_items:
        # Poster mit 24h Cache
        sThumbnail = ''
        try:
            oThumbReq = cRequestHandler(sFullUrl, caching=True)
            oThumbReq.cacheTime = 60 * 60 * 24
            sDetailHtml = oThumbReq.request()
            if sDetailHtml:
                sThumbnail = extractPoster(sDetailHtml)
        except Exception:
            pass

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        p = ParameterHandler()
        p.setParam('sUrl',       sFullUrl)
        p.setParam('sName',      sName)
        p.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, p, True, total)

    if iEnd < len(clean):
        p = ParameterHandler()
        p.setParam('sUrl',  sUrl)
        p.setParam('iPage', str(iPage + 1))
        oGui.addNextPage(SITE_IDENTIFIER, 'showGenreEntries', p)

    oGui.setView('tvshows')
    oGui.setEndOfDirectory()

# ---------------------------------------------------------------------------
# A-Z Menü
# ---------------------------------------------------------------------------

def showAZMenu():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    sHtmlContent = cRequestHandler(sUrl).request()
    if not sHtmlContent:
        cGui().showInfo()
        return
    oGui = cGui()

    match_bar = re.search(r'class="alphabet-bar[^"]*">([\s\S]*?)</nav>', sHtmlContent)
    if match_bar:
        results = re.findall(r'href="(/katalog/[^"]+)"[^>]*>([^<]+)</a>', match_bar.group(1))
        for sNextUrl, sTitle in results:
            p = ParameterHandler()
            p.setParam('sUrl',  _abs_url(sNextUrl))
            p.setParam('sName', sTitle.strip())
            oGui.addFolder(cGuiElement(sTitle.strip(), SITE_IDENTIFIER, 'showKatalog'), p)

    oGui.setEndOfDirectory()


def showKatalog():
    """Zeigt Serien eines Buchstabens. /katalog/X leitet auf /serien um ->
    wir laden /serien und filtern clientseitig nach Anfangsbuchstabe."""
    params  = ParameterHandler()
    sUrl    = params.getValue('sUrl')   # z.B. https://s.to/katalog/A
    iPage   = int(params.getValue('iPage') or 1)
    oGui    = cGui()

    # Buchstabe aus URL extrahieren (letztes Segment: /katalog/A -> A, /katalog/0-9 -> 0-9)
    sLetter = sUrl.rstrip('/').split('/')[-1].upper()

    # Immer /serien laden (die einzige Seite die Daten enthält)
    oRequest = cRequestHandler(URL_SERIES)
    oRequest.cacheTime = 60 * 60 * 24
    sHtmlContent = oRequest.request()
    if not sHtmlContent:
        oGui.showInfo()
        return

    sHtml = re.sub(r'\s+', ' ', sHtmlContent)

    items = re.findall(
        r'<li[^>]*class="[^"]*series-item[^"]*"[^>]*>[\s\S]*?<a[^>]+href="(/serie/[^"]+)"[^>]*>([^<]+)</a>',
        sHtml
    )

    # Deduplizieren + nach Buchstabe filtern
    seen  = set()
    clean = []
    for sLink, sName in items:
        if sLink in seen:
            continue
        seen.add(sLink)
        sName = unescape(sName).strip()
        # Buchstabenfilter
        if sLetter == '0-9':
            if not sName or not sName[0].isdigit():
                continue
        elif sLetter:
            # Sonderzeichen wie ...und, #blackAF -> erster Buchstabe nach führenden Sonderzeichen
            first = ''
            for c in sName:
                if c.isalpha():
                    first = c.upper()
                    break
            if first != sLetter:
                continue
        clean.append((_abs_url(sLink), sName))

    if not clean:
        oGui.showInfo()
        return

    # Seite ausschneiden
    iStart     = (iPage - 1) * PAGE_SIZE
    iEnd       = iStart + PAGE_SIZE
    page_items = clean[iStart:iEnd]
    total      = len(page_items)

    for sFullUrl, sName in page_items:
        # Poster mit 24h Cache
        sThumbnail = ''
        try:
            oThumbReq = cRequestHandler(sFullUrl, caching=True)
            oThumbReq.cacheTime = 60 * 60 * 24
            sDetailHtml = oThumbReq.request()
            if sDetailHtml:
                sThumbnail = extractPoster(sDetailHtml)
        except Exception:
            pass

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        p = ParameterHandler()
        p.setParam('sUrl',       sFullUrl)
        p.setParam('sName',      sName)
        p.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, p, True, total)

    # Nächste Seite
    if iEnd < len(clean):
        p = ParameterHandler()
        p.setParam('sUrl',  sUrl)
        p.setParam('iPage', str(iPage + 1))
        oGui.addNextPage(SITE_IDENTIFIER, 'showKatalog', p)

    oGui.setView('tvshows')
    oGui.setEndOfDirectory()


# ---------------------------------------------------------------------------
# Alle Serien
# ---------------------------------------------------------------------------

def showAllSeries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    iPage = int(params.getValue('iPage') or 1)

    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24
    sHtmlContent = oRequest.request()
    if not sHtmlContent:
        if not sGui: oGui.showInfo()
        return

    items = re.findall(
        r'<li[^>]*class="[^"]*series-item[^"]*"[^>]*>[\s\S]*?<a[^>]+href="(/serie/[^"]+)"[^>]*>([^<]+)</a>',
        sHtmlContent
    )
    if not items:
        items = re.findall(r'<a[^>]+href="(/serie/[^"]+)"[^>]*>([^<]+)</a>', sHtmlContent)

    if not items:
        if not sGui: oGui.showInfo()
        return

    # Deduplizieren
    seen  = set()
    clean = []
    for sLink, sName in items:
        if sLink in seen:
            continue
        seen.add(sLink)
        sName = unescape(sName).strip()
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        clean.append((_abs_url(sLink), sName))

    # Seite ausschneiden
    iStart     = (iPage - 1) * PAGE_SIZE
    iEnd       = iStart + PAGE_SIZE
    page_items = clean[iStart:iEnd]
    total      = len(page_items)

    for sFullUrl, sName in page_items:
        # Poster mit 24h Cache
        sThumbnail = ''
        try:
            oThumbReq = cRequestHandler(sFullUrl, caching=True)
            oThumbReq.cacheTime = 60 * 60 * 24
            sDetailHtml = oThumbReq.request()
            if sDetailHtml:
                sThumbnail = extractPoster(sDetailHtml)
        except Exception:
            pass

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        p = ParameterHandler()
        p.setParam('sUrl',       sFullUrl)
        p.setParam('sName',      sName)
        p.setParam('TVShowTitle', sName)
        p.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, p, True, total)

    # Nächste Seite
    if iEnd < len(clean):
        p = ParameterHandler()
        p.setParam('sUrl',   entryUrl)
        p.setParam('iPage',  str(iPage + 1))
        oGui.addNextPage(SITE_IDENTIFIER, 'showAllSeries', p)

    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


# ---------------------------------------------------------------------------
# Staffeln
# ---------------------------------------------------------------------------

def showSeasons():
    params     = ParameterHandler()
    sUrl       = params.getValue('sUrl')
    sName      = params.getValue('sName') or params.getValue('TVShowTitle') or ''
    sThumbnail = params.getValue('sThumbnail') or ''

    oGui = cGui()
    sHtmlContent = cRequestHandler(sUrl, caching=True).request()
    if not sHtmlContent:
        oGui.showInfo()
        return

    if not sName or sName == 'False':
        title_match = re.search(r'<title>(.*?)\s+(?:Staffel|Season|\|)', sHtmlContent)
        if title_match:
            sName = unescape(title_match.group(1)).strip()

    sDesc = ''
    match_span = re.search(r'<span[^>]*class="description-text"[^>]*>(.*?)</span>', sHtmlContent, re.DOTALL)
    if match_span:
        sDesc = unescape(re.sub(r'<[^>]*>', '', match_span.group(1))).strip()
    if not sDesc:
        match_meta = re.search(r'name="description"\s+content="([^"]+)"', sHtmlContent)
        if match_meta:
            sDesc = unescape(match_meta.group(1)).strip()

    if not sThumbnail or sThumbnail == 'False':
        sThumbnail = extractPoster(sHtmlContent)

    results    = re.findall(r'href="([^"]+/staffel-(\d+))"', sHtmlContent)
    seasons_map = {}
    for sSeasonUrl, sSeasonNum in results:
        if sSeasonNum not in seasons_map:
            seasons_map[sSeasonNum] = sSeasonUrl

    sorted_keys = sorted(seasons_map.keys(), key=lambda x: int(x))

    for sSeasonNum in sorted_keys:
        sSeasonUrl = seasons_map[sSeasonNum]
        sDisplay   = 'Specials' if sSeasonNum == '0' else 'Staffel %s' % sSeasonNum

        oGuiElement = cGuiElement(sDisplay, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setTVShowTitle(sName)
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if sDesc:
            oGuiElement.setDescription(sDesc)

        p = ParameterHandler()
        p.setParam('sUrl',         _abs_url(sSeasonUrl))
        p.setParam('sName',        sName)
        p.setParam('TVShowTitle',  sName)
        p.setParam('sThumbnail',   sThumbnail)
        p.setParam('sDescription', sDesc)
        oGui.addFolder(oGuiElement, p)

    oGui.setView('seasons')
    oGui.setEndOfDirectory()


# ---------------------------------------------------------------------------
# Episoden
# ---------------------------------------------------------------------------

def showEpisodes():
    params       = ParameterHandler()
    sUrl         = params.getValue('sUrl')
    sTVShowTitle = params.getValue('sName') or params.getValue('TVShowTitle') or ''
    sThumbnail   = params.getValue('sThumbnail') or ''
    sDesc        = params.getValue('sDescription') or ''

    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    if not sHtmlContent:
        cGui().showInfo()
        return

    if not sTVShowTitle or sTVShowTitle == 'False':
        title_match = re.search(r'<title>(.*?)\s+Staffel', sHtmlContent)
        if title_match:
            sTVShowTitle = unescape(title_match.group(1)).strip()

    if not sDesc:
        match_plot = re.search(r'<span[^>]*class="description-text"[^>]*>(.*?)</span>', sHtmlContent, re.DOTALL)
        if match_plot:
            sDesc = unescape(match_plot.group(1)).strip()

    if not sThumbnail or sThumbnail == 'False':
        sThumbnail = extractPoster(sHtmlContent)

    sHtmlFlat = re.sub(r'\s+', ' ', sHtmlContent)
    rows = re.findall(r'(<tr[^>]*class="episode-row[^"]*"[^>]*>)(.*?)</tr>', sHtmlFlat, re.DOTALL)

    unique_nav  = []
    titles_dict = {}
    for tr_tag, row_content in rows:
        if 'watch-link' not in row_content:
            continue
        nr_match = re.search(r'episode-number-cell">\s*(\d+)\s*<', row_content)
        if not nr_match:
            continue
        ep_nr = nr_match.group(1)
        link_match = re.search(r"onclick=\"window\.location='([^']+)'\"", tr_tag)
        if not link_match:
            continue
        ep_url = link_match.group(1)
        title_match = re.search(r'episode-title-ger"[^>]*title="([^"]+)"', row_content)
        if not title_match:
            title_match = re.search(r'episode-title-eng"[^>]*title="([^"]+)"', row_content)
        ep_title = unescape(title_match.group(1)).strip() if title_match else ''
        titles_dict[ep_nr] = ep_title
        unique_nav.append((ep_url, ep_nr))

    oGui  = cGui()
    total = len(unique_nav)
    for sUrl2, sEpNr in unique_nav:
        sEpName       = titles_dict.get(sEpNr, '').strip()
        sDisplayTitle = 'Episode %s' % sEpNr
        if sEpName:
            sDisplayTitle += ' - %s' % sEpName

        oGuiElement = cGuiElement(sDisplayTitle, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setMediaType('episode')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if sDesc:
            oGuiElement.setDescription(sDesc)
        oGuiElement.setTVShowTitle(sTVShowTitle)

        p = ParameterHandler()
        p.setParam('sUrl',         _abs_url(sUrl2))
        p.setParam('sThumbnail',   sThumbnail)
        p.setParam('sDescription', sDesc)
        p.setParam('entryUrl',     sUrl)
        oGui.addFolder(oGuiElement, p, False, total)

    oGui.setView('episodes')
    oGui.setEndOfDirectory()


# ---------------------------------------------------------------------------
# Hoster
# ---------------------------------------------------------------------------

def showHosters():
    hosters      = []
    sUrl         = ParameterHandler().getValue('sUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()

    if not sHtmlContent:
        return []

    buttons = re.findall(r'<button[^>]*class="[^"]*link-box[^"]*"[^>]*>', sHtmlContent)
    for sButton in buttons:
        url_match  = re.search(r'data-play-url="([^"]+)"',      sButton)
        name_match = re.search(r'data-provider-name="([^"]+)"', sButton)
        lang_match = re.search(r'data-language-id="([^"]+)"',   sButton)

        if not (url_match and name_match and lang_match):
            continue

        sHUrl = url_match.group(1)
        sName = name_match.group(1)
        sLang = lang_match.group(1)

        if cConfig().isBlockedHoster(sName)[0]:
            continue

        sLanguage = cConfig().getSetting('prefLanguage')
        if sLanguage == '1' and sLang != '1': continue
        if sLanguage == '2' and sLang != '2': continue
        if sLanguage == '3':
            cGui().showLanguage()
            continue

        sLangLabel = '(DE)' if sLang == '1' else '(EN)' if sLang == '2' else '(%s)' % sLang
        sQuality   = '720'

        hoster = {
            'link':          [sHUrl, sName],
            'name':          sName,
            'displayedName': '%s [I]%s [%sp][/I]' % (sName, sLangLabel, sQuality),
            'quality':       sQuality,
            'languageCode':  sLangLabel
        }
        hosters.append(hoster)

    if hosters:
        hosters.append('getHosterUrl')
    if not hosters:
        cGui().showLanguage()
    return hosters


def getHosterUrl(hUrl):
    if type(hUrl) == str:
        hUrl = ast.literal_eval(hUrl)
    Request = cRequestHandler(URL_MAIN + hUrl[0], caching=False)
    Request.addHeaderEntry('Referer', ParameterHandler().getValue('entryUrl'))
    Request.addHeaderEntry('Upgrade-Insecure-Requests', '1')
    Request.request()
    sUrl = Request.getRealUrl()

    if 'voe' in hUrl[1].lower():
        isBlocked, sDomain = cConfig().isBlockedHoster(sUrl)
        if isBlocked:
            sUrl = sUrl.replace(sDomain, 'voe.sx')
            return [{'streamUrl': sUrl, 'resolved': False}]

    return [{'streamUrl': sUrl, 'resolved': False}]


# ---------------------------------------------------------------------------
# Suche
# ---------------------------------------------------------------------------

def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('serienstream.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
        if not sSearchText:
            return
        win.setProperty('serienstream.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    SSsearch(oGui, sSearchText)


def SSsearch(sGui=False, sSearchText=False, iPage=1):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()

    if not sSearchText:
        sSearchText = params.getValue('sSearchText')
    if params.getValue('iPage'):
        iPage = params.getValue('iPage')
    if not sSearchText:
        return

    sUrl = '%s/suche?term=%s&tab=shows&page=%s' % (URL_MAIN, quote_plus(str(sSearchText)), str(iPage))
    sHtmlContent = cRequestHandler(sUrl, caching=True).request()

    if not sHtmlContent:
        oGui.showInfo()
        return

    sHtml = re.sub(r'\s+', ' ', sHtmlContent)
    found_links = set()

    pattern = r'class="card cover-card.*?href="(/serie/[^"]+)".*?(?:data-src|src)="([^"]+)".*?alt="([^"]+)"'
    aResult = re.findall(pattern, sHtml)

    total = len(aResult)
    for sLink, sThumbnail, sTitle in aResult:
        if sLink in found_links:
            continue
        found_links.add(sLink)
        if 'data:image/gif' in sThumbnail:
            continue
        sTitle     = unescape(sTitle)
        sFullUrl   = _abs_url(sLink)
        sFullThumb = _abs_url(sThumbnail)

        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setThumbnail(sFullThumb)

        p = ParameterHandler()
        p.setParam('sUrl',       sFullUrl)
        p.setParam('sName',      sTitle)
        p.setParam('sThumbnail', sFullThumb)
        oGui.addFolder(oGuiElement, p)

    if total >= 20:
        p = ParameterHandler()
        p.setParam('sSearchText', sSearchText)
        p.setParam('iPage', str(int(iPage) + 1))
        oGui.addNextPage(SITE_IDENTIFIER, 'SSsearch', p)

    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()
