# -*- coding: utf-8 -*-
# Python 3

# Always pay attention to the translations in the menu!
# Sprachauswahl für Filme
# HTML LangzeitCache hinzugefügt
# showValue:     24 Stunden
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
import re
import html


SITE_IDENTIFIER = 'filmpalast'
SITE_NAME = 'FilmPalast'
SITE_ICON = 'filmpalast.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'filmpalast.to') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN
# URL_MAIN = 'https://filmpalast.to'
URL_MOVIES = URL_MAIN + '/movies/%s'
URL_SERIES = URL_MAIN + '/serien/view'
URL_ENGLISH = URL_MAIN + '/search/genre/Englisch'
URL_SEARCH = URL_MAIN + '/search/title/%s'

SCRAPER_SETTINGS = f'''
            <group id="filmpalast" label="30702">
                <setting id="plugin_filmpalast" type="boolean" label="30050" help="30411">
                    <level>0</level>
                    <default>True</default>
                    <control type="toggle"/>
                </setting>
                <setting id="global_search_filmpalast" type="boolean" label="30052">
                    <level>0</level>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_filmpalast">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_filmpalast_checkDomain" type="boolean" label="30277">
                    <visible>false</visible>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_filmpalast">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_filmpalast">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_filmpalast.domain" type="string" label="30278" help="">
                    <level>0</level>
                    <default>filmpalast.to</default>
                    <constraints>
                        <allowempty>true</allowempty>
                    </constraints>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_filmpalast">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_filmpalast">false</dependency>
                    </dependencies>
                    <control type="edit" format="string">
                        <heading>30278</heading>
                    </control>
                </setting>
                <setting id="plugin_filmpalast_status" type="string" label="Dummy" help="">
                    <visible>false</visible>
                    <default>true</default>
                    <control type="toggle"/>
                </setting>
            </group>
'''


def _add_menu_item(title, function, url=None, value=None):
    params = ParameterHandler()
    if url is not None:
        params.setParam('sUrl', url)
    if value is not None:
        params.setParam('value', value)
    cGui().addFolder(cGuiElement(title, SITE_IDENTIFIER, function), params)


def load():  # FilmPalast-Hauptmenue: Filme, Serien und Suche getrennt
    logger.info('Load %s' % SITE_NAME)
    _add_menu_item('Aktuelle Filme', 'showCurrentMovies')
    _add_menu_item('Neu hinzugefügt (Filme)', 'showEntries', URL_MOVIES % 'new')
    _add_menu_item('Blockbuster / Top Filme', 'showEntries', URL_MOVIES % 'top')
    _add_menu_item('IMDb-Bewertung', 'showEntries', URL_MOVIES % 'imdb')
    _add_menu_item('Genres', 'showValue', URL_MOVIES % 'new', 'genre')
    _add_menu_item('Erscheinungsjahr suchen', 'showYearSearch')
    _add_menu_item('Serien', 'showSeriesMenu')
    _add_menu_item('Suche', 'showSearch')
    cGui().setEndOfDirectory()


def showCurrentMovies():
    """Show the film posters from the homepage slider (not /movies/new)."""
    oGui = cGui()
    try:
        homepage = cRequestHandler(URL_MAIN + '/', caching=False, bypass_dns=True).request()
        slider_match = re.search(r'<ul\b[^>]*\bid=["\']sliderDla["\'][^>]*>(.*?)</ul\s*>', homepage or '', re.I | re.S)
        if not slider_match:
            oGui.showInfo()
            return

        # Each slider card contains two links to the same film; use the
        # poster link to get the film URL, title and thumbnail exactly once.
        cards = []
        seen = set()
        for item in re.findall(r'<li\b[^>]*class=["\'][^"\']*\bslider-li\b[^"\']*["\'][^>]*>.*?</li\s*>', slider_match.group(1), re.I | re.S):
            poster = re.search(r'<a\b(?=[^>]*\bhref=["\']([^"\']+)["\'])[^>]*>\s*<img\b([^>]+)>', item, re.I | re.S)
            if not poster:
                continue
            film_url = html.unescape(poster.group(1)).strip()
            image_tag = poster.group(2)
            image = re.search(r'\bsrc=["\']([^"\']+)["\']', image_tag, re.I)
            title = re.search(r'\balt=["\']([^"\']+)["\']', image_tag, re.I)
            if not (image and title) or film_url in seen:
                continue
            seen.add(film_url)
            cards.append('<article><a href="%s" title="%s"><img src="%s"></a></article>' % (
                html.escape(film_url, quote=True), html.escape(html.unescape(title.group(1)).strip(), quote=True),
                html.escape(html.unescape(image.group(1)), quote=True)))

        if not cards:
            oGui.showInfo()
            return
        logger.info('[FilmPalast-Slider] %d aktuelle Filme gefunden' % len(cards))
        showEntries(URL_MAIN + '/', pageHtml=''.join(cards), sliderMode=True)
    except Exception as exc:
        logger.info('[FilmPalast-Slider] Fehler: %s' % exc)
        oGui.showInfo()


def showMovieMenu():  # Rueckwaertskompatibilitaet fuer gespeicherte Kodi-Eintraege
    _add_menu_item('Neu hinzugefügt', 'showEntries', URL_MOVIES % 'new')
    _add_menu_item('Blockbuster / Top Filme', 'showEntries', URL_MOVIES % 'top')
    _add_menu_item('IMDb-Bewertung', 'showEntries', URL_MOVIES % 'imdb')
    _add_menu_item('Genres', 'showValue', URL_MOVIES % 'new', 'genre')
    _add_menu_item('Erscheinungsjahr suchen', 'showYearSearch')
    cGui().setEndOfDirectory()


def showSeriesMenu():
    # Nur belegte Serien-Rubriken; keine ungetesteten IMDb-/Top-URLs erfinden.
    _add_menu_item('Neu hinzugefügt (Serien)', 'showEntries', URL_SERIES)
    _add_menu_item('Von A–Z', 'showValue', URL_SERIES, 'movietitle')
    cGui().setEndOfDirectory()


def showYearSearch():
    year = cGui().showKeyBoard(sHeading='Erscheinungsjahr eingeben (z. B. 2024)')
    if not year:
        return
    year = year.strip()
    if not re.fullmatch(r'(?:18[89]\d|19\d{2}|20\d{2}|2100)', year):
        cGui().showInfo()
        return
    # FilmPalast unterstuetzt die Jahreszahl direkt in der Titelsuche.
    # Kein sSearchText-Filter: Der Filmtitel selbst enthaelt meist kein Jahr.
    showEntries(URL_SEARCH % cParser.quotePlus(year), yearFilter=year)


def showValue():
    params = ParameterHandler()
    value = params.getValue("value")
    oRequest = cRequestHandler(params.getValue('sUrl'), bypass_dns=True)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24 # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()
    pattern = '<section[^>]id="%s">(.*?)</section>' % value # Suche in der Section Einträge
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sContainer, 'href="([^"]+)">([^<]+)')
        for sUrl, sName in aResult:
            params.setParam('sUrl', sUrl)
            cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    if not isMatch:
        cGui().showInfo()
        return
    cGui().setEndOfDirectory()


def _find_movie_year(source, detail=False):
    """Read the site's labelled film year, never an unrelated page date."""
    if not source:
        return None
    patterns = [
        r'\bJahr\s*:\s*(?:<[^>]*>\s*)*([12]\d{3})\b',
    ]
    if detail:
        patterns.extend((
            r'\bVeröffentlicht\s*:\s*(?:<[^>]*>\s*)*([12]\d{3})\b',
            r'\bErscheinungsjahr\s*:\s*(?:<[^>]*>\s*)*([12]\d{3})\b',
        ))
    for pattern in patterns:
        match = re.search(pattern, source, re.IGNORECASE)
        if match and 1888 <= int(match.group(1)) <= 2100:
            return match.group(1)
    return None


def _release_year(source):
    """Last resort: year delimited by dots in the release filename."""
    match = re.search(r'releaseTitleHome[^>]*>\s*Release:\s*([^<]+)', source, re.IGNORECASE)
    if match:
        year = re.search(r'(?<!\d)\.([12]\d{3})\.(?!\d)', match.group(1))
        if year and 1888 <= int(year.group(1)) <= 2100:
            return year.group(1)
    return None


def _movie_title_with_year(name, year):
    """Remove trailing repeated year suffixes, preserving years inside titles."""
    title = name.strip()
    title = re.sub(r'(?:\s*-?\s*\([12]\d{3}\))+(?=\s*$)', '', title).strip()
    if year:
        title += ' - (%s)' % year
    return title


def showEntries(entryUrl=False, sGui=False, sSearchText=False, yearFilter=None, pageHtml=None, sliderMode=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    if yearFilter is None:
        yearFilter = params.getValue('yearFilter') or None
    isTvshow = False
    if pageHtml is None:
        oRequest = cRequestHandler(entryUrl, caching=False, ignoreErrors=(sGui is not False), bypass_dns=True)
        if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
        sHtmlContent = oRequest.request()
    else:
        sHtmlContent = pageHtml
    pattern = '<article[^>]*>\s*<a href="([^"]+)" title="([^"]+)">\s*<img src=["\']([^"\']+)["\'][^>]*>(.*?)</article>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        pattern = '<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"[^>]*>[^<]*<img[^>]*src=["\']([^"\']*)["\'][^>]*>\s*</a>(\s*)</article>'
        isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    # FilmPalast zeigt auf /movies/new, /movies/top usw. teilweise keine
    # Erscheinungsjahre. Die Startseite hat dagegen bei denselben Filmen
    # "Jahr: YYYY" in den vollstaendigen Artikelkarten. Nur echte,
    # eindeutig per Film-URL zugeordnete Jahresangaben uebernehmen.
    def collect_article_years(page_html):
        result = {}
        for match in re.finditer(r'<article\b[^>]*>.*?</article\s*>', page_html or '', re.I | re.S):
            block = match.group(0)
            link = re.search(r'<a\b[^>]*\bhref\s*=\s*["\']([^"\']+)', block, re.I)
            if not link:
                continue
            year = _find_movie_year(block)
            if year:
                url = html.unescape(link.group(1)).strip()
                url = re.sub(r'^https?:', '', url, flags=re.I)
                result[url.rstrip('/')] = year
        return result

    movie_years_by_url = collect_article_years(sHtmlContent)
    # Nur die erste Seite der Neu-Zugaenge entspricht der Startseite.
    # Kein unzuverlaessiges Matching ueber Titel oder Release-Dateien.
    if not movie_years_by_url and re.search(r'/movies/new/?(?:\?.*)?$', entryUrl or '', re.I):
        try:
            home_html = cRequestHandler(URL_MAIN + '/', caching=True, ignoreErrors=True, bypass_dns=True).request()
            movie_years_by_url = collect_article_years(home_html)
            logger.info('[FilmPalast-Jahr] Startseiten-Abgleich: %d Filme mit Jahr' % len(movie_years_by_url))
        except Exception as exc:
            logger.info('[FilmPalast-Jahr] Startseiten-Abgleich fehlgeschlagen: %s' % exc)

    # Auf 16 Eintraege pro Seite begrenzen
    if not sliderMode:
        aResult = aResult[:16]
    total = len(aResult)
    for sUrl, sName, sThumbnail, sDummy in aResult:
        isTvshow, _tvCheck = cParser.parse(sName, 'S\d\dE\d\d')
        if '/serien/' in (entryUrl or '').lower() or '/serien/' in sUrl.lower():
            isTvshow = True
        # seriesname should not be crippled here!
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        # Hochaufloesende Poster in allen FilmPalast-Listen verwenden,
        # sofern die Seite den bekannten /files/movies/240/-Pfad liefert.
        # Andere Bildpfade (z.B. Serien) unveraendert lassen.
        sThumbnail = sThumbnail.replace('/files/movies/240/', '/files/movies/450/', 1)
        if sThumbnail.startswith('/'):
            sThumbnail = URL_MAIN + sThumbnail
        ### ÄNDERUNG ANFANG ###
        sYear = None
        sYearSource = 'keine'
        if not isTvshow:
            sYear = movie_years_by_url.get(re.sub(r'^https?:', '', html.unescape(sUrl).strip(), flags=re.I).rstrip('/'))
            if sYear:
                sYearSource = 'Uebersicht-Artikel'
            else:
                sYear = _find_movie_year(sDummy)
                if sYear:
                    sYearSource = 'Uebersicht-Fragment'
            if not sYear:
                title_year = re.search(r'\(([12]\d{3})\)\s*$', sName)
                if title_year:
                    sYear = title_year.group(1)
                    sYearSource = 'Filmtitel'
        isYear = bool(sYear)
        sDetailYearForLog = None
        isDuration, sDuration = cParser.parseSingleResult(sDummy, '(?:Laufzeit|Spielzeit):[^>]([\d]+)')
        isRating, sRating = cParser.parseSingleResult(sDummy, 'Imdb:[^>]([^/]+)')
        # Qualität aus Release-String ermitteln
        isRelease, sRelease = cParser.parseSingleResult(sDummy, 'releaseTitleHome[^>]*>\s*Release:\s*([^<]+)')
        sQualLabel = ''
        if isRelease:
            sRel = sRelease.upper()
            if '2160' in sRel or '4K' in sRel or 'UHD' in sRel:
                sQualLabel = '4K'
            elif '1080' in sRel:
                sQualLabel = '1080p'
            elif '720' in sRel:
                sQualLabel = '720p'
            elif 'SD' in sRel or '480' in sRel:
                sQualLabel = 'SD'
            if 'TELESYNC' in sRel or '.TS.' in sRel:
                sQualLabel = (sQualLabel + ' TS').strip()
            elif 'CAM' in sRel:
                sQualLabel = (sQualLabel + ' CAM').strip()
        # Titel erst nach der Detailabfrage zusammensetzen, damit auch dort
        # vorhandene Erscheinungsjahre berücksichtigt werden können.
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        oGuiElement.setThumbnail(sThumbnail)
        if isDuration:
            oGuiElement.addItemValue('duration', sDuration)
        if isRating:
            oGuiElement.addItemValue('rating', sRating.replace(',', '.'))
        # Detail-Request für Beschreibung und Fanart (gecacht)
        sEntryUrl = ('https:' + sUrl) if sUrl.startswith('//') else sUrl
        try:
            sDetailHtml = cRequestHandler(sEntryUrl, caching=True, ignoreErrors=True, bypass_dns=True).request()
            if sDetailHtml:
                # Detailseiten enthalten teils abweichende/falsche Jahreszahlen.
                # Sie werden ausschliesslich fuer Beschreibung/Fanart verwendet.
                if not isTvshow:
                    # FilmPalast-Shortinfos: "Ver&ouml;ffentlicht: YYYY" ist das
                    # tatsaechliche Filmjahr; "Jahr: YYYY" auf der Detailseite
                    # kann hingegen faelschlich das aktuelle Jahr enthalten.
                    shortinfo = html.unescape(sDetailHtml)
                    published = re.search(r'Veröffentlicht\s*:\s*(?:<[^>]*>\s*)*([12]\d{3})\b', shortinfo, re.I)
                    if published and 1888 <= int(published.group(1)) <= 2100:
                        sYear = published.group(1)
                        isYear = True
                        sYearSource = 'Shortinfos-Veröffentlicht'
                    sDetailYearForLog = _find_movie_year(sDetailHtml, detail=True)
                isDesc, sDesc = cParser.parseSingleResult(sDetailHtml, '"description">([^<]+)')
                if not isDesc:
                    isDesc, sDesc = cParser.parseSingleResult(sDetailHtml, 'class="beschreibung[^"]*">([^<]+)')
                if isDesc and sDesc.strip():
                    oGuiElement.setDescription(sDesc.strip())
                isFanart, sFanart = cParser.parseSingleResult(sDetailHtml, 'property="og:image"[^>]*content="([^"]+)"')
                if isFanart and sFanart.startswith('http'):
                    oGuiElement.setFanart(sFanart)
        except Exception:
            pass
        # Kein Ersatzjahr aus Release-Namen: das Release-Jahr kann vom
        # Filmjahr abweichen (z.B. Millennium Actress 2001 vs. 2002).
        # Fehlt das Uebersichtsjahr, lieber kein Jahr als ein falsches.
        # Nur Filmtitel um das Jahr ergänzen, vorhandene Jahresangaben
        # nicht doppeln und die Qualitätsanzeige beibehalten.
        if yearFilter and (isTvshow or sYear != yearFilter):
            continue
        sTitle = sName.strip() if isTvshow else _movie_title_with_year(sName, sYear)
        if not isTvshow and isYear:
            oGuiElement.setYear(sYear)
        if sQualLabel:
            sTitle += ' [%s]' % sQualLabel
        oGuiElement.setTitle(sTitle)
        # Die Website liefert das Filmjahr selbst. Die automatische Metadaten-
        # Abfrage in cGui.addFolder() kann es sonst durch ein falsches Jahr
        # ersetzen. Nur für FilmPalast-Filmeinträge unterbinden.
        if not isTvshow:
            oGuiElement._isMetaSet = True
        # Parameter übergeben
        if sUrl.startswith('//'):
            params.setParam('entryUrl', 'https:' + sUrl)
        else:
            params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbnail)
        if not isTvshow:
            logger.info('[FilmPalast-Jahr-DIAG] VOR addFolder | Titel=%r | Uebersicht/Quelle=%s | Detailjahr=%s | Jahr=%s | Anzeigetitel=%r | MetaSperre=%s' % (
                sName, sYearSource, sDetailYearForLog, sYear, sTitle, bool(getattr(oGuiElement, '_isMetaSet', False))))
        oGui.addFolder(oGuiElement, params, isTvshow, total)
        if not isTvshow:
            logger.info('[FilmPalast-Jahr-DIAG] NACH addFolder | Titel=%r | Jahr=%s | uebergebener Titel=%r' % (
                sName, sYear, sTitle))
    if not sGui and not sSearchText:
        pattern = '<a class="pageing[^"]*"\s*href=([^>]+)>[^\+]+\+</a>\s*</div>'
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, pattern)
        if isMatchNextPage and not sliderMode:
            sNextUrl = sNextUrl.replace("'", "").replace('"', '')
            if sNextUrl.startswith('/'):
                sNextUrl = URL_MAIN + sNextUrl
            params.setParam('sUrl', sNextUrl)
            if yearFilter:
                params.setParam('yearFilter', yearFilter)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showSeasons():
    params = ParameterHandler()
    # Parameter laden
    sUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue("sThumbnail")
    sName = params.getValue('sName')
    oRequest = cRequestHandler(sUrl, bypass_dns=True)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # HTML Cache Zeit 6 Stunden
    sHtmlContent = oRequest.request()
    pattern = '<a[^>]*class="staffTab"[^>]*data-sid="(\d+)"[^>]*>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return
    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, '"description">([^<]+)')
    total = len(aResult)
    for sSeason in aResult:
        oGuiElement = cGuiElement('Staffel ' + str(sSeason), SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setTVShowTitle(sName)
        oGuiElement.setSeason(sSeason)
        oGuiElement.setMediaType('season')
        oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        cGui().addFolder(oGuiElement, params, True, total)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    # Parameter laden
    sUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue("sThumbnail")
    sSeason = params.getValue('season')
    sShowName = params.getValue('TVShowTitle')
    oRequest = cRequestHandler(sUrl, bypass_dns=True)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4  # HTML Cache Zeit 4 Stunden
    sHtmlContent = oRequest.request()
    pattern = '<div[^>]*class="staffelWrapperLoop[^"]*"[^>]*data-sid="%s">(.*?)</ul></div>' % sSeason
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    pattern = 'href="([^"]+)'
    isMatch, aResult = cParser.parse(sContainer, pattern)
    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, '"description">([^<]+)')
    total = len(aResult)
    for sUrl in aResult:
        isMatch, sName = cParser.parseSingleResult(sUrl, 'e(\d+)')
        oGuiElement = cGuiElement('Episode ' + str(sName), SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setTVShowTitle(sShowName)
        oGuiElement.setSeason(sSeason)
        oGuiElement.setEpisode(sName)
        oGuiElement.setMediaType('episode')
        if sUrl.startswith('//'):
            params.setParam('entryUrl', 'https:' + sUrl)
        else:
            params.setParam('entryUrl', sUrl)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    if '-english' in sUrl: sLang = '(EN)'
    else: sLang = ''
    sHtmlContent = cRequestHandler(sUrl, caching=False, bypass_dns=True).request()
    pattern = 'hostName">([^<]+).*?(http[^"]+)' # Hoster Link
    releaseQuality = 'class="rb">.*?(\d\d\d+)p\.' # Release Qualität
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    isQuality, sQuality = cParser.parseSingleResult(sHtmlContent, releaseQuality)  # sReleaseQuality auslesen z.B. 1080
    if not isQuality: sQuality = '720'
    hosters = []
    if isMatch:
        for sName, sUrl in aResult:
            sName = sName.split(' HD')[0].strip()
            if 'Filemoon' in sName or 'Swiftload' in sName or 'Vidhide' in sName:
                sUrl = sUrl + '$$https://filmpalast.to/' # Referer hinzugefügt
                if cConfig().isBlockedHoster(sName)[0]: continue  # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I]%s [%sp][/I]' % (sName, sLang, sQuality), 'languageCode': sLang, 'quality': sQuality}  # Qualität Anzeige aus Release Eintrag
                hosters.append(hoster)
            else:
                if cConfig().isBlockedHoster(sName)[0]: continue # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I]%s [%sp][/I]' % (sName, sLang, sQuality), 'languageCode': sLang, 'quality': sQuality} # Qualität Anzeige aus Release Eintrag
                hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters

def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_SEARCH % cParser.quotePlus(sSearchText), oGui, sSearchText)
