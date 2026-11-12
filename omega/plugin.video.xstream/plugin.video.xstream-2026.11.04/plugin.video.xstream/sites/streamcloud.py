# -*- coding: utf-8 -*-
# Python 3

# Always pay attention to the translations in the menu!

import concurrent.futures
import re
import time
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
import xbmcgui
from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler

# Fehlerrueckgaben der installierten xStream_mod-requestHandler.py
REQUEST_ERRORS = ('DDOS GUARD SCHUTZ', 'CLOUDFLARE-SCHUTZ AKTIV', 'SEITE NICHT ERREICHBAR', 'URL FEHLER', 'TIMEOUT')
from resources.lib.tools import logger
from resources.lib.wrappers.meinecloud import resolveMeinecloud, resolveMeinecloudSerial, expandHosterList, buildHosterFromUrl, buildMergedHosters, MEINECLOUD_TRIGGER, isPlatformUrl, platformImdbId, packSourceUrls, unpackSourceUrls
from resources.lib.tools import cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'streamcloud'
SITE_NAME = 'Streamcloud'
SITE_ICON = 'streamcloud.png'
SITE_FANART = cConfig().getAddonInfo('path') + '/resources/art/sites/' + SITE_ICON

# Streamcloud nimmt an der globalen TMDb-Suche teil.
SITE_GLOBAL_SEARCH = True

DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'streamcloud.date')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)

URL_MAIN = 'https://' + DOMAIN + '/'
URL_MAINPAGE = URL_MAIN + 'streamcloud'
URL_MOVIES = URL_MAIN + 'filme'
URL_KINO = URL_MAIN + 'kinofilme'
URL_TOP_DEUTSCHLAND = URL_MAIN + 'land/germany'
URL_FAVOURITE_MOVIE_PAGE = URL_MAIN + 'trends'
URL_SERIES = URL_MAIN + 'serien'
URL_SEARCH = URL_MAIN + 'suche?q=%s'


def _modernCards(content, kind=None):
    """Parse the current Next.js HTML cards; return legacy 4-tuples.

    Restrict extraction to card anchors to avoid menu links and unrelated HTML.
    """
    from html import unescape
    from urllib.parse import urljoin
    results = []
    seen = set()
    for match in re.finditer(r'<a\b(?=[^>]*\bclass=["\'][^"\']*\bcv\b)[^>]*>.*?</a>', content or '', re.I | re.S):
        card = match.group(0)
        link = re.search(r'\bhref=["\']([^"\']+)', card, re.I)
        if not link:
            continue
        path = unescape(link.group(1))
        if not (path.startswith('/filme/') or path.startswith('/serie/')):
            continue
        if kind == 'series' and not path.startswith('/serie/'):
            continue
        if kind == 'movies' and not path.startswith('/filme/'):
            continue
        url = urljoin(URL_MAIN, path)
        if url in seen:
            continue
        title = re.search(r'\btitle=["\']([^"\']+)', card, re.I)
        if not title:
            title = re.search(r'<div\s+class=["\']cv-t["\']>(.*?)</div>', card, re.I | re.S)
        if not title:
            continue
        name = unescape(re.sub(r'<[^>]*>', '', title.group(1))).strip()
        poster = re.search(r'<img\b[^>]*\bsrc=["\']([^"\']+)', card, re.I)
        thumb = urljoin(URL_MAIN, unescape(poster.group(1))) if poster else ''
        year = re.search(r'<div\s+class=["\']cv-m["\'][^>]*>\s*(\d{4})', card, re.I)
        results.append((name, url, thumb, year.group(1) if year else ''))
        seen.add(url)
    return results


def _menu_item(title, function, url=None):
    params = ParameterHandler()
    if url:
        params.setParam('sUrl', url)
    cGui().addFolder(cGuiElement(title, SITE_IDENTIFIER, function), params)


def load():
    logger.info('Load %s' % SITE_NAME)
    xbmcgui.Window(10000).clearProperty('xstream.streamcloud.lastSearchText')
    _menu_item('Aktuelle Filme im Kino', 'showEntries', URL_KINO)
    _menu_item('Neue Filme', 'showEntries', URL_MOVIES)
    _menu_item('Beliebte Filme', 'showEntries', URL_FAVOURITE_MOVIE_PAGE)
    _menu_item('Top Deutschland', 'showTopDeutschland', URL_TOP_DEUTSCHLAND)
    _menu_item('Alle Filme', 'showEntries', URL_MOVIES)
    _menu_item('Genres', 'showMovieGenres', URL_MOVIES)
    _menu_item('Land', 'showCountryMenu', URL_MOVIES)
    _menu_item('Erscheinungsjahr', 'showYearMenu', URL_MOVIES)
    _menu_item('Serien', 'showSeriesMenu')
    _menu_item('Suche', 'showSearch')
    cGui().setEndOfDirectory()


def showTopDeutschland():
    # Die Laenderseite enthaelt Filme UND Serien. Nur Filme anzeigen.
    showEntries(moviesOnly=True)


def showSeriesMenu():
    _menu_item('Aktuelle Serien', 'showSeries', URL_SERIES)
    _menu_item('Neue Serien', 'showSeries', URL_SERIES)
    _menu_item('Beliebte Serien', 'showPopularSeries', URL_SERIES)
    _menu_item('Alle Serien', 'showSeries', URL_SERIES)
    _menu_item('Genres', 'showSeriesGenres', URL_SERIES)
    _menu_item('Land', 'showSeriesCountryMenu', URL_SERIES)
    _menu_item('Erscheinungsjahr', 'showSeriesYearMenu', URL_SERIES)
    _menu_item('Serien suchen', 'showSeriesSearch')
    cGui().setEndOfDirectory()


def showPopularSeries():
    # Keine gesicherte eigene Beliebtheits-URL: die Serienliste bleibt erreichbar.
    showSeries(URL_SERIES)


def showSeriesGenres():
    _showFilterOptions('genere', 'showFilteredSeries', URL_SERIES)


def showSeriesCountryMenu():
    _showFilterOptions('country', 'showFilteredSeries', URL_SERIES)


def showSeriesYearMenu():
    _showYears('showFilteredSeries', URL_SERIES)


def showCountryMenu():
    _showFilterOptions('country', 'showFilteredMovies', URL_MOVIES)


def showYearMenu():
    _showYears('showFilteredMovies', URL_MOVIES)


def _showYears(function, baseUrl):
    from datetime import datetime
    for year in range(datetime.now().year, 1949, -1):
        params = ParameterHandler()
        params.setParam('filterType', 'year')
        params.setParam('filterValue', str(year))
        params.setParam('sUrl', baseUrl)
        cGui().addFolder(cGuiElement(str(year), SITE_IDENTIFIER, function), params)
    cGui().setEndOfDirectory()


def _showFilterOptions(field, function, baseUrl):
    html = cRequestHandler(URL_SERIES, caching=False).request() or ''
    pattern = r'<input[^>]*name=["\']' + re.escape(field) + r'["\'][^>]*value=["\']([^"\']+)["\'][^>]*>\s*<label[^>]*>([^<]+)</label>'
    matches = re.findall(pattern, html, re.I)
    if not matches:
        cGui().showInfo()
        cGui().setEndOfDirectory()
        return
    for value, label in matches:
        if label.strip().lower() in ('serien', 'kinofilme'):
            continue
        params = ParameterHandler()
        params.setParam('filterType', field)
        params.setParam('filterValue', value)
        params.setParam('sUrl', baseUrl)
        cGui().addFolder(cGuiElement(label.strip(), SITE_IDENTIFIER, function), params)
    cGui().setEndOfDirectory()


def showMovieGenres():
    _showFilterOptions('genere', 'showFilteredMovies', URL_MOVIES)


def _showFiltered(isSeries):
    """Filterparameter nach dem sfilter.js-GET-Format der Webseite bauen."""
    params = ParameterHandler()
    field = params.getValue('filterType')
    value = params.getValue('filterValue')
    if not value or field not in ('genere', 'country', 'year'):
        cGui().showInfo()
        cGui().setEndOfDirectory()
        return

    # Das Javascript sendet auch auf /serien/ immer an /filme-stream/.
    # Genre 27 bezeichnet Serien; damit die übrigen Filter Serien liefern,
    # muss diese ID zusätzlich in die Anfrage.
    query = {}
    if isSeries:
        query['genere'] = '27'
    if field == 'year':
        query['years'] = '%s;%s' % (value, value)
    elif field == 'genere' and isSeries:
        query['genere'] = '27,%s' % value
    else:
        query[field] = value

    url = URL_MOVIES + '?' + urlencode(query)
    logger.info('Streamcloud Filter: %s' % url)
    if isSeries:
        showSeries(url)
    else:
        showEntries(url)


def showFilteredSeries():
    _showFiltered(True)


def showFilteredMovies():
    _showFiltered(False)


def showSeriesSearch():
    sSearchText = cGui().showKeyBoard(sHeading='Serien suchen')
    if not sSearchText:
        return
    showSeries(URL_SEARCH % cParser.quotePlus(sSearchText), sSearchText=sSearchText)


def showLatest():
    """Zeigt die 'Updates' Sektion von der Streamcloud-Homepage.
    Container hat 2 Spalten: Filme links, Serien rechts (jeweils 12 Items).
    Items im Format: <a href="URL"><div><i class="flag flag-de"></i> NAME (YEAR)</div></a>
    URL-Pattern ist identisch fuer Filme und Serien — Movie/Serie-Erkennung erfolgt
    via Block-Position (vor/nach 'Serien</a>' Header).
    """
    params = ParameterHandler()
    sHtmlContent = cRequestHandler(URL_MAINPAGE).request()
    if not sHtmlContent:
        cGui().showInfo()
        return

    # Updates-Sektion isolieren
    isMatch, sContainer = cParser.parseSingleResult(
        sHtmlContent,
        r'<h2[^>]*>Updates</h2>(.*?)(?=<h2|<div\s+class="section)'
    )
    if not isMatch:
        cGui().showInfo()
        return

    # Container in Filme- und Serien-Block aufteilen
    sFilmsBlock = ''
    sSeriesBlock = ''
    splitMatch = re.search(r'<a\s+href="/serien/"[^>]*>Serien</a>', sContainer)
    if splitMatch:
        sFilmsBlock = sContainer[:splitMatch.start()]
        sSeriesBlock = sContainer[splitMatch.end():]
    else:
        sFilmsBlock = sContainer

    # Gleicher Item-Pattern fuer beide Bloecke
    item_pat = r'<a href="([^"]+)"[^>]*>\s*<div[^>]*>\s*<i class="flag flag-[a-z]+"></i>\s*([^<]+)\s*</div>\s*</a>'

    aFilms = re.findall(item_pat, sFilmsBlock)
    aSeries = re.findall(item_pat, sSeriesBlock)
    aItems = [(url, title.strip(), False) for url, title in aFilms] + \
             [(url, title.strip(), True) for url, title in aSeries]

    if not aItems:
        cGui().showInfo()
        return

    total = len(aItems)
    isTvshow = False
    for sUrl, sTitle, isSerie in aItems:
        # Year aus Title extrahieren: "Name (2026)"
        sYear = ''
        isYear, aYear = cParser.parseSingleResult(sTitle, r'\((\d{4})\)')
        if isYear:
            sYear = aYear

        sName = re.sub(r'\s*\(\d{4}\)\s*$', '', sTitle).strip()

        if sUrl.startswith('/'):
            sUrl = URL_MAIN.rstrip('/') + sUrl

        oGuiElement = cGuiElement(
            sName,
            SITE_IDENTIFIER,
            'showSeasons' if isSerie else 'showHosters'
        )
        oGuiElement.setMediaType('tvshow' if isSerie else 'movie')
        if sYear:
            oGuiElement.setYear(sYear)
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        if sYear:
            params.setParam('sYear', sYear)
        cGui().addFolder(oGuiElement, params, isSerie, total)
        isTvshow = isSerie

    cGui().setView('movies')
    cGui().setEndOfDirectory()


def showGenre(entryUrl=False):
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl)
    sHtmlContent = oRequest.request()    
    pattern = '>Genres<.*?</div></div>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    # Navigations-Einträge filtern (sind schon im Hauptmenü)
    nav_slugs = ['filme', 'filme1', 'kinofilme', 'serien', 'serienstream-deutsch',
                 'kinofilme-online', 'aktuelle-kinofilme-im-kino', 'demnachst',
                 'filme-online-sehen', 'filme-stream', 'neue-filme',
                 'erotik', 'erotikfilme']
    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl
        slug = sUrl.rstrip('/').split('/')[-1].lower()
        if slug in nav_slugs:
            continue
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def _prefetchDetails(aUrls):
    """Detailseiten einer Liste vorab parallel holen.

    Die Film/Serie-Erkennung in showEntries braucht je Eintrag einen Abruf.
    Sequenziell kostet das Latenz mal Listenlaenge; parallel bleibt es bei rund
    einer Latenz. Der Requesthandler cacht die Antworten, deshalb trifft die
    Einzelpruefung danach den Cache statt das Netz. Fehler werden geschluckt —
    die Einzelpruefung behandelt sie ohnehin selbst.
    """
    # ignoreErrors: das ist ein Hilfsabruf zur Serienerkennung, der Nutzer hat
    # diesen Titel nicht angeklickt. Antwortet die Seite mit 5xx/4xx, zeigte der
    # requestHandler dafuer ein Fehlerfenster — beim Oeffnen einer Genre-Liste
    # bis zu zehn hintereinander (Audit 01.09.2026, 502-Phase einer damals
    # gleich gebauten Schwesterseite: vier Fenster fuer „Drama"). Jetzt
    # schweigt der Abruf, der Eintrag gilt
    # als Film; das Fenster bleibt dem Klick des Nutzers vorbehalten.
    def _fetch(sUrl):
        try:
            # Nur die Seite in den Cache holen: der Serien-Check liest seit dem
            # Plattform-Umbau (28.09.2026) allein die Marker dieser Seite, ein
            # zweiter Abruf faellt weg (siehe _hasMeinecloudSerial).
            cRequestHandler(sUrl, ignoreErrors=True).request()
        except Exception:
            pass  # Fehler behandelt die Einzelpruefung selbst
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as oPool:
        list(oPool.map(_fetch, aUrls))


def _hasMeinecloudSerial(sDetailHtml):
    """Serie oder Film — die Detailseite sagt es selbst.

    Die Seite bettet je Typ ein anderes Plattform-Snippet ein: bei Serien
    `var imdb = '<tt-id>'` samt dem /serial/-Link, bei Filmen den /movie/-Link
    ohne `var imdb`. Gemessen am 28.09.2026 auf 12 von 12 Serien- und 18 von 18
    Filmseiten; die Plattform-API bestaetigt es (tv-Anfragen fuer Film-IDs
    geben 403). Damit braucht die Erkennung keinen Plattform-Abruf mehr — der
    fruehere Check-Endpunkt der Plattform (serials.php) existiert seit dem
    Umbau nicht mehr. Die Staffeln holt spaeter resolveMeinecloudSerial.
    """
    if not sDetailHtml or '/serial/' not in sDetailHtml:
        return False
    isMatch, _ = cParser.parseSingleResult(sDetailHtml, r"var imdb = '(tt\d+)'")
    return bool(isMatch)


def _fetchSearchPage(entryUrl, iPage, pattern, bFrisch=False):
    """Eine Folgeseite der Suche holen.

    Rueckgabe ist (Rohtreffer, bErreicht). bErreicht=False heisst, der Abruf
    selbst ist gescheitert — Timeout, Sperre, 404 oder leere Antwort. Das darf
    NICHT als Ende der Ergebnisse gelten: request() liefert im Fehlerfall einen
    Klartext aus REQUEST_ERRORS, darin findet das Muster nichts, und eine leere
    Trefferliste sieht dann exakt wie die letzte Seite aus. Ein einzelner
    Aussetzer wuerde so die halbe Trefferliste abschneiden (nachgestellt:
    Fehler auf Seite 4 -> 24 statt 108 Rohtreffer).
    """
    sSep = '&' if '?' in entryUrl else '?'
    # Fehler ab Seite 2 werden nicht gemeldet: die Seite blaettert weiter, als sie
    # Ergebnisse hat, und ein 404 dort ist kein Fall fuer ein Fenster.
    # bFrisch=True zwingt am HTML-Cache vorbei: Nachhol- und Bestaetigungs-
    # abrufe muessen den SERVER fragen — der Cache liefert sonst exakt die
    # Antwort zurueck, die gerade geheilt oder bestaetigt werden soll
    # (Drosselseiten mit Status 200 werden wie normale Antworten gecacht).
    oRequest = cRequestHandler('%s%ssearch_start=%d' % (entryUrl, sSep, iPage), ignoreErrors=True, caching=not bFrisch)
    sHtmlContent = oRequest.request()
    if not sHtmlContent or sHtmlContent in REQUEST_ERRORS:
        return [], False
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    return (aResult if isMatch else []), True


# Pause vor jedem Nachholversuch: gibt einem Rate-Limit (429) Luft. Kuerzer
# heilt seltener, laenger kostet nur im Fehlerfall — im Normalfall laeuft
# keine einzige Pause. 0,6 s reichten der Drossel nicht (Jacks Log 01.09.2026:
# 17 von 23 nachgeholten Seiten „weiterhin nicht erreichbar"), daher 2,5 s.
RETRY_PAUSE = 2.5


def _fetchMoreSearchPages(entryUrl, pattern, iMaxPages=10, iBatch=1):
    """Folgeseiten einer Suche einsammeln — die Seite blaettert ueber `search_start`.

    Ohne das endete jede Suche nach Seite 1. Die Seite sortiert ihre Treffer
    nicht nach Relevanz, deshalb stehen Titeltreffer regelmaessig erst auf den
    Folgeseiten: gemessen "star wars" 12 statt 32 und "koenig" 4 statt 12 bzw. 23.

    Geholt wird SEQUENZIELL (iBatch=1), nicht mehr in Vierergruppen parallel:
    mit vier gleichzeitigen Folgeseiten plus Seite 1 lief Jacks Anschluss am
    01.09.2026 in die nginx-Drossel der Seite — 29x HTTP 429 in vier Suchen
    ueber „Weitere Quellen", 17 Seiten blieben trotz Nachholrunde weg, die
    Trefferzahl wuerfelte. Sequenziell kostet gemessen etwa eine Sekunde je
    Suche bei streamcloud, bei kurzen Suchen ist es sogar schneller, weil der
    Ende-Abbruch nach der ersten leeren Seite greift statt erst nach der
    Vierergruppe. Der Batch-Parameter bleibt fuer den Fall, dass die Seite
    ihre Drossel lockert.

    Fehlertoleranz in zwei Stufen (Anlass 31.08.: unter der Parallellast fielen
    je Lauf zufaellig ganze Seiten aus, die Trefferzahl wuerfelte zwischen 21,
    26 und 39 — still, ohne jede Meldung):
    - Ein GESCHEITERTER Abruf (Timeout, Sperre, 404) wird nach den Gruppen
      einmal sequenziell mit kurzer Pause nachgeholt statt still verworfen.
    - Eine ERREICHTE Seite ohne Treffer gilt erst als Listenende, wenn ein
      zweiter Abruf das bestaetigt — ein 200er mit leerem Body saehe sonst
      exakt wie das Ende aus und schnitte alles Folgende ab. Kostet am
      echten Ende genau einen Zusatzabruf.
    Die Treffer werden je Seite gesammelt und in Seitenreihenfolge
    zurueckgegeben, damit Nachgeholtes an der richtigen Stelle landet.
    """
    dPages = {}
    aRetry = []
    iEnde = None
    iPage = 2
    while iPage <= iMaxPages:
        aBatch = list(range(iPage, min(iPage + iBatch, iMaxPages + 1)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(aBatch)) as oPool:
            aPages = list(oPool.map(lambda p: _fetchSearchPage(entryUrl, p, pattern), aBatch))
        for iNum, (aRows, bErreicht) in zip(aBatch, aPages):
            if not bErreicht:
                aRetry.append(iNum)
            elif aRows:
                dPages[iNum] = aRows
            else:
                # Ende-Kandidat: einmal bestaetigen, bevor abgebrochen wird.
                time.sleep(RETRY_PAUSE)
                aRows2, bErreicht2 = _fetchSearchPage(entryUrl, iNum, pattern, bFrisch=True)
                if bErreicht2 and not aRows2:
                    iEnde = iNum
                    break
                if aRows2:
                    # Hickser: beim zweiten Abruf war die Seite doch gefuellt.
                    logger.info('searchRetry %s: Seite %d nachgeholt, %d Treffer' % (SITE_NAME, iNum, len(aRows2)))
                    dPages[iNum] = aRows2
                else:
                    # Erst leer-erreicht, dann gescheitert: unklar, Seite fehlt.
                    logger.info('searchRetry %s: Seite %d nicht bestaetigt, Treffer dieser Seite fehlen' % (SITE_NAME, iNum))
        if iEnde is not None:
            break
        iPage += iBatch
    # Nachholrunde: gescheiterte Seiten einmal sequenziell holen. Seiten hinter
    # einem bestaetigten Ende liegen jenseits der Ergebnisse und bleiben weg.
    if iEnde is not None:
        aRetry = [p for p in aRetry if p < iEnde]
    for iNum in aRetry:
        time.sleep(RETRY_PAUSE)
        aRows, bErreicht = _fetchSearchPage(entryUrl, iNum, pattern, bFrisch=True)
        if aRows:
            logger.info('searchRetry %s: Seite %d nachgeholt, %d Treffer' % (SITE_NAME, iNum, len(aRows)))
            dPages[iNum] = aRows
        else:
            logger.info('searchRetry %s: Seite %d weiterhin nicht erreichbar, Treffer dieser Seite fehlen' % (SITE_NAME, iNum))
    aAll = []
    for iNum in sorted(dPages):
        aAll.extend(dPages[iNum])
    return aAll


def _keepFilterQuery(currentUrl, nextUrl):
    """Filter beim Weiterblaettern erhalten, falls Next sie nicht enthaelt."""
    from urllib.parse import urljoin
    nextUrl = urljoin(URL_MAIN, nextUrl)
    current = dict(parse_qsl(urlsplit(currentUrl).query))
    parts = urlsplit(nextUrl)
    existing = dict(parse_qsl(parts.query))
    for key in ('genere', 'country', 'years'):
        if key in current and key not in existing:
            existing[key] = current[key]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(existing), parts.fragment))


def showEntries(entryUrl=False, sGui=False, sSearchText=False, moviesOnly=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    # Adressen mit Leerzeichen oder Umlaut kommen aus dem Parameter-Durchlauf
    # unkodiert zurueck -> direkt vor dem Request kodieren (deckt auch die
    # Naechste-Seite-URL ab). Pfadstruktur bleibt erhalten.
    entryUrl = cParser.urlEncode(entryUrl, safe="/:?=&%#")
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    sHtmlContent = oRequest.request()
    modern = _modernCards(sHtmlContent, 'series' if False else 'movies')
    if modern:
        total = len(modern)
        for name, url, thumb, year in modern:
            if sSearchText and str(sSearchText).casefold() not in name.casefold():
                continue
            is_series = urlsplit(url).path.startswith('/serie/')
            if False is False and moviesOnly and is_series:
                continue
            gui_item = cGuiElement(name, SITE_IDENTIFIER, 'showSeasons' if is_series else 'showHosters')
            if thumb:
                gui_item.setThumbnail(thumb)
            gui_item.setMediaType('tvshow' if is_series else 'movie')
            if year:
                gui_item.setYear(year)
            item_params = ParameterHandler()
            item_params.setParam('entryUrl', url)
            item_params.setParam('sName', name)
            item_params.setParam('sThumbnail', thumb)
            item_params.setParam('sYear', year)
            oGui.addFolder(gui_item, item_params, is_series, total)
        if not sGui:
            oGui.setView('tvshows' if False else 'movies')
            oGui.setEndOfDirectory()
        return
    pattern = 'class="thumb".*?title="([^"]+).*?href="([^"]+).*?src="([^"]+).*?_year">([^<]+)'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if isMatch and sSearchText:
        # In der globalen Suche laufen alle Sites gleichzeitig, deshalb dort nur
        # fuenf Seiten je Site. Mit zehn dauerte eine breite Suche ueber Mobilfunk
        # 19 s ("koenig", 412 Treffer) — der Einzelaufruf der Site bleibt bei zehn,
        # dort laeuft nur eine Seite zur Zeit.
        aResult += _fetchMoreSearchPages(entryUrl, pattern, iMaxPages=5 if sGui else 10)
    # Wie bei FilmPro: kurze Titel koennen auf der Webseite in der allgemeinen
    # Suche fehlen, obwohl die jahresbezogene Suche sie findet. Nur wenn kein
    # Treffer mit exakt passendem Titel und aktuellem Jahr vorliegt, nachsuchen.
    if sSearchText:
        from datetime import datetime
        from html import unescape
        _query_text = unescape(str(sSearchText)).strip()
        _year_match = re.search(r'\b((?:19|20)\d{2})\b', _query_text)
        _plain_title = re.sub(r'\s*[-–]?\s*\(?\b(?:19|20)\d{2}\b\)?\s*$', '', _query_text).strip()
        _wanted_year = _year_match.group(1) if _year_match else str(datetime.now().year)
        _normalize = lambda t: re.sub(r'\s+', ' ', re.sub(r'\s*[-–]?\s*\(?\b(?:19|20)\d{2}\b\)?\s*$', '', unescape(str(t)))).strip().casefold()
        _has_exact = any(_normalize(n) == _normalize(_plain_title) and str(y).strip() == _wanted_year
                         for n, _u, _t, y in (aResult or []))
        if _plain_title and not _has_exact:
            try:
                _extra_query = '%s (%s)' % (_plain_title, _wanted_year)
                _extra_url = URL_SEARCH % cParser.quotePlus(_extra_query)
                _extra_html = cRequestHandler(_extra_url, ignoreErrors=True).request() or ''
                _extra_ok, _extra_rows = cParser.parse(_extra_html, pattern)
                if _extra_ok:
                    _seen_urls = {u for _n, u, _t, _y in (aResult or [])}
                    for _row in _extra_rows:
                        if _row[1] not in _seen_urls:
                            aResult.append(_row)
                            _seen_urls.add(_row[1])
                    isMatch = bool(aResult)
                logger.info('Streamcloud Jahres-Nachsuche %s: %d Treffer' % (_extra_query, len(_extra_rows or [])))
            except Exception as _exc:
                logger.info('Streamcloud Jahres-Nachsuche fehlgeschlagen: %s' % _exc)
    if not isMatch and not aResult:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    iShown = 0
    # Die Serien-Erkennung unten braucht je Eintrag die Detailseite. Einzeln in
    # der Schleife abgerufen summiert sich das auf der Leitung (Latenz mal
    # Listenlaenge) — gemessen bei 0,30 s Latenz 8,87 s fuer eine Kategorie mit
    # zwoelf Titeln, in der globalen Suche 17,8 s ueber alle Ergebnisseiten.
    # Deshalb werden sie VOR der Schleife parallel geholt; die Einzelpruefung
    # trifft danach den HTML-Cache und loest keinen zweiten Netzabruf aus.
    # Gefiltert wird vorher, damit keine Seite fuer einen Titel geholt wird, den der
    # Suchfilter ohnehin verwirft.
    _filter_title = re.sub(r'\s*[-–]?\s*\(?\b(?:19|20)\d{2}\b\)?\s*$', '', str(sSearchText)).strip() if sSearchText else ''
    _prefetchDetails([u for n, u, _t, _y in aResult
                      if not sSearchText or _filter_title.casefold() in n.casefold()])
    for sName, sUrl, sThumbnail, sYear in aResult:
        if sSearchText and not _filter_title.casefold() in sName.casefold():
            continue
        if sThumbnail[0] == '/':
            sThumbnail = sThumbnail[1:]
        # In den Parameter gehoert die VOLLE Adresse, nicht der relative Pfad:
        # showSeasons und showEpisodes setzen den Wert unveraendert als Bild, und
        # ein relativer Pfad laesst sich dort nicht laden - die Staffelauswahl blieb
        # ohne Cover, sobald man ueber Suche, Aktuelle Releases, Filme oder Genre in
        # eine Serie ging (belegt 04.09.2026 an "Law & Order"). Ueber showSeries war
        # das Cover da, weil dort schon die volle Adresse weitergereicht wird.
        sThumbAbs = sThumbnail if sThumbnail.startswith('http') else URL_MAIN + sThumbnail.lstrip('/')

        # Film/Serie via Detail-Seite erkennen (zuverlässigste Quelle bei streamcloud)
        # xStream's Request-Cache macht Wiederholungen instant
        isTvshow = False
        try:
            detailHtml = cRequestHandler(sUrl, ignoreErrors=True).request()   # Hilfsabruf, siehe _prefetchDetails
            # Serie erkannt wenn data-num="NxN" (natives DLE-Pattern) ODER das
            # Plattform-Snippet der Seite eine Serie meldet (_hasMeinecloudSerial).
            # Streamcloud hat seine Serien auf die Plattform umgestellt (kein
            # data-num mehr) — ohne diesen Marker wuerden Plattform-Serien wie
            # "The Rookie" als Film erkannt und direkt in einen Stream springen
            # statt in die Serie.
            isSeriesMatch, _ = cParser.parseSingleResult(detailHtml, r'data-num="\d+x\d+"')
            if not isSeriesMatch:
                isSeriesMatch = _hasMeinecloudSerial(detailHtml)
            if isSeriesMatch:
                isTvshow = True
        except Exception:
            isTvshow = False

        if moviesOnly and isTvshow:
            continue

        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setThumbnail(sThumbAbs)
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        # Bei Kinofilmen die Beschreibung aus der bereits geladenen Detailseite
        # uebernehmen. Keine zusaetzlichen Netzwerkaufrufe erforderlich.
        if '/kinofilme/' in urlsplit(entryUrl).path and detailHtml:
            from html import unescape
            mDesc = re.search(r'<meta\s+[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', detailHtml, re.I)
            if not mDesc:
                mDesc = re.search(r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']', detailHtml, re.I)
            if mDesc:
                sDesc = unescape(re.sub(r'<[^>]+>', '', mDesc.group(1))).strip()
                if sDesc:
                    oGuiElement.setDescription(sDesc)
        if sYear: oGuiElement.setYear(sYear)  # Aki: reaktiviert - heutige tmdb/api.py hat getrennte year-Parameter
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbAbs)
        params.setParam('sYear', sYear)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
        iShown += 1
        
    # Kamen Treffer an, wurden aber ALLE vom Titelfilter verworfen, stand hier
    # ein leeres Verzeichnis ohne Hinweis (belegt mit "koenig", Audit 01.09.2026).
    # BEWUSST VOR dem Pagination-Block: dessen Bedingung schliesst die Suche aus,
    # die Meldung wuerde dort nie erreicht. Gleiches Muster wie in hdfilme.
    if not sGui and not iShown:
        oGui.showInfo()

    if not sGui and not sSearchText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'href="([^"]+)">Next')
        # Seitenlage fuer den Weiter-Eintrag: die hoechste Zahl der Blaetterleiste ist
        # das Listenende — bei langen Listen steht sie hinter der "…"-Auslassung, bei
        # kurzen sind ohnehin alle Zahlen da (gemessen 04.09.2026 gegen die bisektierten
        # Enden, kurz wie lang). Die aktive Seite steht als <span> in derselben Leiste.
        sPageInfo = ''
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="wp-pagenavi(.*?)Next')
        if isMatchSiteSearch:
            isMatchCur, sCurrent = cParser.parseSingleResult(sHtmlContainer, r'<span[^>]*>(\d+)</span>')
            aPages = [int(x) for x in re.findall(r'>(\d{1,6})<', sHtmlContainer)]
            if isMatchCur and aPages:
                sPageInfo = '%s/%s' % (sCurrent, max(aPages))

        if isMatchNextPage:
            sNextUrl = _keepFilterQuery(entryUrl, sNextUrl)
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showTopDeutschland' if moviesOnly else 'showEntries', params)

        oGui.setView('movies')
        oGui.setEndOfDirectory()


def showSeries(entryUrl=False, sGui=False, sSearchText=False): # Neu eingebaut da auf der Webseite nicht erkennbar ist was Serien sind und was nicht
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = True
    if not entryUrl: entryUrl = params.getValue('sUrl')
    # Adressen mit Leerzeichen oder Umlaut kommen aus dem Parameter-Durchlauf
    # unkodiert zurueck -> direkt vor dem Request kodieren (deckt auch die
    # Naechste-Seite-URL ab). Pfadstruktur bleibt erhalten.
    entryUrl = cParser.urlEncode(entryUrl, safe="/:?=&%#")
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    sHtmlContent = oRequest.request()
    modern = _modernCards(sHtmlContent, 'series' if True else 'movies')
    if modern:
        total = len(modern)
        for name, url, thumb, year in modern:
            if sSearchText and str(sSearchText).casefold() not in name.casefold():
                continue
            is_series = urlsplit(url).path.startswith('/serie/')
            if True is False and moviesOnly and is_series:
                continue
            gui_item = cGuiElement(name, SITE_IDENTIFIER, 'showSeasons' if is_series else 'showHosters')
            if thumb:
                gui_item.setThumbnail(thumb)
            gui_item.setMediaType('tvshow' if is_series else 'movie')
            if year:
                gui_item.setYear(year)
            item_params = ParameterHandler()
            item_params.setParam('entryUrl', url)
            item_params.setParam('sName', name)
            item_params.setParam('sThumbnail', thumb)
            item_params.setParam('sYear', year)
            oGui.addFolder(gui_item, item_params, is_series, total)
        if not sGui:
            oGui.setView('tvshows' if True else 'movies')
            oGui.setEndOfDirectory()
        return
    pattern = 'class="thumb".*?title="([^"]+).*?href="([^"]+).*?src="([^"]+).*?_year">([^<]+)'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    iShown = 0
    for sName, sUrl, sThumbnail, sYear in aResult:
        if sSearchText and not str(sSearchText).casefold() in sName.casefold():
            continue
        if sThumbnail[0] == '/':
            sThumbnail = sThumbnail[1:]
        sThumbAbs = sThumbnail if sThumbnail.startswith('http') else URL_MAIN + sThumbnail.lstrip('/')
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setThumbnail(sThumbAbs)
        oGuiElement.setMediaType('tvshow')
        if sYear: oGuiElement.setYear(sYear)  # Aki: reaktiviert - heutige tmdb/api.py hat getrennte year-Parameter
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbAbs)
        params.setParam('sYear', sYear)

        oGui.addFolder(oGuiElement, params, isTvshow, total)
        iShown += 1

    # Kamen Treffer an, wurden aber ALLE vom Titelfilter verworfen, stand hier
    # ein leeres Verzeichnis ohne Hinweis (belegt mit "koenig", Audit 01.09.2026).
    # BEWUSST VOR dem Pagination-Block: dessen Bedingung schliesst die Suche aus,
    # die Meldung wuerde dort nie erreicht. Gleiches Muster wie in hdfilme.
    if not sGui and not iShown:
        oGui.showInfo()

    if not sGui and not sSearchText:
        # Beleg ist der Vorwaerts-Link der Seite — dasselbe Muster wie in showEntries.
        # Das frueher hier stehende Muster verlangte >\d[1-9]+< und scheiterte damit an
        # jeder letzten Seitenzahl, die ab der zweiten Stelle eine 0 traegt (aktuell 506):
        # der Weiter-Eintrag fiel komplett weg und die Serienliste endete nach der ersten
        # Seite, obwohl die Quelle ueber 500 Seiten fuehrt. Umgekehrt griff es auf der
        # letzten Seite, wo gar keine Folgeseite mehr existiert.
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'href="([^"]+)">Next')
        # Seitenlage fuer den Weiter-Eintrag: die hoechste Zahl der Blaetterleiste ist
        # das Listenende — bei langen Listen steht sie hinter der "…"-Auslassung, bei
        # kurzen sind ohnehin alle Zahlen da (gemessen 04.09.2026 gegen die bisektierten
        # Enden, kurz wie lang). Die aktive Seite steht als <span> in derselben Leiste.
        sPageInfo = ''
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="wp-pagenavi(.*?)Next')
        if isMatchSiteSearch:
            isMatchCur, sCurrent = cParser.parseSingleResult(sHtmlContainer, r'<span[^>]*>(\d+)</span>')
            aPages = [int(x) for x in re.findall(r'>(\d{1,6})<', sHtmlContainer)]
            if isMatchCur and aPages:
                sPageInfo = '%s/%s' % (sCurrent, max(aPages))
        if isMatchNextPage:
            sNextUrl = _keepFilterQuery(entryUrl, sNextUrl)
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showSeries', params)
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


# Poster der Detailseite: genau ein <img itemprop="image" src="/uploads/thumb/300x450-…">
# (DLE-Fullstory, gemessen 03.10.2026 an 60 von 60 Detailseiten, Filme wie Serien). Ein
# og:image-Meta fuehrt die Seite NICHT. Gebraucht, wenn die Liste kein Cover mitliefert
# (Neu auf der Seite = Updates-Block ohne Bilder) — die Detailseite ist dann ohnehin geladen,
# es kostet keinen Abruf.
_RE_DETAIL_COVER = re.compile(r'<img\b[^>]*\bitemprop="image"[^>]*>', re.I)


def _detailCover(sHtmlContent):
    """Volle Adresse des Posters aus dem Detail-HTML, sonst ''."""
    m = _RE_DETAIL_COVER.search(sHtmlContent or '')
    mSrc = re.search(r'\bsrc="([^"]+)"', m.group(0)) if m else None
    if not mSrc:
        return ''
    sCover = mSrc.group(1)
    if sCover.startswith('//'):
        return 'https:' + sCover
    return sCover if sCover.startswith('http') else URL_MAIN.rstrip('/') + '/' + sCover.lstrip('/')


def showSeasons():
    """Staffel-Ebene fuer Serien. Native DLE-Serien liefern die Staffeln ueber
    data-num="SxE", meinecloud-Serien ueber die Plattform-API (resolveMeinecloudSerial). Bei genau einer Staffel
    wird die Ordner-Ebene uebersprungen (direkt in die Episoden, HTML/mc werden
    durchgereicht — kein zweiter Request/Lookup)."""
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sName = params.getValue('sName') if params.exist('sName') else ''
    sThumbnail = params.getValue('sThumbnail')
    sHtmlContent = cRequestHandler(entryUrl).request()
    if not sThumbnail:
        # Liste ohne Cover (Neu auf der Seite): Poster der Detailseite, und als Parameter
        # weiter, damit auch der Klick auf eine Staffel es hat
        sThumbnail = _detailCover(sHtmlContent)
        if sThumbnail:
            params.setParam('sThumbnail', sThumbnail)

    # Native data-num Staffeln (erste Zahl vor dem 'x')
    isMatch, aNum = cParser.parse(sHtmlContent, r'data-num="(\d+)x\d+"')
    seasons = sorted(set(int(s) for s in aNum)) if isMatch else []

    # meinecloud-Serie: Staffeln aus der Plattform-API
    aMc = []
    if not seasons:
        sImdbId = platformImdbId(sHtmlContent)
        if sImdbId:
            aMc = resolveMeinecloudSerial(sImdbId, referer=entryUrl, siteHtml=sHtmlContent)
            seasons = sorted(set(ep['season'] for ep in aMc))

    if not seasons:
        cGui().showInfo()
        return

    # Nur eine Staffel: Ordner-Ebene sparen, direkt in die Episoden.
    if len(seasons) == 1:
        showEpisodes(staffel=seasons[0], htmlContent=sHtmlContent, mcEpisodes=aMc)
        return

    for iSeason in seasons:
        oGuiElement = cGuiElement(cConfig().getLocalizedString(30512) + ' %d' % iSeason, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setSeason(iSeason)
        if sName: oGuiElement.setTVShowTitle(sName)
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        params.setParam('entryUrl', entryUrl)
        params.setParam('staffel', str(iSeason))
        cGui().addFolder(oGuiElement, params, True)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes(staffel=None, htmlContent=None, mcEpisodes=None):
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sTVShowTitle = params.getValue('sName') if params.exist('sName') else ''   # sName ist unten die Folgenkennung der Schleife
    sThumbnail = params.getValue('sThumbnail')
    # staffel/htmlContent/mcEpisodes werden von showSeasons durchgereicht
    # (Single-Staffel-Skip), sonst kommt die Staffel aus dem Parameter
    # (Klick auf einen Staffel-Ordner).
    if staffel is None and params.exist('staffel'):
        staffel = params.getValue('staffel')
    sStaffel = str(staffel) if staffel is not None else None
    if htmlContent is not None:
        sHtmlContent = htmlContent
    else:
        sHtmlContent = cRequestHandler(entryUrl).request()

    isMatch, aResult = cParser.parse(sHtmlContent, 'data-num="([^"]+)')

    # meinecloud-Episoden: durchgereicht (von showSeasons) oder — falls native
    # Pattern leer — neu laden (Stranger Things etc., Daten nur ueber die Plattform-API).
    aMeinecloudEpisodes = list(mcEpisodes) if mcEpisodes else []
    if not isMatch and not aMeinecloudEpisodes:
        sImdbId = platformImdbId(sHtmlContent)
        if sImdbId:
            aMeinecloudEpisodes = resolveMeinecloudSerial(sImdbId, referer=entryUrl, siteHtml=sHtmlContent)
    if aMeinecloudEpisodes and not isMatch:
        # Format wie Site-Pattern: "<staffel>x<episode>" — kompatibel zu showHosters
        aResult = ['%dx%d' % (ep['season'], ep['episode']) for ep in aMeinecloudEpisodes]

    if not aResult:
        cGui().showInfo()
        return

    # Auf die gewaehlte Staffel filtern (native + meinecloud synchron halten).
    if sStaffel is not None:
        if aMeinecloudEpisodes:
            filtered = [(ep, sNum) for ep, sNum in zip(aMeinecloudEpisodes, aResult) if str(ep['season']) == sStaffel]
            aMeinecloudEpisodes = [ep for ep, sNum in filtered]
            aResult = [sNum for ep, sNum in filtered]
        else:
            aResult = [sNum for sNum in aResult if sNum.split('x')[0] == sStaffel]
        if not aResult:
            cGui().showInfo()
            return

    # Falls kein Parent-Thumbnail uebergeben (z.B. aus showLatest): Poster der Detailseite
    if not sThumbnail:
        sThumbnail = _detailCover(sHtmlContent)

    total = len(aResult)
    for i, sName in enumerate(aResult):
        # meinecloud-Mode: Label mit Episodentitel anreichern
        if aMeinecloudEpisodes:
            ep = aMeinecloudEpisodes[i]
            sLabel = 'S%dE%d — %s' % (ep['season'], ep['episode'], ep['title'])
        else:
            sLabel = sName
        oGuiElement = cGuiElement(sLabel, SITE_IDENTIFIER, 'showHosters')
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setMediaType('episode')
        if sTVShowTitle: oGuiElement.setTVShowTitle(sTVShowTitle)
        if aMeinecloudEpisodes:
            oGuiElement.setSeason(ep['season'])
            oGuiElement.setEpisode(ep['episode'])
        params.setParam('entryUrl', entryUrl)
        params.setParam('episode', sName)
        # meinecloud-Mode: alle Quellen der Folge mitgeben (ein Parameter, packSourceUrls),
        # damit showHosters() ohne weiteren Lookup aufloest
        if aMeinecloudEpisodes:
            params.setParam('meinecloud_url', packSourceUrls(aMeinecloudEpisodes[i]['urls']))
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def _resolvePlayerWrapper(wrapperUrl):
    """Löst einen streamcloud-internen /player/... Wrapper zu einer echten Hoster-URL auf."""
    try:
        oRequest = cRequestHandler(wrapperUrl)
        oRequest.addHeaderEntry('Referer', URL_MAIN)
        wrapperHtml = oRequest.request()
        # Innerhalb des Wrappers stehen iframes oder direkte Hoster-URLs
        # Pattern: iframe src=, oder data-link= mit http(s)
        isMatch, aResult = cParser.parse(wrapperHtml, r'<iframe[^>]+src="(https?://[^"]+)"')
        if isMatch and aResult:
            return aResult[0]
        isMatch, aResult = cParser.parse(wrapperHtml, r'data-link="(https?://[^"]+)"')
        if isMatch and aResult:
            return aResult[0]
    except Exception:
        pass
    return None


def showHosters():
    hosters = []
    sUrl = ParameterHandler().getValue('entryUrl')
    sMeinecloudUrl = ParameterHandler().getValue('meinecloud_url') if ParameterHandler().exist('meinecloud_url') else ''

    # meinecloud-Mode: die Adressen kommen direkt aus showEpisodes (alle Quellen der
    # Folge in einem Parameter, unpackSourceUrls), kein DLE-HTML-Parsing noetig.
    if sMeinecloudUrl:
        for sMcUrl in unpackSourceUrls(sMeinecloudUrl):
            _fixedUrl = ('https:' + sMcUrl) if sMcUrl.startswith('//') else sMcUrl
            sName = cParser.urlparse(_fixedUrl).split('.')[0].strip()
            if not cConfig().isBlockedHoster(sName)[0]:
                hosters.append({'link': _fixedUrl, 'name': sName, 'displayedName': sName})
        if hosters:
            hosters.append('getHosterUrl')
        return hosters

    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    if ParameterHandler().exist('episode'): #kommt aus showSeries
        episode = ParameterHandler().getValue('episode')
        # Ganzen <li>-Block für diese Episode holen (primary + alle mirrors)
        # Struktur: <li><a data-num="NxN">...</a><div class="mirrors"><a data-m="..." data-link="...">...</a>...</div></li>
        blockPattern = r'<li>\s*<a [^>]*data-num="{0}".*?</li>'.format(episode)
        isMatch, sBlock = cParser.parseSingleResult(sHtmlContent, blockPattern)
        if not isMatch:
            cGui().showInfo()
            return
        # Native DLE-Serien (data-num) sind auf der Seite seit der Umstellung auf meinecloud
        # kaum noch zu finden (Stichproben 02.09.2026: keine) — dieser Zweig bleibt fuer den
        # Altbestand. Echte HTML-Kommentare (<!-- ... -->) entfernen damit disablte Mirrors rausfliegen.
        # Aber NICHT <!--- ... ---> (drei Dashes) matchen — Streamcloud nutzt das Format
        # fuer "soft-disabled" Mirrors (z.B. Dropload). Falls Site-Owner sie reaktiviert,
        # sind sie automatisch verfuegbar ohne Code-Touch.
        sBlock = re.sub(r'<!--(?!-)(.*?)(?<!-)-->', '', sBlock, flags=re.DOTALL)
        # Alle data-link sammeln (externe + interne Player-Wrapper)
        isMatch, aResult = cParser.parse(sBlock, r'data-link="([^"]+)"')
        if not isMatch:
            cGui().showInfo()
            return
        # Interne /player/... URLs auflösen, externe direkt übernehmen
        resolvedLinks = []
        seen = set()
        for link in aResult:
            if link.startswith('/'):
                # Interner Player-Wrapper → zu echter Hoster-URL auflösen
                fullWrapperUrl = URL_MAIN + link.lstrip('/')
                realUrl = _resolvePlayerWrapper(fullWrapperUrl)
                if realUrl and realUrl not in seen:
                    seen.add(realUrl)
                    resolvedLinks.append(realUrl)
            elif link.startswith('http') and link not in seen:
                seen.add(link)
                resolvedLinks.append(link)
        aResult = resolvedLinks
        if not aResult:
            cGui().showInfo()
            return
        isMatch = True
    else:
        # Aufs Tag begrenzt: der alte offene Schnitt ('<iframe.*?allowfull') lief
        # bei einem iframe OHNE allowfull-Attribut bis zum naechsten allowfull im
        # Dokument weiter und haette dann ein fremdes src gegriffen — dieselbe
        # Fallenklasse wie ein offener serial_iframe-Schnitt. Die Player-iframes
        # der Seite tragen allowfullscreen im Tag, fuer die aendert sich nichts.
        # Das komplette iframe-Tag auswerten: das alte Pattern endete bereits
        # bei "allowfull" und konnte ein danach stehendes src nicht erkennen.
        aIframes = re.findall(r'<iframe\b[^>]*>', sHtmlContent or '', re.I | re.S)
        sPlayerUrl = ''
        for sTag in aIframes:
            if not re.search(r'\ballowfullscreen\b|\ballowfull\b', sTag, re.I):
                continue
            mSrc = re.search(r'\bsrc\s*=\s*["\']([^"\']+)', sTag, re.I)
            if mSrc:
                sPlayerUrl = mSrc.group(1).strip()
                break
        if not sPlayerUrl:
            # Auch ein direkt eingebetteter Plattform-Link ist verwendbar.
            mPlatform = re.search(r'https?://[^"\'\s<>]+(?:meinecloud|devideosrc)[^"\'\s<>]*', sHtmlContent or '', re.I)
            if mPlatform:
                sPlayerUrl = mPlatform.group(0)
        if not sPlayerUrl:
            logger.info('streamcloud: kein Player-iframe auf %s gefunden' % sUrl)
            cGui().showInfo()
            return
        if sPlayerUrl.startswith('//'):
            sPlayerUrl = 'https:' + sPlayerUrl
        elif sPlayerUrl.startswith('/'):
            sPlayerUrl = URL_MAIN.rstrip('/') + sPlayerUrl
        sUrl = sPlayerUrl
        if isPlatformUrl(sUrl):
            # Plattform-iframe (meinecloud/devideosrc): Laden und Parsen macht
            # resolveMeinecloud() zentral — inklusive API-Zweig fuer den neuen
            # DEVIDEOSRC-Player und caching=False, weil die Plattform Hoster
            # rotiert. Der Selbst-Parse darunter griffe beim neuen Player
            # (keine data-links im HTML) ins Leere. Das expandHosterList am
            # Konvergenzpunkt unten laeuft fuer diese schon finalen URLs als
            # reiner Dedupe-Durchlauf ohne weiteren Netzabruf.
            aResult = expandHosterList([sUrl], referer=URL_MAIN)
            isMatch = bool(aResult)
        else:
            sHtmlContent = cRequestHandler(sUrl, caching=False, ignoreErrors=True).request()
            isMatch, aResult = cParser.parse(sHtmlContent or '', 'data-link="([^"]+)')
            if not isMatch:
                logger.info('streamcloud: keine Hoster-Links auf Player-Seite %s' % sUrl)
    if isMatch:
        sQuality = '720'
        # Meinecloud-Wrapper expandieren: streamcloud versteckt zusaetzliche Hoster
        # hinter meinecloud-URLs (siehe resources/lib/wrappers/meinecloud.py). Page liefert eigene data-link Liste.
        # Greift fuer beide Modi (Episode + Movie konvergieren hier).
        aResult = expandHosterList(aResult, referer=URL_MAIN)

        for sUrl in aResult:
            if not sUrl or not sUrl.strip(): continue   # Leere data-link skippen (z.B. meinecloud "andere Server" Toggle)
            hoster = buildHosterFromUrl(sUrl, sQuality=sQuality, includeQualitySuffix=True)
            if hoster:
                hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    else:
        logger.info('streamcloud: keine spielbaren Hoster gefunden')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    win = xbmcgui.Window(10000)
    sSearchText = win.getProperty('xstream.streamcloud.lastSearchText')
    if not sSearchText:
        sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30287))
        if not sSearchText: return
        win.setProperty('xstream.streamcloud.lastSearchText', sSearchText)
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_SEARCH % cParser.quotePlus(sSearchText), oGui, sSearchText)


