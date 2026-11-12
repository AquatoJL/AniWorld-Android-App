# -*- coding: utf-8 -*-
# Python 3
# einschalten.in - xStream Site Plugin
# REST-API: /api/movies, /api/movies/{id}, /api/movies/{id}/watch
# Poster: /api/image/poster/PATH  Backdrop: /api/image/backdrop/PATH

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from json import loads

SITE_IDENTIFIER = 'einschalten'
SITE_NAME = 'Einschalten'
SITE_ICON = 'einschalten.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

DOMAIN  = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'einschalten.in')
STATUS  = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE  = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)

URL_MAIN      = 'https://' + DOMAIN
URL_API       = URL_MAIN + '/api/movies'
URL_GENRES    = URL_MAIN + '/api/genres'
URL_SEARCH    = URL_MAIN + '/api/movies?query=%s'
URL_POSTER    = URL_MAIN + '/api/image/poster'
URL_BACKDROP  = URL_MAIN + '/api/image/backdrop'

SCRAPER_SETTINGS = f'''
            <group id="einschalten" label="30705">
                <setting id="plugin_einschalten" type="boolean" label="30050" help="30411">
                    <level>0</level><default>True</default><control type="toggle"/>
                </setting>
                <setting id="global_search_einschalten" type="boolean" label="30052">
                    <level>0</level><default>True</default>
                    <dependencies><dependency type="enable" operator="!is" setting="plugin_einschalten">False</dependency></dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_einschalten_checkDomain" type="boolean" label="30277">
                    <visible>false</visible><default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_einschalten">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_einschalten">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_einschalten.domain" type="string" label="30278" help="">
                    <level>0</level><default>einschalten.in</default>
                    <constraints><allowempty>true</allowempty></constraints>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_einschalten">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_einschalten">false</dependency>
                    </dependencies>
                    <control type="edit" format="string"><heading>30278</heading></control>
                </setting>
                <setting id="plugin_einschalten_status" type="string" label="Dummy" help="">
                    <visible>false</visible><default>true</default><control type="toggle"/>
                </setting>
            </group>
'''


def _request(url, caching=True):
    """Hilfsfunktion: Request mit JSON-Antwort"""
    try:
        oRequest = cRequestHandler(url, ignoreErrors=True)
        if caching and cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 6
        return loads(oRequest.request())
    except Exception:
        return None


def load():
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()

    # Neue Filme
    params.setParam('sUrl', URL_API)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30541), SITE_IDENTIFIER, 'showEntries'), params)
    # Zuletzt hinzugefügt
    params.setParam('sUrl', URL_API + '?order=added')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30549), SITE_IDENTIFIER, 'showEntries'), params)
    # Sammlungen
    params.setParam('sUrl', URL_MAIN + '/api/collections')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30543), SITE_IDENTIFIER, 'showCollections'), params)
    # Genre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre'), params)
    # Suche
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)
    cGui().setEndOfDirectory()


def showGenre():
    params = ParameterHandler()
    aJson = _request(URL_GENRES, caching=True)
    if not aJson:
        cGui().showInfo()
        return
    # Antwort kann direkt eine Liste sein oder {data: [...]}
    genres = aJson if isinstance(aJson, list) else aJson.get('data', [])
    for genre in genres:
        sId   = str(genre.get('id', ''))
        sName = str(genre.get('name', ''))
        if not sId or not sName:
            continue
        params.setParam('sUrl', URL_API + '?genre=' + sId)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')

    # Paginierung
    iPage = params.getValue('page')
    if iPage and str(iPage) != '0':
        sep = '&' if '?' in entryUrl else '?'
        sUrl = entryUrl + sep + 'page=' + str(iPage)
    else:
        sUrl = entryUrl

    aJson = _request(sUrl)
    if not aJson:
        if not sGui: oGui.showInfo()
        return

    aData = aJson.get('data', [])
    if sSearchText:
        aData = [m for m in aData if cParser.search(sSearchText, str(m.get('title', '')))]
    aData = aData[:16]
    total = len(aData)

    for movie in aData:
        sId    = str(movie.get('id', ''))
        sTitle = str(movie.get('title', ''))
        sYear  = str(movie.get('releaseDate', ''))[:4]
        sPoster = movie.get('posterPath', '')
        sThumbnail = (URL_POSTER + sPoster) if sPoster else ''
        sScore = movie.get('voteAverage', 0)

        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showHosters')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if len(sYear) == 4:
            oGuiElement.setYear(sYear)
        if sScore:
            oGuiElement.addItemValue('rating', round(float(sScore), 1))
        oGuiElement.setMediaType('movie')

        params.setParam('entryUrl', sId)
        params.setParam('sName', sTitle)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, False, total)

    if not sGui and not sSearchText:
        pagination = aJson.get('pagination', {})
        if pagination.get('hasMore'):
            curPage = int(pagination.get('currentPage', 1))
            params.setParam('page', curPage + 1)
            params.setParam('sUrl', entryUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('movies')
        oGui.setEndOfDirectory()


def showCollections(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')

    iPage = params.getValue('page')
    if iPage and str(iPage) != '0':
        sep = '&' if '?' in entryUrl else '?'
        sUrl = entryUrl + sep + 'page=' + str(iPage)
    else:
        sUrl = entryUrl

    aJson = _request(sUrl)
    if not aJson:
        if not sGui: oGui.showInfo()
        return

    aData = aJson.get('data', [])
    total = len(aData)

    for col in aData:
        sId     = str(col.get('id', ''))
        sName   = str(col.get('name', ''))
        sPoster = col.get('posterPath', '')
        sThumbnail = (URL_POSTER + sPoster) if sPoster else ''

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showCollectionEntries')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setMediaType('movie')
        params.setParam('entryUrl', sId)
        params.setParam('sName', sName)
        oGui.addFolder(oGuiElement, params, False, total)

    if not sGui:
        pagination = aJson.get('pagination', {})
        if pagination.get('hasMore'):
            curPage = int(pagination.get('currentPage', 1))
            params.setParam('page', curPage + 1)
            params.setParam('sUrl', entryUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showCollections', params)
        oGui.setView('movies')
        oGui.setEndOfDirectory()


def showCollectionEntries(sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    sColId = params.getValue('entryUrl')
    sUrl = URL_MAIN + '/api/collections/' + sColId + '/movies'

    aJson = _request(sUrl)
    if not aJson:
        if not sGui: oGui.showInfo()
        return

    aData = aJson.get('data', [])
    total = len(aData)

    for movie in aData:
        sId    = str(movie.get('id', ''))
        sTitle = str(movie.get('title', ''))
        sYear  = str(movie.get('releaseDate', ''))[:4]
        sPoster = movie.get('posterPath', '')
        sThumbnail = (URL_POSTER + sPoster) if sPoster else ''

        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showHosters')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if len(sYear) == 4:
            oGuiElement.setYear(sYear)
        oGuiElement.setMediaType('movie')
        params.setParam('entryUrl', sId)
        params.setParam('sName', sTitle)
        oGui.addFolder(oGuiElement, params, False, total)

    if not sGui:
        oGui.setView('movies')
        oGui.setEndOfDirectory()


def showHosters():
    hosters = []
    params = ParameterHandler()
    sId = params.getValue('entryUrl')

    # Beschreibung aus Detail-API laden (gecacht)
    try:
        oDetail = cRequestHandler(URL_API + '/' + sId, ignoreErrors=True)
        oDetail.cacheTime = 60 * 60 * 24 * 7
        aDetail = loads(oDetail.request())
        sDesc = aDetail.get('overview', '')
        # Beschreibung wird bereits beim Klick angezeigt — nicht hier verwendet
    except Exception:
        pass

    # Streams laden
    try:
        oWatch = cRequestHandler(URL_API + '/' + sId + '/watch', caching=False)
        aWatch = loads(oWatch.request())
    except Exception:
        return hosters

    # Antwort kann direkt ein Objekt oder eine Liste sein
    if isinstance(aWatch, dict):
        streams = [aWatch] if aWatch.get('streamUrl') else aWatch.get('streams', [])
    elif isinstance(aWatch, list):
        streams = aWatch
    else:
        streams = []

    i = 0
    for stream in streams:
        sUrl = stream.get('streamUrl', '') if isinstance(stream, dict) else str(stream)
        if not sUrl:
            continue
        if sUrl.startswith('//'):
            sUrl = 'https:' + sUrl
        isMatch, aName = cParser.parse(sUrl, r'//([^/]+)/')
        sName = aName[0][:aName[0].rindex('.')] if isMatch and '.' in aName[0] else str(i)
        if cConfig().isBlockedHoster(sName)[0]:
            continue
        sQuality = stream.get('quality', '720') if isinstance(stream, dict) else '720'
        hosters.append({
            'link': sUrl,
            'name': '%d: %s' % (i, sName),
            'displayedName': '%s [I][%sp][/I]' % (sName, sQuality),
            'quality': sQuality
        })
        i += 1

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
