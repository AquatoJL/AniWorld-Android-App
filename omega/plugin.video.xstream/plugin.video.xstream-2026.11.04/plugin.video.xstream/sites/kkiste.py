# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showValue:     48 Stunden
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden


from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
import re
from urllib.parse import urljoin

SITE_IDENTIFIER = 'kkiste'
SITE_NAME = 'KKiste'
SITE_ICON = 'kkiste.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'kkiste-io.ink') # Domain Auswahl über die xStream Einstellungen möglich
DOMAIN = str(DOMAIN or 'kkiste-io.ink').replace('https://', '').replace('http://', '').strip().strip('/')
if DOMAIN == 'kkiste-io.skin':
    DOMAIN = 'kkiste-io.ink'
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN + '/'

URL_NEW = URL_MAIN + 'kinofilme-online/'
URL_KINO = URL_MAIN + 'aktuelle-kinofilme-im-kino/'
URL_SERIES = URL_MAIN + 'serienstream-deutsch/'
URL_DEMNAECHST = URL_MAIN + 'demnachst/'
URL_SEARCH = URL_MAIN + 'index.php?do=search&subaction=search&story=%s'

SCRAPER_SETTINGS = f'''
            <group id="plugin_kkiste" label="30709">
                <setting id="plugin_kkiste" type="boolean" label="30050" help="30411">
                    <level>0</level>
                    <default>True</default>
                    <control type="toggle"/>
                </setting>
                <setting id="global_search_kkiste" type="boolean" label="30052">
                    <level>0</level>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_kkiste">False</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_kkiste_checkDomain" type="boolean" label="30277">
                    <visible>false</visible>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_kkiste">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_kkiste">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_kkiste.domain" type="string" label="30278" help="">
                    <level>0</level>
                    <default>kkiste-io.ink</default>
                    <constraints>
                        <allowempty>true</allowempty>
                    </constraints>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_kkiste">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_kkiste">false</dependency>
                    </dependencies>
                    <control type="edit" format="string">
                        <heading>30278</heading>
                    </control>
                </setting>
                <setting id="plugin_kkiste_status" type="string" label="Dummy" help="">
                    <visible>false</visible>
                    <default>true</default>
                    <control type="toggle"/>
                </setting>
            </group>
'''

def load():
    """KKiste Hauptmenü."""
    oGui = cGui()
    for title, url in (
        ('Neu hinzugefügt', URL_NEW),
        ('Aktuelle Kinofilme', URL_KINO),
        ('Demnächst im Kino', URL_DEMNAECHST),
    ):
        params = ParameterHandler()
        params.setParam('sUrl', url)
        oGui.addFolder(cGuiElement(title, SITE_IDENTIFIER, 'showEntries'), params)
    params = ParameterHandler()
    params.setParam('Value', 'Genres')
    oGui.addFolder(cGuiElement('Genres', SITE_IDENTIFIER, 'showValue'), params)
    params = ParameterHandler()
    params.setParam('sUrl', URL_SERIES)
    oGui.addFolder(cGuiElement('Serien', SITE_IDENTIFIER, 'showEntries'), params)
    oGui.addFolder(cGuiElement('Suche', SITE_IDENTIFIER, 'showSearch'), ParameterHandler())
    oGui.setEndOfDirectory()


def showYears():
    """Im Untermenü Erscheinungsjahr nur die freie Jahressuche anbieten."""
    oGui = cGui()
    oGui.addFolder(cGuiElement('Jahr suchen ...', SITE_IDENTIFIER, 'showYearSearch'), ParameterHandler())
    oGui.setEndOfDirectory()


def showYearSearch():
    year = cGui().showKeyBoard(sHeading='Erscheinungsjahr eingeben (z. B. 2025)')
    year = str(year or '').strip()
    if year and len(year) == 4 and year.isdigit() and 1888 <= int(year) <= 2100:
        showYearEntries(year=year)
    else:
        cGui().setEndOfDirectory()


def _kkiste_release_year(html):
    """Read a labelled film year; never use an arbitrary four-digit number."""
    if not html:
        return None
    for pattern in (
        r'\bJahr\s*:?\s*(?:<[^>]+>\s*)*([12]\d{3})\b',
        r'\b(?:Erscheinungsjahr|Release\s*Jahr)\s*:?\s*(?:<[^>]+>\s*)*([12]\d{3})\b',
        r'\b(?:datePublished|releaseDate)\s*["\']?\s*[:=]\s*["\']([12]\d{3})-',
    ):
        match = re.search(pattern, html, re.I)
        if match and 1888 <= int(match.group(1)) <= 2100:
            return match.group(1)
    return None


def showYearEntries(year=None):
    """Check the film detail year and collect up to 15 verified movies."""
    params = ParameterHandler()
    year = str(year or params.getValue('year') or '').strip()
    if not (len(year) == 4 and year.isdigit() and 1888 <= int(year) <= 2100):
        cGui().setEndOfDirectory()
        return

    page_url = params.getValue('sUrl') or urljoin(URL_MAIN, 'xfsearch/' + year + '/')
    try:
        start_index = max(0, int(params.getValue('yearOffset') or 0))
    except (ValueError, TypeError):
        start_index = 0
    oGui = cGui()
    collected = []
    visited = set()
    # Limit each Kodi invocation to two listing pages for responsive navigation.
    for page_number in range(2):
        if page_url in visited:
            break
        visited.add(page_url)
        html = cRequestHandler(page_url).request()
        found, entries = cParser.parse(html, 'class="short">.*?href="([^"]+)">([^<]+).*?(.*?)</article>')
        if not found:
            break
        for index in range(start_index, len(entries)):
            film_url, name, block = entries[index]
            film_url = urljoin(page_url, film_url)
            if 'serie' in film_url.lower() or 'staffel' in name.lower():
                continue
            # Prefer the explicitly labelled release year in the listing.
            # Fetch a detail page only when the listing has no release year.
            release_year = _kkiste_release_year(block)
            if release_year is None:
                detail_html = cRequestHandler(film_url).request()
                release_year = _kkiste_release_year(detail_html)
            if release_year != year:
                continue
            collected.append((film_url, name, block, release_year))
            if len(collected) == 15:
                _kkiste_add_year_movies(oGui, collected)
                next_params = ParameterHandler()
                next_params.setParam('year', year)
                next_params.setParam('sUrl', page_url)
                next_params.setParam('yearOffset', str(index + 1))
                oGui.addNextPage(SITE_IDENTIFIER, 'showYearEntries', next_params)
                oGui.setView('movies')
                oGui.setEndOfDirectory()
                return
        start_index = 0
        next_found, next_url = cParser.parseSingleResult(html, 'next"><a href="([^"]+)')
        if not next_found:
            break
        page_url = urljoin(page_url, next_url)
    if collected:
        _kkiste_add_year_movies(oGui, collected)
    else:
        oGui.showInfo()
    if page_number == 1 and next_found and page_url not in visited:
        next_params = ParameterHandler()
        next_params.setParam('year', year)
        next_params.setParam('sUrl', page_url)
        next_params.setParam('yearOffset', '0')
        oGui.addNextPage(SITE_IDENTIFIER, 'showYearEntries', next_params)
    oGui.setView('movies')
    oGui.setEndOfDirectory()


def _kkiste_add_year_movies(oGui, movies):
    """Render verified movies using the existing KKiste hoster handler."""
    for film_url, name, block, year in movies:
        language = cConfig().getSetting('prefLanguage')
        if language == '1' and 'English*' in name:
            continue
        if language == '2' and 'English*' not in name:
            continue
        element = cGuiElement(name, SITE_IDENTIFIER, 'showHosters')
        element.setMediaType('movie')
        element.setYear(year)
        thumbnail_found, thumbnail = cParser.parseSingleResult(block, 'img src="([^"]+)')
        thumbnail = urljoin(URL_MAIN, thumbnail) if thumbnail_found else ''
        if thumbnail:
            element.setThumbnail(thumbnail)
        quality_found, quality = cParser.parseSingleResult(block, 'label-1">([^<]+)')
        if quality_found:
            element.setQuality(quality)
        desc_found, desc = cParser.parseSingleResult(block, 'desc">([^<]+)')
        if desc_found:
            element.setDescription(desc)
        duration_found, duration = cParser.parseSingleResult(block, r's-red">([\d]+)')
        if duration_found:
            element.addItemValue('duration', duration)
        film_params = ParameterHandler()
        film_params.setParam('entryUrl', film_url)
        film_params.setParam('sThumbnail', thumbnail)
        oGui.addFolder(element, film_params, False, len(movies))


def showValue():
    params = ParameterHandler()
    oRequest = cRequestHandler(URL_MAIN)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48  # 48 Stunden
    sHtmlContent = oRequest.request()
    pattern = '>{0}<.*?</ul>'.format(params.getValue('Value'))
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False, filterYear=None, yearOffset=0):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()
    pattern = 'class="short">.*?href="([^"]+)">([^<]+).*?(.*?)</article>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    if sSearchText:
        aResult = [(u, n, d) for u, n, d in aResult if cParser.search(sSearchText, n)]
    if not filterYear:
        aResult = aResult[:16]
    # Jahresansicht: maximal 15 passende Filme je Kodi-Seite.
    if filterYear:
        matching = []
        for entry in aResult:
            found, release_year = cParser.parseSingleResult(entry[2], r'Jahr.*?([\d]+)')
            if found and str(release_year).strip() == str(filterYear):
                matching.append(entry)
        aResult = matching[int(yearOffset):int(yearOffset) + 15]
    total = len(aResult)
    for sUrl, sName, sDummy in aResult:
        # Abfrage der voreingestellten Sprache
        sLanguage = cConfig().getSetting('prefLanguage')
        if (sLanguage == '1' and 'English*' in sName):   # Deutsch
            continue
        if (sLanguage == '2' and not 'English*' in sName):   # English
            continue
        elif sLanguage == '3':    # Japanisch
            cGui().showLanguage()
            continue
        isThumbnail, sThumbnail = cParser.parseSingleResult(sDummy, 'img src="([^"]+)')  # Thumbnail
        isQuality, sQuality = cParser.parseSingleResult(sDummy, 'label-1">([^<]+)')  # Qualität
        isInfoEpisode, sInfoEpisode = cParser.parseSingleResult(sDummy, r'serie-num.*?</span>([\d]+)')  # Episodenanzahl
        isDesc, sDesc = cParser.parseSingleResult(sDummy, 'desc">([^<]+)')  # Beschreibung
        isYear, sYear = cParser.parseSingleResult(sDummy, r'Jahr.*?([\d]+)')  # Release Jahr
        isDuration, sDuration = cParser.parseSingleResult(sDummy, r's-red">([\d]+)')  # Laufzeit
        if filterYear and (not isYear or str(sYear).strip() != str(filterYear)):
            continue
        isTvshow = True if 'taffel' in sName or 'serie' in sUrl else False
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        if isThumbnail:
            sThumbnail = URL_MAIN + sThumbnail
            oGuiElement.setThumbnail(sThumbnail)
        if isQuality:
            oGuiElement.setQuality(sQuality)
        if isInfoEpisode:
            oGuiElement.setInfo(sInfoEpisode + ' Episoden')
        if isDesc:
            oGuiElement.setDescription(sDesc)
        if isYear:
            oGuiElement.setYear(sYear)
        if isDuration:
            oGuiElement.addItemValue('duration', sDuration)
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        params.setParam('entryUrl', sUrl)
        params.setParam('sThumbnail', sThumbnail if isThumbnail else '')
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui and not sSearchText and not sSearchPageText:
        if filterYear and len(matching) > int(yearOffset) + 15:
            next_params = ParameterHandler()
            next_params.setParam('sUrl', entryUrl)
            next_params.setParam('year', str(filterYear))
            next_params.setParam('yearOffset', str(int(yearOffset) + 15))
            oGui.addNextPage(SITE_IDENTIFIER, 'showYearEntries', next_params)
            oGui.setView('movies')
            oGui.setEndOfDirectory()
            return
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'next"><a href="([^"]+)')
        # Start Page Function
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="pagi-nav(.*?)</main>')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, r'<span>([\d]+)</span>.*?nav_ext">.*?">([\d]+)</a>.*?href="([^"]+)')
            for sPageActive, sPageLast, sNextPage in aResult:
                #sPageName = '[I]Seitensuche starten  >>> [/I] Seite ' + str(sPageActive) + ' von ' + str(sPageLast) + ' Seiten  [I]<<<[/I]'
                sPageName = cConfig().getLocalizedString(30284) + str(sPageActive) + cConfig().getLocalizedString(30285) + str(sPageLast) + cConfig().getLocalizedString(30286)
                params.setParam('sNextPage', sNextPage)
                params.setParam('sPageLast', sPageLast)
                oGui.searchNextPage(sPageName, SITE_IDENTIFIER, 'showSearchPage', params)
            # End Page Function
        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            if filterYear:
                params.setParam('year', str(filterYear))
                params.setParam('yearOffset', '0')
            oGui.addNextPage(SITE_IDENTIFIER, 'showYearEntries' if filterYear else 'showEntries', params)
        oGui.setView('movies' if filterYear else ('tvshows' if 'staffel' in sUrl else 'movies'))
        oGui.setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4  # HTML Cache Zeit 4 Stunden
    sHtmlContent = oRequest.request()
    isMatch, aResult = cParser.parse(sHtmlContent, '"><a href="#">([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, '"description"[^>]content="([^"]+)')
    total = len(aResult)
    for sName in aResult:
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        oGuiElement.setMediaType('episode')
        params.setParam('entryUrl', entryUrl)
        params.setParam('episode', sName)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    sUrl = ParameterHandler().getValue('entryUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    if ParameterHandler().exist('episode'):
        episode = ParameterHandler().getValue('episode')
        pattern = '>{0}<.*?</ul></li>'.format(episode)
        isMatch, sHtmlContent = cParser.parseSingleResult(sHtmlContent, pattern)
    isMatch, aResult = cParser.parse(sHtmlContent, 'link="([^"]+)')
    if isMatch:
        sQuality = '720'
        for sUrl in aResult:
            if 'youtube' in sUrl:
                continue
            elif sUrl.startswith('//'):
                sUrl = 'https:' + sUrl
            sName = cParser.urlparse(sUrl).split('.')[0].strip()
            if 'Mdy48Tn97' in sName: sName = sName.replace('Mdy48Tn97', 'Mixdrop')
            if cConfig().isBlockedHoster(sName)[0]: continue  # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
            hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality}
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


def showSearchPage(): # Suche für die Page Funktion
    params = ParameterHandler()
    sNextPage = params.getValue('sNextPage') # URL mit nächster Seite
    sPageLast = params.getValue('sPageLast') # Anzahl gefundener Seiten
    #sHeading = 'Bitte eine Zahl zwischen 1 und ' + str(sPageLast) + ' wählen.'
    sHeading = cConfig().getLocalizedString(30282) + str(sPageLast)
    sSearchPageText = cGui().showKeyBoard(sHeading=sHeading)
    if not sSearchPageText: return
    sNextSearchPage = sNextPage.split('page/')[0].strip() + 'page/' + sSearchPageText + '/'
    showEntries(sNextSearchPage)
    cGui().setEndOfDirectory()