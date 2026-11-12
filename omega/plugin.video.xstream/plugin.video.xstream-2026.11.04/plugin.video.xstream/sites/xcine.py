# -*- coding: utf-8 -*-
# Python 3
# xCine.ru - xStream Site Plugin
# API: /data/browse/ + /data/watch/ (gleiche Struktur wie movie2k / kinokiste)

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from json import loads

SITE_IDENTIFIER = 'xcine'
SITE_NAME = 'xCine'
SITE_ICON = 'xcinetop.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

DOMAIN  = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'xcine.hair')
STATUS  = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE  = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)

ORIGIN  = 'https://' + DOMAIN
REFERER = ORIGIN + '/'

URL_MAIN      = ORIGIN + '/data/browse/?lang=%s&type=%s&order_by=%s&page=%s'
URL_GENRE     = ORIGIN + '/data/browse/?lang=%s&type=%s&order_by=releases&genre=%s&page=%s'
URL_YEAR      = ORIGIN + '/data/browse/?lang=%s&type=%s&order_by=releases&year=%s&page=%s'
URL_SEARCH    = ORIGIN + '/data/browse/?lang=%s&keyword=%s&page=%s'
URL_WATCH     = ORIGIN + '/data/watch/?_id=%s'
URL_THUMBNAIL = 'https://image.tmdb.org/t/p/w300%s'

SCRAPER_SETTINGS = f'''
            <group id="plugin_xcine" label="30716">
                <setting id="plugin_xcine" type="boolean" label="30050" help="30411">
                    <level>0</level><default>True</default><control type="toggle"/>
                </setting>
                <setting id="global_search_xcine" type="boolean" label="30052">
                    <level>0</level><default>True</default>
                    <dependencies><dependency type="enable" operator="!is" setting="plugin_xcine">False</dependency></dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_xcine_checkDomain" type="boolean" label="30277">
                    <visible>false</visible><default>False</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_xcine">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_xcine">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_xcine.domain" type="string" label="30278" help="">
                    <level>0</level><default>xcine.ru</default>
                    <constraints><allowempty>true</allowempty></constraints>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_xcine">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_xcine">false</dependency>
                    </dependencies>
                    <control type="edit" format="string"><heading>30278</heading></control>
                </setting>
                <setting id="plugin_xcine_status" type="string" label="Dummy" help="">
                    <visible>false</visible><default>true</default><control type="toggle"/>
                </setting>
            </group>
'''


def _getQuality(sQuality):
    isMatch, aResult = cParser.parse(str(sQuality), '(4K|HDCAM|HD|WEB|BLUERAY|BRRIP|DVD|TS|SD|CAM)', 1, True)
    return aResult[0] if isMatch else sQuality


def _getLang():
    sLanguage = cConfig().getSetting('prefLanguage')
    if sLanguage == '1':   return '2'
    elif sLanguage == '2': return '3'
    return 'all'


def load():
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    sLang = _getLang()
    params.setParam('sLanguage', sLang)

    # --- Hauptmenü ---
    # Im Kino (aktuell im Kino / nach Erscheinungsdatum)
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'releases', '1'))
    cGui().addFolder(cGuiElement('Im Kino', SITE_IDENTIFIER, 'showEntries'), params)
    # Derzeit Beliebt (meistgesehene gesamt)
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'views', '1'))
    cGui().addFolder(cGuiElement('Derzeit Beliebt', SITE_IDENTIFIER, 'showEntries'), params)
    # Neu hinzugefügt
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'new', '1'))
    cGui().addFolder(cGuiElement('Neu', SITE_IDENTIFIER, 'showEntries'), params)
    # Meist gesehen (alias views – gleicher Endpunkt, klarer Name)
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'views', '1'))
    cGui().addFolder(cGuiElement('Meist gesehen', SITE_IDENTIFIER, 'showEntries'), params)
    # Top bewertet (nach Rating)
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'rating', '1'))
    cGui().addFolder(cGuiElement('Top IMDB', SITE_IDENTIFIER, 'showEntries'), params)
    # Filme-Untermenü
    cGui().addFolder(cGuiElement('Filme', SITE_IDENTIFIER, 'showMovieMenu'), params)
    # Serien-Untermenü
    cGui().addFolder(cGuiElement('Serien', SITE_IDENTIFIER, 'showSeriesMenu'), params)
    # Suche
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)
    cGui().setEndOfDirectory()


def showMovieMenu():
    """Untermenü: Filme"""
    params = ParameterHandler()
    sLang = params.getValue('sLanguage') or _getLang()
    params.setParam('sLanguage', sLang)
    params.setParam('sType', 'movies')

    # Neu
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'new', '1'))
    cGui().addFolder(cGuiElement('Neu', SITE_IDENTIFIER, 'showEntries'), params)
    # Im Kino
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'releases', '1'))
    cGui().addFolder(cGuiElement('Im Kino', SITE_IDENTIFIER, 'showEntries'), params)
    # Beliebt
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'views', '1'))
    cGui().addFolder(cGuiElement('Beliebt', SITE_IDENTIFIER, 'showEntries'), params)
    # Top bewertet
    params.setParam('sUrl', URL_MAIN % (sLang, 'movies', 'rating', '1'))
    cGui().addFolder(cGuiElement('Top bewertet', SITE_IDENTIFIER, 'showEntries'), params)
    # Nach Genre
    cGui().addFolder(cGuiElement('Nach Genre', SITE_IDENTIFIER, 'showMovieGenre'), params)
    # Nach Jahr
    cGui().addFolder(cGuiElement('Nach Jahr', SITE_IDENTIFIER, 'showMovieYears'), params)
    cGui().setEndOfDirectory()


def showSeriesMenu():
    """Untermenü: Serien"""
    params = ParameterHandler()
    sLang = params.getValue('sLanguage') or _getLang()
    params.setParam('sLanguage', sLang)
    params.setParam('sType', 'tvseries')

    # Neue Serien
    params.setParam('sUrl', URL_MAIN % (sLang, 'tvseries', 'new', '1'))
    cGui().addFolder(cGuiElement('Neue Serien', SITE_IDENTIFIER, 'showEntries'), params)
    # Beliebt
    params.setParam('sUrl', URL_MAIN % (sLang, 'tvseries', 'views', '1'))
    cGui().addFolder(cGuiElement('Beliebt', SITE_IDENTIFIER, 'showEntries'), params)
    # Top bewertet
    params.setParam('sUrl', URL_MAIN % (sLang, 'tvseries', 'rating', '1'))
    cGui().addFolder(cGuiElement('Top bewertet', SITE_IDENTIFIER, 'showEntries'), params)
    # Nach Genre
    cGui().addFolder(cGuiElement('Nach Genre', SITE_IDENTIFIER, 'showSeriesGenre'), params)
    # Nach Jahr
    cGui().addFolder(cGuiElement('Nach Jahr', SITE_IDENTIFIER, 'showSeriesYears'), params)
    cGui().setEndOfDirectory()


def showMovieGenre():
    """Genre-Untermenü für Filme"""
    params = ParameterHandler()
    sLang = params.getValue('sLanguage') or _getLang()
    for sName, sSlug in [
        ('Action',          'Action'),
        ('Abenteuer',       'Adventure'),
        ('Animation',       'Animation'),
        ('Biografie',       'Biography'),
        ('Dokumentation',   'Documentary'),
        ('Drama',           'Drama'),
        ('Familie',         'Family'),
        ('Fantasy',         'Fantasy'),
        ('Geschichte',      'History'),
        ('Horror',          'Horror'),
        ('Komödie',         'Comedy'),
        ('Krimi',           'Crime'),
        ('Musik',           'Music'),
        ('Musical',         'Musical'),
        ('Mystery',         'Mystery'),
        ('Romance',         'Romance'),
        ('Science Fiction', 'Sci-Fi'),
        ('Sport',           'Sport'),
        ('Thriller',        'Thriller'),
        ('War',             'War'),
        ('Western',         'Western'),
    ]:
        params.setParam('sUrl', URL_GENRE % (sLang, 'movies', cParser.quotePlus(sSlug), '1'))
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showSeriesGenre():
    """Genre-Untermenü für Serien"""
    params = ParameterHandler()
    sLang = params.getValue('sLanguage') or _getLang()
    for sName, sSlug in [
        ('Action',          'Action'),
        ('Abenteuer',       'Adventure'),
        ('Animation',       'Animation'),
        ('Drama',           'Drama'),
        ('Familie',         'Family'),
        ('Fantasy',         'Fantasy'),
        ('Horror',          'Horror'),
        ('Komödie',         'Comedy'),
        ('Krimi',           'Crime'),
        ('Mystery',         'Mystery'),
        ('Reality',         'Reality'),
        ('Romance',         'Romance'),
        ('Sci-Fi & Fantasy','Sci-Fi'),
        ('Thriller',        'Thriller'),
        ('Western',         'Western'),
    ]:
        params.setParam('sUrl', URL_GENRE % (sLang, 'tvseries', cParser.quotePlus(sSlug), '1'))
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showMovieYears():
    """Jahr-Untermenü für Filme"""
    params = ParameterHandler()
    sLang = params.getValue('sLanguage') or _getLang()
    import datetime
    for year in range(datetime.datetime.now().year, 1979, -1):
        params.setParam('sUrl', URL_YEAR % (sLang, 'movies', year, '1'))
        cGui().addFolder(cGuiElement(str(year), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showSeriesYears():
    """Jahr-Untermenü für Serien"""
    params = ParameterHandler()
    sLang = params.getValue('sLanguage') or _getLang()
    import datetime
    for year in range(datetime.datetime.now().year, 1979, -1):
        params.setParam('sUrl', URL_YEAR % (sLang, 'tvseries', year, '1'))
        cGui().addFolder(cGuiElement(str(year), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    sLanguage = params.getValue('sLanguage') or _getLang()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')

    try:
        oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
        if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 6
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        oRequest.addHeaderEntry('Accept', 'application/json, text/plain, */*')
        oRequest.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
        aJson = loads(oRequest.request())
    except Exception:
        if not sGui: oGui.showInfo()
        return

    if 'movies' not in aJson or not isinstance(aJson.get('movies'), list) or not aJson['movies']:
        if not sGui: oGui.showInfo()
        return

    # 16-Limit mit Suchtextfilter davor
    aMovies = [m for m in aJson['movies'] if '_id' in m]
    if sSearchText:
        aMovies = [m for m in aMovies if cParser.search(sSearchText, str(m.get('title', '')))]
    aMovies = aMovies[:16]
    total = len(aMovies)

    for movie in aMovies:
        sTitle = str(movie['title'])
        if 'Staffel' in sTitle or 'Season' in sTitle:
            isTvshow = True

        # Poster / Fanart
        sThumbnail = ''
        if movie.get('poster_path_season'):
            sThumbnail = URL_THUMBNAIL % str(movie['poster_path_season'])
        elif movie.get('poster_path'):
            sThumbnail = URL_THUMBNAIL % str(movie['poster_path'])
        elif movie.get('backdrop_path'):
            sThumbnail = URL_THUMBNAIL % str(movie['backdrop_path'])
        sFanart = (URL_THUMBNAIL % str(movie['backdrop_path'])) if movie.get('backdrop_path') else sThumbnail

        # Titelformat: Name - (Jahr) [Qualität]
        sYear    = str(movie['year'])    if movie.get('year')    else ''
        sQuality = str(movie['quality']) if movie.get('quality') else ''
        sDisplayTitle = sTitle.strip()
        if len(sYear) == 4:
            sDisplayTitle += ' - (%s)' % sYear
        if sQuality.strip():
            sDisplayTitle += ' [%s]' % _getQuality(sQuality)

        oGuiElement = cGuiElement(sDisplayTitle, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
            oGuiElement.setFanart(sFanart)
        if len(sYear) == 4:
            oGuiElement.setYear(sYear)
        if sQuality:
            oGuiElement.setQuality(_getQuality(sQuality))
        if movie.get('rating'):
            oGuiElement.addItemValue('rating', movie['rating'])
        if movie.get('lang'):
            if sLanguage != '1' and movie['lang'] == 2:
                oGuiElement.setLanguage('DE')
            if sLanguage != '2' and movie['lang'] == 3:
                oGuiElement.setLanguage('EN')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if movie.get('runtime'):
            isMatch, sRuntime = cParser.parseSingleResult(str(movie['runtime']), r'\d+')
            if isMatch:
                oGuiElement.addItemValue('duration', sRuntime)

        # Beschreibung via Watch-API (gecacht 7 Tage)
        try:
            oDetailReq = cRequestHandler(URL_WATCH % str(movie['_id']), ignoreErrors=True)
            oDetailReq.cacheTime = 60 * 60 * 24 * 7
            oDetailReq.addHeaderEntry('Referer', REFERER)
            oDetailReq.addHeaderEntry('Origin', ORIGIN)
            oDetailReq.addHeaderEntry('Accept', 'application/json, text/plain, */*')
            oDetailReq.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
            aDetail = loads(oDetailReq.request())
            aM = aDetail if isinstance(aDetail, dict) else {}
            if isinstance(aM.get('movie'), dict):
                aM = aM['movie']
            elif isinstance(aM.get('movies'), list) and aM['movies']:
                aM = aM['movies'][0]
            sDesc = (aM.get('storyline') or aM.get('overview') or
                     aM.get('description') or movie.get('storyline') or
                     movie.get('overview') or '')
            if sDesc:
                oGuiElement.setDescription(str(sDesc).strip())
        except Exception:
            sDesc = movie.get('storyline') or movie.get('overview') or ''
            if sDesc:
                oGuiElement.setDescription(str(sDesc))

        params.setParam('entryUrl', URL_WATCH % str(movie['_id']))
        params.setParam('sName', sTitle)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    if not sGui and not sSearchText:
        try:
            curPage = aJson['pager']['currentPage']
            if curPage < aJson['pager']['totalPages']:
                import re as _re
                sNextUrl = _re.sub(r'page=\d+', 'page=%d' % (curPage + 1), entryUrl)
                params.setParam('sUrl', sNextUrl)
                oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        except Exception:
            pass
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    sName = params.getValue('sName')
    try:
        oRequest = cRequestHandler(sUrl, ignoreErrors=True)
        oRequest.cacheTime = 60 * 60 * 4
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        oRequest.addHeaderEntry('Accept', 'application/json, text/plain, */*')
        oRequest.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
        aJson = loads(oRequest.request())
    except Exception:
        cGui().showInfo()
        return

    if 'streams' not in aJson or not aJson['streams']:
        cGui().showInfo()
        return

    aEpisodes = sorted(set(int(s['e']) for s in aJson['streams'] if 'e' in s))
    total = len(aEpisodes)
    for sEpisode in aEpisodes:
        oGuiElement = cGuiElement('Episode ' + str(sEpisode), SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setTVShowTitle(sName)
        oGuiElement.setEpisode(sEpisode)
        oGuiElement.setMediaType('episode')
        params.setParam('episode', str(sEpisode))
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sEpisode = params.getValue('episode')
    try:
        oRequest = cRequestHandler(sUrl, caching=False)
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        oRequest.addHeaderEntry('Accept', 'application/json, text/plain, */*')
        oRequest.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
        aJson = loads(oRequest.request())
    except Exception:
        return hosters

    if 'streams' not in aJson:
        return hosters

    i = 0
    for stream in aJson['streams']:
        if sEpisode and 'e' in stream and str(stream['e']) != str(sEpisode):
            continue
        sStreamUrl = stream.get('stream', '')
        if not sStreamUrl:
            continue
        if sStreamUrl.startswith('//'):
            sStreamUrl = 'https:' + sStreamUrl
        isMatch, aName = cParser.parse(sStreamUrl, r'//([^/]+)/')
        sName = aName[0][:aName[0].rindex('.')] if isMatch else str(i)
        if cConfig().isBlockedHoster(sName)[0]:
            continue
        sRelease = stream.get('release', '')
        sQuality = _getQuality(sRelease) if sRelease else 'HD'
        hosters.append({'link': sStreamUrl, 'name': '%d: %s' % (i, sName),
                        'displayedName': '%s [I][%s][/I]' % (sName, sQuality), 'quality': sQuality})
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
    params = ParameterHandler()
    sLang = params.getValue('sLanguage') or _getLang()
    showEntries(URL_SEARCH % (sLang, cParser.quotePlus(sSearchText), '1'), oGui, sSearchText)
