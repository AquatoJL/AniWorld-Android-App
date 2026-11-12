# -*- coding: utf-8 -*-
"""TMDb-Katalog mit Übergabe an die bestehende xStream-Globale Suche."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from resources.lib.config import cConfig
from resources.lib.tmdb import cTMDB
from resources.lib.gui.gui import cGui
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.tools import logger

SITE_NAME = 'TMDb Filme & Serien'
SITE_IDENTIFIER = 'api_all'
SITE_ICON = 'api.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON
SITE_GLOBAL_SEARCH = False  # Keine rekursive Suche in der vorhandenen Globalen Suche

SCRAPER_SETTINGS = '''
<group id="api_all" label="30727">
    <setting id="plugin_api_all" type="boolean" label="30050" help="30411">
        <level>0</level><default>true</default><control type="toggle"/>
    </setting>
    <setting id="global_search_api_all" type="boolean" label="30052">
        <level>0</level><default>false</default><control type="toggle"/>
    </setting>
</group>
'''

BASE = 'https://api.themoviedb.org/3'
IMAGE = 'https://image.tmdb.org/t/p/'
CATEGORIES = {
    'movie': [
        ('Neueste Filme', 'movie/now_playing'),
        ('Beliebte Filme', 'movie/popular'),
        ('Kinofilme', 'movie/upcoming'),
        ('Top bewertet', 'movie/top_rated'),
        ('Genres', 'genre/movie/list'),
    ],
    'tv': [
        ('Neueste Serien', 'tv/on_the_air'),
        ('Beliebte Serien', 'tv/popular'),
        ('Serien im Trend', 'trending/tv/week'),
        ('Top bewertet', 'tv/top_rated'),
        ('Genres', 'genre/tv/list'),
    ],
}


def _api(path, **kwargs):
    # Vorhandene TMDb-Anbindung nutzen; api.tmdb ist in dieser Version nicht registriert.
    key = cTMDB().api_key
    if not key:
        logger.error('[api_all] TMDb API-Key fehlt in Einstellung api.tmdb')
        return None
    args = {'api_key': key, 'language': 'de-DE'}
    args.update(kwargs)
    url = BASE + '/' + path.lstrip('/') + '?' + urlencode(args)
    try:
        request = Request(url, headers={'User-Agent': 'xStream-Mod/1.0.10', 'Accept': 'application/json'})
        with urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode('utf-8'))
        if isinstance(data, dict) and data.get('success') is False:
            logger.error('[api_all] TMDb meldet: %s' % data.get('status_message', 'API-Fehler'))
            return None
        return data
    except Exception as exc:
        logger.error('[api_all] TMDb-Anfrage fehlgeschlagen (%s): %s' % (path, exc))
        return None


def _finish(gui, content='movies'):
    gui.setView(content)
    gui.setEndOfDirectory()


def load():
    gui = cGui()
    gui.addFolder(cGuiElement('Filme', SITE_IDENTIFIER, 'showCategories'), _params(media='movie'))
    gui.addFolder(cGuiElement('Serien', SITE_IDENTIFIER, 'showCategories'), _params(media='tv'))
    gui.addFolder(cGuiElement('TMDb-Suche', SITE_IDENTIFIER, 'showSearch'))
    gui.setEndOfDirectory()


def _params(**kwargs):
    params = ParameterHandler()
    for key, value in kwargs.items():
        params.setParam(key, value)
    return params


def showCategories():
    media = ParameterHandler().getValue('media')
    gui = cGui()
    if media in CATEGORIES:
        for title, path in CATEGORIES[media]:
            action = 'showGenres' if path.startswith('genre/') else 'showEntries'
            gui.addFolder(cGuiElement(title, SITE_IDENTIFIER, action), _params(media=media, path=path, page=1))
    gui.setEndOfDirectory()


def showGenres():
    media = ParameterHandler().getValue('media')
    gui = cGui()
    if media not in CATEGORIES:
        gui.setEndOfDirectory()
        return
    data = _api('genre/%s/list' % media)
    for genre in (data or {}).get('genres', []):
        gui.addFolder(cGuiElement(genre.get('name', ''), SITE_IDENTIFIER, 'showEntries'),
                      _params(media=media, path='discover/' + media, genre=genre['id'], page=1))
    gui.setEndOfDirectory()


def showEntries():
    p = ParameterHandler()
    media, path = p.getValue('media'), p.getValue('path')
    if media not in CATEGORIES or path not in [v for _, v in CATEGORIES[media]] + ['discover/' + media]:
        cGui().setEndOfDirectory()
        return
    try:
        page = max(1, min(int(p.getValue('page') or 1), 500))
    except (ValueError, TypeError):
        page = 1
    genre = p.getValue('genre')
    opts = {'page': page}
    if genre and path.startswith('discover/'):
        opts['with_genres'] = genre
        opts['sort_by'] = 'popularity.desc'
    data = _api(path, **opts)
    _show_results(data, media, path=path, page=page, genre=genre)


def showSearch():
    term = cGui().showKeyBoard(sHeading='TMDb: Film oder Serie suchen')
    if term:
        gui = cGui()
        for media, title in [('movie', 'Filme'), ('tv', 'Serien')]:
            gui.addFolder(cGuiElement('%s: %s' % (title, term), SITE_IDENTIFIER, 'showSearchResults'),
                          _params(media=media, query=term, page=1))
        gui.setEndOfDirectory()
    else:
        cGui().setEndOfDirectory()


def showSearchResults():
    p = ParameterHandler()
    media, query = p.getValue('media'), p.getValue('query')
    if media not in CATEGORIES or not query:
        cGui().setEndOfDirectory()
        return
    try:
        page = max(1, min(int(p.getValue('page') or 1), 500))
    except (TypeError, ValueError):
        page = 1
    data = _api('search/' + media, query=query, page=page, include_adult='false')
    _show_results(data, media, page=page, query=query)


def _show_results(data, media, path='', page=1, genre='', query=''):
    gui = cGui()
    if not isinstance(data, dict):
        gui.showInfo()
        gui.setEndOfDirectory()
        return
    for item in data.get('results', []):
        title = item.get('title') if media == 'movie' else item.get('name')
        if not title:
            continue
        date = item.get('release_date') if media == 'movie' else item.get('first_air_date')
        year = date[:4] if date and len(date) >= 4 else ''
        element = cGuiElement(title, 'globalSearch', 'searchGlobal')
        element.setMediaType('movie' if media == 'movie' else 'tvshow')
        if year and year.isdigit():
            element.setYear(year)
        element.setDescription(item.get('overview') or '')
        if item.get('poster_path'):
            element.setThumbnail(IMAGE + 'w500' + item['poster_path'])
        if item.get('backdrop_path'):
            element.setFanart(IMAGE + 'w1280' + item['backdrop_path'])
        if item.get('vote_average'):
            element.addItemValue('rating', float(item['vote_average']))
        params = _params(searchTitle=title, searchYear=year, searchMode='tmdb')
        gui.addFolder(element, params, iTotal=100)  # TMDb-Metadaten bereits vorhanden
    try:
        total_pages = int(data.get('total_pages', 1))
    except (TypeError, ValueError):
        total_pages = 1
    if page < min(total_pages, 500):
        action = 'showSearchResults' if query else 'showEntries'
        gui.addNextPage(SITE_IDENTIFIER, action,
                        _params(media=media, path=path, page=page + 1, genre=genre, query=query))
    _finish(gui, 'tvshows' if media == 'tv' else 'movies')


def _search(oGui, sSearchText):
    # Die TMDb-Übersicht darf nicht selbst als Hoster-Anbieter gesucht werden.
    return
