# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showEntries:    6 Stunden
# showSeasons:    6 Stunden
# showEpisodes:   4 Stunden
# Seite vollständig mit JSON erstellt


import json

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

def _safe_json_response(request):
    """Gracefully handle blocked, empty or invalid MOFLIX API responses."""
    try:
        payload = request.request()
        if not payload or not str(payload).strip():
            logger.info('[MOFLIX] API-Antwort leer oder blockiert; keine JSON-Daten')
            return None
        return json.loads(payload)
    except (ValueError, TypeError) as exc:
        logger.info('[MOFLIX] Ungueltige API-JSON-Antwort: %s' % exc)
        return None
    except Exception as exc:
        logger.info('[MOFLIX] API-Abfrage fehlgeschlagen: %s' % exc)
        return None


SITE_IDENTIFIER = 'moflix-stream'
SITE_NAME = 'Moflix-Stream'
SITE_ICON = 'moflix-stream.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'moflix-stream.xyz') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN + '/'
# URL_MAIN = 'https://moflix-stream.xyz/'
# Search Links
URL_SEARCH = URL_MAIN + 'api/v1/search/%s?query=%s&limit=8'
# Genre
URL_VALUE = URL_MAIN + 'api/v1/channel/%s?channelType=channel&restriction=&paginate=simple'
# Hoster
URL_HOSTER = URL_MAIN + 'api/v1/titles/%s?load=images,genres,productionCountries,keywords,videos,primaryVideo,seasons,compactCredits'

SCRAPER_SETTINGS = f'''
            <group id="plugin_moflix-stream" label="30728">
                <setting id="plugin_moflix-stream" type="boolean" label="30050" help="30411">
                    <level>0</level>
                    <default>True</default>
                    <control type="toggle"/>
                </setting>
                <setting id="global_search_moflix-stream" type="boolean" label="30052">
                    <level>0</level>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_moflix-stream">False</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <!-- Domain Überprüfung mit automatischer und manueller Anpassung -->
                <setting id="plugin_moflix-stream_checkDomain" type="boolean" label="30277">
                    <visible>false</visible>
                    <default>True</default>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_moflix-stream">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_moflix-stream">false</dependency>
                    </dependencies>
                    <control type="toggle"/>
                </setting>
                <setting id="plugin_moflix-stream.domain" type="string" label="30278" help="">
                    <level>0</level>
                    <default>moflix-stream.xyz</default>
                    <constraints>
                        <allowempty>true</allowempty>
                    </constraints>
                    <dependencies>
                        <dependency type="enable" operator="!is" setting="plugin_moflix-stream">false</dependency>
                        <dependency type="visible" operator="!is" setting="plugin_moflix-stream">false</dependency>
                    </dependencies>
                    <control type="edit" format="string">
                        <heading>30278</heading>
                    </control>
                </setting>
                <setting id="plugin_moflix-stream_status" type="string" label="Dummy" help="">
                    <visible>false</visible>
                    <default>true</default>
                    <control type="toggle"/>
                </setting>
            </group>
'''


def _apply_movie_metadata(element, item):
    """Pass through available MOFLIX metadata to Kodi without fabricating values."""
    release = str(item.get('release_date') or item.get('year') or '')
    year = release[:4]
    if len(year) == 4 and year.isdigit() and 1880 <= int(year) <= 2100:
        element.setYear(year)

    raw_genres = item.get('genres') or item.get('genre') or []
    if isinstance(raw_genres, str):
        genres = [part.strip() for part in raw_genres.split(',') if part.strip()]
    elif isinstance(raw_genres, list):
        genres = []
        for genre in raw_genres:
            if isinstance(genre, dict):
                label = genre.get('display_name') or genre.get('name') or genre.get('title')
            elif isinstance(genre, str):
                label = genre
            else:
                label = None
            if label and str(label).strip():
                genres.append(str(label).strip())
    else:
        genres = []
    if genres:
        element.addItemValue('genre', ' / '.join(dict.fromkeys(genres)))

    rating = item.get('rating')
    if isinstance(rating, dict):
        rating = rating.get('value') or rating.get('average')
    try:
        rating = float(rating)
        if 0 <= rating <= 10:
            element.addItemValue('rating', rating)
    except (ValueError, TypeError):
        pass

def load():
    logger.info("Load %s" % SITE_NAME)
    menu = [
        ('Suche', 'showSearch', None),
        ('Filme', 'showEntries', 'movies'),
        ('Top Filme', 'showEntries', 'top-rated-movies'),
        ('Neues', 'showEntries', 'now-playing'),
        ('Serien', 'showEntries', 'series'),
        ('Kollektionen', 'showCollections', None),
        ('Genres', 'showGenres', None),
        ('Erscheinungsjahr', 'showReleaseYears', None),
    ]
    gui = cGui()
    for title, function, channel in menu:
        params = ParameterHandler()
        if channel:
            params.setParam('sUrl', URL_VALUE % channel)
            params.setParam('page', 1)
        gui.addFolder(cGuiElement(title, SITE_IDENTIFIER, function), params)
    gui.setEndOfDirectory()


_GENRES = ('Action', 'Abenteuer', 'Animation', 'Komödie', 'Krimi', 'Dokumentation',
           'Drama', 'Familie', 'Fantasy', 'Historie', 'Horror', 'Musik',
           'Mystery', 'Romantik', 'Science-Fiction', 'Thriller', 'Kriegsfilm', 'Western')


def showGenres():
    gui = cGui()
    for genre in _GENRES:
        params = ParameterHandler()
        params.setParam('filterGenre', genre)
        gui.addFolder(cGuiElement(genre, SITE_IDENTIFIER, 'showFilteredEntries'), params)
    gui.setEndOfDirectory()


def showReleaseYears():
    from datetime import datetime
    gui = cGui()
    for year in range(datetime.now().year, 1979, -1):
        params = ParameterHandler()
        params.setParam('filterYear', str(year))
        gui.addFolder(cGuiElement(str(year), SITE_IDENTIFIER, 'showFilteredEntries'), params)
    gui.setEndOfDirectory()


def _item_year(item):
    import re
    value = str(item.get('release_date') or item.get('year') or '')
    match = re.search(r'(?:19|20)\d{2}', value)
    return match.group(0) if match else ''


def _display_title(item):
    title = str(item.get('name') or '')
    year = _item_year(item)
    return title + ' - (' + year + ')' if year else title


def _genre_names(item):
    raw = item.get('genres') or item.get('genre') or []
    if isinstance(raw, str):
        return [v.strip() for v in raw.split(',') if v.strip()]
    if isinstance(raw, dict):
        raw = raw.get('data') or []
    if not isinstance(raw, list):
        return []
    return [str(v.get('display_name') or v.get('name') or v.get('title') or '') if isinstance(v, dict) else str(v)
            for v in raw]


def showFilteredEntries():
    params = ParameterHandler()
    year = params.getValue('filterYear')
    genre = params.getValue('filterGenre')
    import unicodedata
    def normalize(value):
        return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).casefold() if c.isalnum())
    results = []
    seen = set()
    # Search the accessible catalog, without using the Cloudflare-blocked search endpoint.
    for channel in ('movies', 'top-rated-movies', 'now-playing'):
        for page in range(1, 9):
            request = cRequestHandler((URL_VALUE % channel) + '&page=' + str(page), ignoreErrors=True)
            request.addHeaderEntry('Referer', URL_MAIN)
            request.cacheTime = 60 * 60
            payload = _safe_json_response(request)
            data = ((payload.get('channel') or {}).get('content') or {}).get('data') or [] if isinstance(payload, dict) else []
            if not isinstance(data, list) or not data:
                break
            for item in data:
                if not isinstance(item, dict) or item.get('is_series'):
                    continue
                if year and _item_year(item) != year:
                    continue
                if genre and normalize(genre) not in [normalize(g) for g in _genre_names(item)]:
                    continue
                key = str(item.get('id') or '')
                if key and key not in seen:
                    seen.add(key)
                    results.append(item)
    # Use saved public collection items when no catalog data can be matched.
    if not results:
        for collection in _collection_snapshot().values():
            for item in collection.get('items') or []:
                if not isinstance(item, dict) or item.get('is_series'):
                    continue
                if year and _item_year(item) != year:
                    continue
                if genre and normalize(genre) not in [normalize(g) for g in _genre_names(item)]:
                    continue
                key = str(item.get('id') or '')
                if key and key not in seen:
                    seen.add(key)
                    results.append(item)
    showSearchEntries('__moflix_collection__', False, '', collectionResults=results)


def _collection_snapshot():
    """First items of public MOFLIX collections, captured from the supplied HTML."""
    import os
    try:
        path = os.path.join(cConfig().getAddonInfo('path'), 'resources', 'data', 'moflix_collections.json')
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception as exc:
        logger.info('[MOFLIX] Kollektionen-Snapshot nicht lesbar: %s' % exc)
        return {}


def showCollections():
    snapshot = _collection_snapshot()
    gui = cGui()
    for slug, collection in snapshot.items():
        params = ParameterHandler()
        params.setParam('sUrl', URL_VALUE % slug)
        gui.addFolder(cGuiElement(collection['name'], SITE_IDENTIFIER, 'showCollectionEntries'), params)
    gui.setEndOfDirectory()


def showCollectionEntries():
    import re
    url = ParameterHandler().getValue('sUrl')
    match = re.search(r'/channel/([^?&/]+)', url or '')
    slug = match.group(1) if match else ''
    collection = _collection_snapshot().get(slug) or {}
    # Prefer the complete live collection when its endpoint is accessible.
    request = cRequestHandler(URL_VALUE % slug + '&page=1', ignoreErrors=True)
    request.addHeaderEntry('Referer', URL_MAIN)
    request.cacheTime = 60 * 60
    payload = _safe_json_response(request)
    channel = (payload.get('channel') or {}) if isinstance(payload, dict) else {}
    content = channel.get('content') or {}
    results = content.get('data') or []
    if not isinstance(results, list):
        results = []
    if not results:
        results = collection.get('items') or []
        logger.info('[MOFLIX] Kollektion %s: %d gesicherte Eintraege aus Webseiten-Daten (von %s)' %
                    (slug, len(results), collection.get('total', '?')))
    else:
        logger.info('[MOFLIX] Kollektion %s: %d Live-Eintraege' % (slug, len(results)))
    showSearchEntries('__moflix_collection__', False, '', collectionResults=results)


def showEntries(entryUrl=False, sGui=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    # Parameter laden
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    iPage = int(params.getValue('page'))
    oRequest = cRequestHandler(entryUrl + '&page=' + str(iPage) if iPage > 0 else entryUrl, ignoreErrors=(sGui is not False))
    oRequest.addHeaderEntry('Referer', params.getValue('sUrl'))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    jSearch = _safe_json_response(oRequest)  # Lade JSON aus dem Request der URL
    if not jSearch: return  # Wenn Suche erfolglos - Abbruch
    aResults = jSearch.get('channel', {}).get('content', {}).get('data', [])
    total = len(aResults)
    if len(aResults) == 0:
        if not sGui: oGui.showInfo()
        return
    isTvshow = False
    for i in aResults:
        sId = str(i['id'])  # ID des Films / Serie für die weitere URL
        sName = str(i['name'])  # Name des Films / Serie
        displayName = _display_title(i)
        if 'is_series' in i: isTvshow = i['is_series']  # Wenn True dann Serie
        oGuiElement = cGuiElement(displayName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        _apply_movie_metadata(oGuiElement, i)
        # sDesc = i['description']
        if 'description' in i and i['description'] != '':
            oGuiElement.setDescription(str(i['description']))  # Suche nach Desc wenn nicht leer dann setze GuiElement
        # sThumbnail = i['poster']
        if 'poster' in i and i['poster'] != '':
            oGuiElement.setThumbnail(str(i['poster']))  # Suche nach Poster wenn nicht leer dann setze GuiElement
        # sFanart = i['backdrop']
        if 'backdrop' in i and i['backdrop'] != '':
            oGuiElement.setFanart(str(i['backdrop']))  # Suche nach Fanart wenn nicht leer dann setze GuiElement
        if 'runtime' in i and i['runtime'] != None:
            oGuiElement.addItemValue('duration', str(i['runtime']))  # Suche nach Runtime wenn nicht leer dann setze GuiElement
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        # Parameter übergeben
        params.setParam('entryUrl', URL_HOSTER % sId)
        params.setParam('sThumbnail', i.get('poster') or '')
        params.setParam('sName', sName)
        params.setParam('seasonPage', 1)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui:
        sPageNr = int(params.getValue('page'))
        if sPageNr == 0:
            sPageNr = 2
        else:
            sPageNr += 1
        params.setParam('page', int(sPageNr))
        oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showSeasons(sGui=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    # Parameter laden
    # https://moflix-stream.xyz/api/v1/titles/dG1kYnxzZXJpZXN8NzE5MTI=?load=images,genres,productionCountries,keywords,videos,primaryVideo,seasons,compactCredits
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    iPage = int(params.getValue('seasonPage'))
    oRequest = cRequestHandler(entryUrl + '&page=' + str(iPage) if iPage > 0 else entryUrl)
    oRequest.addHeaderEntry('Referer', entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    jSearch = _safe_json_response(oRequest) # Lade JSON aus dem Request der URL
    if not jSearch: return  # Wenn Suche erfolglos - Abbruch
    sDesc = jSearch.get('title', {}).get('description', '') # Lade Beschreibung aus JSON
    aResults = jSearch.get('seasons', {}).get('data', [])
    aResults = sorted(aResults, key=lambda k: k['number'])  # Sortiert die Staffeln nach Nummer aufsteigend
    total = len(aResults)
    if len(aResults) == 0:
        if not sGui: oGui.showInfo()
        return
    for i in aResults:
        sId = str(i['title_id']) # ID ändert sich !!!
        sSeasonNr = str(i['number']) # Staffel Nummer
        oGuiElement = cGuiElement('Staffel ' + sSeasonNr, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setSeason(sSeasonNr)
        oGuiElement.setThumbnail(sThumbnail)
        if sDesc != '':
            oGuiElement.setDescription(str(sDesc))
        params.setParam('sSeasonNr', sSeasonNr)
        params.setParam('sId', sId)
        cGui().addFolder(oGuiElement, params, True, total)
    # wenn es mehr als 8 Staffeln gibt, dann werden die ersten Staffeln nicht auf der ersten Seite angezeigt
    if aResults[0]['number'] > 1:
        iPage = int(params.getValue('seasonPage'))
        iPage += 1
        params.setParam('seasonPage', iPage)
        cGui().addNextPage(SITE_IDENTIFIER, 'showSeasons', params)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes(sGui=False):
    oGui = cGui()
    params = ParameterHandler()
    # Parameter laden
    sId = params.getValue('sId')
    sSeasonNr = params.getValue('sSeasonNr')
    sUrl = URL_MAIN + 'api/v1/titles/%s/seasons/%s/episodes?perPage=100&query=&page=1' % (sId, sSeasonNr) #Hep 02.12.23: Abfrage für einzelne Episoden per query force auf 100 erhöht
    oRequest = cRequestHandler(sUrl)
    oRequest.addHeaderEntry('Referer', sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4  # 4 Stunden
    jSearch = _safe_json_response(oRequest) # Lade JSON aus dem Request der URL
    if not jSearch: return  # Wenn Suche erfolglos - Abbruch
    #aResults = jSearch['episodes']['data'] # Ausgabe der Suchresultate von jSearch
    aResults = jSearch.get('pagination', {}).get('data', [])  # Ausgabe der Suchresultate von jSearch
    total = len(aResults) # Anzahl aller Ergebnisse
    if len(aResults) == 0:
        if not sGui: oGui.showInfo()
        return
    for i in aResults:
        if 'primary_video' in i and i['primary_video'] == None: continue # no video available (skip this entry)
        sName = str(i['name']) # Episoden Titel
        sEpisodeNr = str(i['episode_number']) # Episoden Nummer
        sThumbnail = str(i['poster']) # Episoden Poster
        oGuiElement = cGuiElement('Episode ' + sEpisodeNr + ' - ' + sName, SITE_IDENTIFIER, 'showHosters')
        if 'description' in i and i['description'] != '': oGuiElement.setDescription(i['description']) # Suche nach Desc wenn nicht leer dann setze GuiElement
        oGuiElement.setEpisode(sEpisodeNr)
        oGuiElement.setSeason(sSeasonNr)
        oGuiElement.setMediaType('episode')
        oGuiElement.setThumbnail(sThumbnail)
        if 'runtime' in i and i['runtime'] != None:
            oGuiElement.addItemValue('duration', str(i['runtime']))  # Suche nach Runtime wenn nicht leer dann setze GuiElement
        # Parameter setzen
        params.setParam('entryUrl', URL_MAIN + 'api/v1/titles/%s/seasons/%s/episodes/%s?load=videos,compactCredits,primaryVideo' % (sId, sSeasonNr, sEpisodeNr))
        oGui.addFolder(oGuiElement, params, False, total)
    oGui.setView('episodes')
    oGui.setEndOfDirectory()


def _catalog_search(sSearchText):
    """Search reachable MOFLIX channels when the search endpoint is blocked."""
    import re
    import unicodedata

    def normalize(value):
        value = unicodedata.normalize('NFKD', str(value or '')).casefold()
        return ''.join(ch for ch in value if ch.isalnum())

    wanted = normalize(sSearchText)
    if not wanted:
        return []
    found = []
    seen = set()
    for channel in ('now-playing', 'movies', 'top-rated-movies', 'series'):
        for page in range(1, 5):
            url = (URL_VALUE % channel) + '&page=' + str(page)
            request = cRequestHandler(url, ignoreErrors=True)
            request.addHeaderEntry('Referer', URL_MAIN)
            request.cacheTime = 60 * 60
            payload = _safe_json_response(request)
            if not isinstance(payload, dict):
                break
            entries = (payload.get('channel') or {}).get('content') or {}
            entries = entries.get('data') or []
            if not isinstance(entries, list) or not entries:
                break
            for item in entries:
                if not isinstance(item, dict):
                    continue
                title = normalize(item.get('name'))
                item_id = item.get('id')
                if item_id and wanted in title and str(item_id) not in seen:
                    seen.add(str(item_id))
                    found.append(item)
            if len(found) >= 40:
                return found
    return found


def showSearchEntries(entryUrl=False, sGui=False, sSearchText='', collectionResults=None):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    # Parameter laden
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = None if entryUrl in ('__moflix_catalog__', '__moflix_collection__') else cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if oRequest is not None: oRequest.addHeaderEntry('Referer', entryUrl)
    # Direct search uses the reachable catalog first to avoid Cloudflare on /search/.
    # Global search can still use the API and falls back on blocked/empty responses.
    if entryUrl == '__moflix_collection__':
        aResults = collectionResults or []
    elif entryUrl == '__moflix_catalog__':
        aResults = _catalog_search(sSearchText)
    else:
        jSearch = _safe_json_response(oRequest)
        aResults = jSearch.get('results', []) if isinstance(jSearch, dict) else []
        if not aResults and sSearchText:
            aResults = _catalog_search(sSearchText)
    # Ausgabe der Suchresultate von jSearch
    total = len(aResults) # Anzahl aller Ergebnisse
    if len(aResults) == 0: # Wenn Resultate 0 zeige Benachrichtigung
        if not sGui: oGui.showInfo()
        return
    isTvshow = False
    for i in aResults:
        if 'person' in str(i.get('model_type', '')): continue # Personen in der Suche ausblenden
        sId = str(i['id'])   # ID des Films / Serie für die weitere URL
        sName = str(i['name']) # Name des Films / Serie
        displayName = _display_title(i)
        sYear = str(i.get('release_date') or '').split('-')[0].strip()
        if sSearchText and ''.join(c for c in sSearchText.casefold() if c.isalnum()) not in ''.join(c for c in sName.casefold() if c.isalnum()): continue
        if 'is_series' in i: isTvshow = i['is_series'] # Wenn True dann Serie
        oGuiElement = cGuiElement(displayName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        _apply_movie_metadata(oGuiElement, i)
        #sDesc = i['description']
        if 'description' in i and i['description'] != '':
            oGuiElement.setDescription(str(i['description'])) # Suche nach Desc wenn nicht leer dann setze GuiElement
        # sThumbnail = i['poster']
        if 'poster' in i and i['poster'] != '':
            oGuiElement.setThumbnail(str(i['poster'])) # Suche nach Poster wenn nicht leer dann setze GuiElement
        # sFanart = i['backdrop']
        if 'backdrop' in i and i['backdrop'] != '':
            oGuiElement.setFanart(str(i['backdrop'])) # Suche nach Fanart wenn nicht leer dann setze GuiElement
        if 'runtime' in i and i['runtime'] != None:
            oGuiElement.addItemValue('duration', str(i['runtime']))  # Suche nach Runtime wenn nicht leer dann setze GuiElement
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        # Parameter setzen
        params.setParam('entryUrl', URL_HOSTER % sId)
        params.setParam('sThumbnail', i.get('poster') or '')
        params.setParam('sName', sName)
        params.setParam('seasonPage', 1)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui:
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showHosters(sGui=False):
    oGui = sGui if sGui else cGui()
    hosters = []
    sUrl = ParameterHandler().getValue('entryUrl')
    oRequest = cRequestHandler(sUrl, caching=False)
    oRequest.addHeaderEntry('Referer', sUrl)
    jSearch = _safe_json_response(oRequest)  # Lade JSON aus dem Request der URL
    if not jSearch: return  # Wenn Suche erfolglos - Abbruch
    if ParameterHandler().getValue('mediaType') == 'movie': #Bei MediaTyp Filme nutze das Result
        aResults = jSearch.get('title', {}).get('videos', []) # Ausgabe der Suchresultate von jSearch für Filme
    else:
        aResults = jSearch.get('episode', {}).get('videos', []) # Ausgabe der Suchresultate von jSearch für Episoden
    # total = len(aResults)  # Anzahl aller Ergebnisse
    if len(aResults) == 0:
        if not sGui: oGui.showInfo()
        return
    for i in aResults:
        sQuality = str(i['quality'])
        if 'None' in sQuality:
            sQuality = '720p'
        sUrl = str(i['src'])
        if 'Mirror' in i['name']: # Wenn Mirror als sName hole realen Name aus der URL
            sName = cParser.urlparse(sUrl)
        else:
            sName = str(i['name'].split('-')[0].strip())
        if cConfig().isBlockedHoster(sUrl)[0]: continue  # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
        if 'youtube' in sUrl: continue # Trailer ausblenden
        hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I][%s][/I]' % (sName, sQuality), 'quality': sQuality}
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
    # https://moflix-stream.xyz/api/v1/search/Super%20Mario?query=Super+Mario&limit=8
    # Suche mit Quote und QuotePlus beim Suchtext
    sID1 = cParser.quote(sSearchText)
    sID2 = cParser.quotePlus(sSearchText)
    showSearchEntries('__moflix_catalog__', oGui, sSearchText)