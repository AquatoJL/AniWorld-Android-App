# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showGenre:     48 Stunden
# showYears:     48 Stunden
# showEpisodes:   4 Stunden

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
import re

SITE_IDENTIFIER = 'hdfilme'
SITE_NAME = 'HD Filme'
SITE_ICON = 'hdfilme.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'hd-filme.lol') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN + '/'
# URL_MAIN = 'https://hdfilme.im/'
URL_NEW = URL_MAIN + 'kinofilme-online/'
URL_KINO = URL_MAIN + 'aktuelle-kinofilme-im-kino/'
URL_MOVIES = URL_MAIN + 'kinofilme-online'
URL_SERIES = URL_MAIN + 'serienstream-deutsch/'
URL_SEARCH = URL_MAIN + 'index.php?do=search&subaction=search&story=%s'
URL_SOON = URL_MAIN + 'demnachst/'

SCRAPER_SETTINGS = f'''
            <group id="plugin_hdfilme" label="30704">
                <setting id="plugin_hdfilme" type="boolean" label="30050" help="30411">
                    <level>0</level>
                    <default>True</default>
                    <control type="toggle"/>
                </setting>
                <setting id="global_search_hdfilme" type="boolean" label="30052">
                    <level>0</level>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_hdfilme">False</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_hdfilme_checkDomain" type="boolean" label="30277">
                    <visible>false</visible>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_hdfilme">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_hdfilme">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_hdfilme.domain" type="string" label="30278" help="">
                    <level>0</level>
                    <default>hd-filme.lol</default>
                    <constraints>
                        <allowempty>true</allowempty>
                    </constraints>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_hdfilme">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_hdfilme">false</dependency>
                    </dependencies>
                    <control type="edit" format="string">
                        <heading>30278</heading>
                    </control>
                </setting>
                <setting id="plugin_hdfilme_status" type="string" label="Dummy" help="">
                    <visible>false</visible>
                    <default>true</default>
                    <control type="toggle"/>
                </setting>
            </group>
'''

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    params.setParam('sUrl', URL_NEW)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showEntries'), params)  # Neues
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Aktuelle Filme im Kino
    params.setParam('sUrl', URL_MOVIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showEntries'), params)  # Filme
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Serien
    params.setParam('sUrl', URL_SOON)
    cGui().addFolder(cGuiElement('Demnächst im Kino', SITE_IDENTIFIER, 'showEntries'), params)  # Demnächst
    params.setParam('sUrl', URL_MAIN)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre'), params)  # Genre
    params.setParam('sUrl', URL_MAIN)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30538), SITE_IDENTIFIER, 'showCountry'), params)  # Land
    params.setParam('sUrl', URL_MAIN)
    cGui().addFolder(cGuiElement('Erscheinungsjahr', SITE_IDENTIFIER, 'showYears'), params)  # Jahre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)  # Suche
    cGui().setEndOfDirectory()


def showGenre(entryUrl=False):
    params = ParameterHandler()
    # Genre-Liste direkt aus bekannten URLs der Website
    genres = [
        ('Kinofilme', URL_MAIN + 'kinofilme-online/'),
        ('Serien', URL_MAIN + 'serienstream-deutsch/'),
        ('Action', URL_MAIN + 'action/'),
        ('Animation', URL_MAIN + 'animation/'),
        ('Abenteuer', URL_MAIN + 'abenteuer/'),
        ('Biographie', URL_MAIN + 'biographie/'),
        ('Drama', URL_MAIN + 'drama/'),
        ('Dokumentation', URL_MAIN + 'dokumentation/'),
        ('Erotikfilme', URL_MAIN + 'erotikfilme/'),
        ('Familie', URL_MAIN + 'familie/'),
        ('Fantasy', URL_MAIN + 'fantasy/'),
        ('Historienfilme', URL_MAIN + 'historien/'),
        ('Horror', URL_MAIN + 'horror/'),
        ('Komödie', URL_MAIN + 'komodie/'),
        ('Krieg', URL_MAIN + 'krieg/'),
        ('Krimi', URL_MAIN + 'krimi/'),
        ('Musikfilme', URL_MAIN + 'musikfilme/'),
        ('Mystery', URL_MAIN + 'mystery/'),
        ('Romantik', URL_MAIN + 'romantik/'),
        ('Science-Fiction', URL_MAIN + 'sci-fi/'),
        ('Sport', URL_MAIN + 'sport/'),
        ('Thriller', URL_MAIN + 'thriller/'),
        ('Western', URL_MAIN + 'western/'),
    ]
    for sName, sUrl in genres:
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showCountry(entryUrl=False):
    params = ParameterHandler()
    # Länder-Liste direkt aus bekannten URLs der Website
    countries = [
        ('Vereinigte Staaten', URL_MAIN + 'xfsearch/Vereinigte Staaten/'),
        ('Deutschland', URL_MAIN + 'xfsearch/Deutschland'),
        ('Japan', URL_MAIN + 'xfsearch/Japan/'),
        ('Vereinigtes Königreich', URL_MAIN + 'xfsearch/Vereinigtes K%C3%B6nigreich'),
        ('Austria', URL_MAIN + 'xfsearch/Austria'),
    ]
    for sName, sUrl in countries:
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showYears(entryUrl=False):
    params = ParameterHandler()
    import datetime
    current_year = datetime.datetime.now().year
    for year in range(current_year, 2013, -1):
        sUrl = URL_MAIN + 'xfsearch/%d' % year
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(str(year), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()



def _getMovieYear(sName, sDummy, sDetailHtml=''):
    """Find a release year without inventing one or repeating an existing suffix."""
    for source, patterns in (
        (sDummy, (r'(?:19|20)\d{2}\s*</p>', r'\b(?:19|20)\d{2}\b')),
        (sName, (r'\(((?:19|20)\d{2})\)',)),
        (sDetailHtml, (
            r'"datePublished"\s*:\s*"((?:19|20)\d{2})',
            r'"(?:releaseDate|release_date|year)"\s*:\s*"?((?:19|20)\d{2})',
            r'(?:Erscheinungsjahr|Produktionsjahr|Release(?:-Jahr)?|Jahr)\s*:?\s*</?[^>]*>\s*((?:19|20)\d{2})',
        )),
    ):
        for pattern in patterns:
            match = re.search(pattern, source or '', re.IGNORECASE)
            if match:
                year = re.search(r'(?:19|20)\d{2}', match.group(0))
                if year:
                    return year.group(0)
    return ''


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()
    pattern = '<div class="box-product(.*?)<h3.*?href="([^"]+).*?">([^<]+).*?(.*?)</li>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    # Auf 16 Eintraege pro Seite begrenzen
    aResult = aResult[:16]
    # Jahresfilter: wenn URL ein xfsearch-Jahr enthält, nur Einträge dieses Jahres anzeigen
    import re as _re
    _year_filter = None
    _year_match = _re.search(r'/xfsearch/(\d{4})', entryUrl)
    if _year_match:
        _year_filter = _year_match.group(1)

    # Auf 16 Eintraege begrenzen NACH Jahresfilter
    if _year_filter:
        aResult = [r for r in aResult if _year_filter in r[3]][:16]
    else:
        aResult = aResult[:16]

    total = len(aResult)
    for sInfo, sUrl, sName, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        # Abfrage der voreingestellten Sprache
        sLanguage = cConfig().getSetting('prefLanguage')
        if (sLanguage == '1' and 'English*' in sName):   # Deutsch
            continue
        if (sLanguage == '2' and not 'English*' in sName):   # English
            continue
        elif sLanguage == '3':    # Japanisch
            cGui().showLanguage()
            continue
        isThumbnail, sThumbnail = cParser.parseSingleResult(sInfo, 'data-src="([^"]+)')  # Thumbnail
        isQuality, sQuality = cParser.parseSingleResult(sDummy, 'quality-product">([^<]+)')  # Qualität
        isTvshow = True if 'taffel' in sName else False
        sYear = _getMovieYear(sName, sDummy) if not isTvshow else ''
        sThumbnail = URL_MAIN + sThumbnail if isThumbnail and not sThumbnail.startswith('http') else sThumbnail
        # Detaildaten werden unten ergänzt; Titel erst danach zusammensetzen.
        # Detail-Request für Beschreibung, Rating und Fanart (gecacht)
        sDescription = sRatingValue = sFanartValue = None
        try:
            sDetailUrl = sUrl if sUrl.startswith('http') else URL_MAIN + sUrl
            sDetailHtml = cRequestHandler(sDetailUrl, caching=True, ignoreErrors=True).request()
            if sDetailHtml:
                if not isTvshow and not sYear:
                    sYear = _getMovieYear(sName, sDummy, sDetailHtml)
                isDesc, sDesc = cParser.parseSingleResult(sDetailHtml, '"description"[^>]content="([^"]+)')
                if isDesc and sDesc.strip():
                    sDescription = sDesc.strip()
                isRating, sRating = cParser.parseSingleResult(sDetailHtml, 'imdb[^>]*>([0-9,.]+)')
                if not isRating:
                    isRating, sRating = cParser.parseSingleResult(sDetailHtml, '"ratingValue"[^>]*content="([^"]+)')
                if isRating:
                    sRatingValue = sRating.replace(',', '.')
                isFanart, sFanart = cParser.parseSingleResult(sDetailHtml, 'property="og:image"[^>]*content="([^"]+)"')
                if not isFanart:
                    isFanart, sFanart = cParser.parseSingleResult(sDetailHtml, '"og:image"[^>]*content="([^"]+)"')
                if isFanart and sFanart.startswith('http'):
                    sFanartValue = sFanart
        except Exception:
            pass
        sTitle = sName.strip()
        if not isTvshow and sYear:
            sTitle = re.sub(r'\s*(?:-\s*)?\(\s*%s\s*\)\s*$' % re.escape(sYear), '', sTitle).strip()
            sTitle += ' - (%s)' % sYear
        if isQuality:
            sTitle += ' [%s]' % sQuality.strip()
        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if isThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if sYear:
            oGuiElement.setYear(sYear)
        if sDescription:
            oGuiElement.setDescription(sDescription)
        if sRatingValue:
            oGuiElement.addItemValue('rating', sRatingValue)
        if sFanartValue:
            oGuiElement.setFanart(sFanartValue)
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'href="([^"]+)">›</a></div>')
        # Start Page Function
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="pagination(.*?)</div></div>')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, '<span>([\d]+)</span>.*?nav_ext">.*?">([\d]+)</a>.*?href="([^"]+)')
            for sPageActive, sPageLast, sNextPage in aResult:
                #sPageName = '[I]Seitensuche starten  >>> [/I] Seite ' + str(sPageActive) + ' von ' + str(sPageLast) + ' Seiten  [I]<<<[/I]'
                sPageName = cConfig().getLocalizedString(30284) + str(sPageActive) + cConfig().getLocalizedString(30285) + str(sPageLast) + cConfig().getLocalizedString(30286)
                params.setParam('sNextPage', sNextPage)
                params.setParam('sPageLast', sPageLast)
                oGui.searchNextPage(sPageName, SITE_IDENTIFIER, 'showSearchPage', params)
            # End Page Function
        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
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
    sHtmlContent = cRequestHandler(ParameterHandler().getValue('entryUrl'), caching=False).request()
    if ParameterHandler().getValue('episode'):
        pass
        pattern = '%s<.*?</ul>' % ParameterHandler().getValue('episode')
        isMatch, sHtmlContent = cParser.parseSingleResult(sHtmlContent, pattern)
    isMatch, aResult = cParser.parse(sHtmlContent, 'link="([^"]+)')
    if isMatch:
        sQuality = '720'
        for sUrl in aResult:
            if 'youtube' in sUrl or 'dropload' in sUrl:
                continue
            elif sUrl.startswith('//'):
                sUrl = 'https:' + sUrl
            sName = cParser.urlparse(sUrl).split('.')[0].strip()
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