# -*- coding: utf-8 -*-
# Python 3

import sys
import xbmc
import xbmcgui
import os
import time
from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.handler.pluginHandler import cPluginHandler
from xbmc import LOGINFO as LOGNOTICE, LOGERROR, log
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.gui.gui import cGui
from resources.lib.config import cConfig
from resources.lib.tools import logger, cParser, cCache

try:
    import resolveurl as resolver
except ImportError:
    # Resolver Fehlermeldung (bei defekten oder nicht installierten Resolver)
    xbmcgui.Dialog().ok(cConfig().getLocalizedString(30119), cConfig().getLocalizedString(30120))


def viewInfo(params):
    from resources.lib.tmdbinfo import WindowsBoxes
    parms = ParameterHandler()
    sCleanTitle = params.getValue('searchTitle')
    sMeta = parms.getValue('sMeta')
    sYear = parms.getValue('sYear')
    WindowsBoxes(sCleanTitle, sCleanTitle, sMeta, sYear)


def parseUrl():
    if xbmc.getInfoLabel('Container.PluginName') == 'plugin.video.osmosis':
        sys.exit()

    params = ParameterHandler()
    logger.info(params.getAllParameters())

    # If no function is set, we set it to the default "load" function
    if params.exist('function'):
        sFunction = params.getValue('function')
        if sFunction == 'spacer':
            return True
        elif sFunction == 'clearCache':
            cRequestHandler('dummy').clearCache()
            return
        elif sFunction == 'viewInfo':
            viewInfo(params)
            return
        elif sFunction == 'searchAlter':
            searchAlter(params)
            return
        elif sFunction == 'searchTMDB':
            searchTMDB(params)
            return
        elif sFunction == 'devUpdates':
            from resources.lib import updateManager
            updateManager.devUpdates()
            return
        elif sFunction == 'pluginInfo':
            cPluginHandler().pluginInfo()
            return
        elif sFunction == 'systemStatus':
            showSystemStatus()
            return
        elif sFunction == 'vod':
            vodGuiElements(sFunction)
            return
        elif sFunction == 'changelog':
            from resources.lib import tools
            cConfig().setSetting('changelog_version', '')
            tools.changelog()
            return
        elif sFunction == 'devWarning':
            from resources.lib import tools
            tools.devWarning()
            return
            
    elif params.exist('remoteplayurl'):
        try:
            remotePlayUrl = params.getValue('remoteplayurl')
            sLink = resolver.resolve(remotePlayUrl)
            if sLink:
                xbmc.executebuiltin('PlayMedia(' + sLink + ')')
            else:
                log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Could not play remote url %s ' % sLink, LOGNOTICE)
        except resolver.resolver.ResolverError as e:
            log(cConfig().getLocalizedString(30166) + ' -> [xstream]: ResolverError: %s' % e, LOGERROR)
        return
    else:
        sFunction = 'load'

    # Test if we should run a function on a special site
    if not params.exist('site'):
        # As a default if no site was specified, we run the default starting gui with all plugins
        showMainMenu(sFunction)
        return
    sSiteName = params.getValue('site')
    if params.exist('playMode'):
        from resources.lib.gui.hoster import cHosterGui
        url = False
        playMode = params.getValue('playMode')
        isHoster = params.getValue('isHoster')
        url = params.getValue('url')
        manual = params.exist('manual')

        if cConfig().getSetting('hosterSelect') == 'Auto' and playMode != 'jd' and playMode != 'jd2' and playMode != 'pyload' and not manual:
            cHosterGui().streamAuto(playMode, sSiteName, sFunction)
        else:
            cHosterGui().stream(playMode, sSiteName, sFunction, url)
        return

    log(cConfig().getLocalizedString(30166) + " -> [xstream]: Call function '%s' from '%s'" % (sFunction, sSiteName), LOGNOTICE)
    # If the hoster gui is called, run the function on it and return
    if sSiteName == 'cHosterGui':
        showHosterGui(sFunction)
    # If global search is called
    elif sSiteName == 'globalSearch':
        # TMDb cards use the same provider search, but require exact title matching.
        # Only the manually entered global search uses substring matching.
        if params.getValue('searchMode') == 'tmdb':
            searchTMDB(params)
        else:
            searchterm = False
            if params.exist('searchterm'):
                searchterm = params.getValue('searchterm')
            searchGlobal(searchterm)
    elif sSiteName == 'xStream':
        oGui = cGui()
        oGui.openSettings()
        # resolves strange errors in the logfile
        #oGui.updateDirectory()
        oGui.setEndOfDirectory()
        xbmc.executebuiltin('Action(ParentDir)')
    # Resolver Einstellungen im Hauptmenü
    elif sSiteName == 'resolver':
        oGui = cGui()
        resolver.display_settings()
        # resolves strange errors in the logfile
        oGui.setEndOfDirectory()
        xbmc.executebuiltin('Action(ParentDir)')
    # Manuelles Update im Hauptmenü
    elif sSiteName == 'devUpdates':
        from resources.lib import updateManager
        updateManager.devUpdates()
    # Plugin Infos    
    elif sSiteName == 'pluginInfo':
        cPluginHandler().pluginInfo()
    # Changelog anzeigen    
    elif sSiteName == 'changelog':
        from resources.lib import tools
        tools.changelog()
    # Dev Warnung anzeigen
    elif sSiteName == 'devWarning':
        from resources.lib import tools
        tools.devWarning()
    # VoD Menü Site Name
    elif sSiteName == 'vod':
        vodGuiElements(sFunction)
    # Unterordner der Einstellungen   
    elif sSiteName == 'settings':
        oGui = cGui()
        for folder in settingsGuiElements():
            oGui.addFolder(folder)
        oGui.setEndOfDirectory()
    else:
        # Else load any other site as plugin and run the function
        plugin = __import__(sSiteName, globals(), locals())
        # Site-Icon als Standard-Fanart für alle GuiElemente dieser Site setzen
        if hasattr(plugin, 'SITE_FANART'):
            from resources.lib.gui.guiElement import cGuiElement
            cGuiElement.DEFAULT_FANART = plugin.SITE_FANART
        function = getattr(plugin, sFunction)
        function()


def showMainMenu(sFunction):
    ART = os.path.join(cConfig().getAddonInfo('path'), 'resources', 'art')
    addon_id = cConfig().getAddonInfo('id')
    start_time = time.time()
    # timeout for the startup status check = 60s
    while (startupStatus := cCache().get(addon_id + '_main', -1)) != 'finished' and time.time() - start_time <= 60:
        time.sleep(5)
    
    oGui = cGui()

    # Setzte die globale Suche an erste Stelle
    if cConfig().getSetting('GlobalSearchPosition') == 'true':
        oGui.addFolder(globalSearchGuiElement())

    oPluginHandler = cPluginHandler()
    aPlugins = oPluginHandler.getAvailablePlugins()
    if not aPlugins:
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: No activated Plugins found', LOGNOTICE)
        # Open the settings dialog to choose a plugin that could be enabled
        oGui.openSettings()
        oGui.updateDirectory()
    else:
        # Create a gui element for every plugin found
        for aPlugin in sorted(aPlugins, key=lambda k: k['id']):
            if 'vod_' in aPlugin['id']:
                continue
            oGuiElement = cGuiElement()
            plugin_title = aPlugin['name']
            try:
                plugin_module = __import__(aPlugin['id'])
                plugin_domain = getattr(plugin_module, 'DOMAIN', '')
                if not plugin_domain:
                    from urllib.parse import urlparse
                    plugin_domain = urlparse(getattr(plugin_module, 'URL_MAIN', '')).netloc
                plugin_domain = str(plugin_domain).replace('https://', '').replace('http://', '').strip('/').lower()
                status = xbmcgui.Window(10000).getProperty('xstream.status.' + plugin_domain) if plugin_domain else ''
                if status:
                    plugin_title += ' [' + status + ']'
            except Exception:
                pass
            oGuiElement.setTitle(plugin_title)
            oGuiElement.setSiteName(aPlugin['id'])
            oGuiElement.setFunction(sFunction)
            if 'icon' in aPlugin and aPlugin['icon']:
                oGuiElement.setThumbnail(aPlugin['icon'])
                oGuiElement.setFanart(aPlugin['icon'])
            oGui.addFolder(oGuiElement)
        if cConfig().getSetting('GlobalSearchPosition') == 'false':
            oGui.addFolder(globalSearchGuiElement())
    # VoD-Ordner nur anzeigen, wenn mindestens ein VoD-Plugin aktiviert ist.
    if any(aPlugin['id'].startswith('vod_') for aPlugin in aPlugins):
        oGuiElement = cGuiElement()
        oGuiElement.setTitle(cConfig().getLocalizedString(30412))
        oGuiElement.setSiteName('vod')
        oGuiElement.setFunction(sFunction)
        oGuiElement.setThumbnail(os.path.join(ART, 'vod.png'))
        oGuiElement.setIcon(os.path.join(ART, 'settings.png'))
        oGui.addFolder(oGuiElement)

    if cConfig().getSetting('SettingsFolder') == 'true':
        # Einstellung im Menü mit Untereinstellungen
        oGuiElement = cGuiElement()
        oGuiElement.setTitle(cConfig().getLocalizedString(30041))
        oGuiElement.setSiteName('settings')
        oGuiElement.setFunction('showSettingsFolder')
        oGuiElement.setThumbnail(os.path.join(ART, 'settings.png'))
        oGui.addFolder(oGuiElement)
    else:
        for folder in settingsGuiElements():
            oGui.addFolder(folder)
    oGui.setEndOfDirectory()


def vodGuiElements(sFunction): # Vod Menü
    oGui = cGui()
    oPluginHandler = cPluginHandler()
    aPlugins = oPluginHandler.getAvailablePlugins() # Suche Plugins mit Pluginhandler
    if not aPlugins:
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: No activated Vod Plugins found', LOGNOTICE)
        # Öffne Einstellungen wenn keine VoD SitePlugins vorhanden
        oGui.openSettings()
        oGui.updateDirectory()
    else:
        # Erstelle ein gui element für alle gefundenen Siteplugins
        for aPlugin in sorted(aPlugins, key=lambda k: k['id']):
            #if cConfig().getSetting('indexVoDyes') == 'true': # Wenn VoD Menü True
            oGuiElement = cGuiElement()
            oGuiElement.setTitle(aPlugin['name'])
            oGuiElement.setSiteName(aPlugin['id'])
            if not 'vod_' in aPlugin['id']: continue # Blende alle SitePlugins ohne vod_ am Anfang aus
            oGuiElement.setFunction(sFunction)
            if 'icon' in aPlugin and aPlugin['icon']:
                oGuiElement.setThumbnail(aPlugin['icon'])
            oGui.addFolder(oGuiElement)
    oGui.setEndOfDirectory()

def showSystemStatus():
    lines = []
    try:
        import resolveurl
        version = getattr(resolveurl, '__version__', '') or cConfig(addon_id='script.module.resolveurl').getAddonInfo('version')
        lines.append('ResolveURL: OK' + ((' (' + str(version) + ')') if version else ''))
    except Exception:
        lines.append('ResolveURL: FEHLER')
    for module_name, label in [('kodi_six', 'kodi-six'), ('six', 'six'), ('pyqrcode', 'pyqrcode')]:
        try:
            __import__(module_name)
            lines.append(label + ': OK')
        except Exception:
            lines.append(label + ': FEHLER')
    try:
        import resolveurl
        dropload_ok = bool(resolveurl.relevant_resolvers(domain='dr0pstream.com') or resolveurl.relevant_resolvers(domain='dropload.io'))
        lines.append('Dropload Resolver: ' + ('OK' if dropload_ok else 'NICHT GEFUNDEN'))
    except Exception:
        lines.append('Dropload Resolver: FEHLER')
    xbmcgui.Dialog().textviewer(cConfig().getLocalizedString(30825), '\n'.join(lines))

def settingsGuiElements():
    ART = os.path.join(cConfig().getAddonInfo('path'), 'resources', 'art')

    # GUI Plugin Informationen
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30267))
    oGuiElement.setSiteName('pluginInfo')
    oGuiElement.setFunction('pluginInfo')
    oGuiElement.setThumbnail(os.path.join(ART, 'plugin_info.png'))
    PluginInfo = oGuiElement


    # GUI Systemstatus
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30825))
    oGuiElement.setSiteName('systemStatus')
    oGuiElement.setFunction('systemStatus')
    oGuiElement.setThumbnail(os.path.join(ART, 'plugin_info.png'))
    SystemStatus = oGuiElement

    # GUI xStream Einstellungen
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30042))
    oGuiElement.setSiteName('xStream')
    oGuiElement.setFunction('display_settings')
    oGuiElement.setThumbnail(os.path.join(ART, 'xstream_settings.png'))
    xStreamSettings = oGuiElement

    # GUI Resolver Einstellungen
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30043))
    oGuiElement.setSiteName('resolver')
    oGuiElement.setFunction('display_settings')
    oGuiElement.setThumbnail(os.path.join(ART, 'resolveurl_settings.png'))
    resolveurlSettings = oGuiElement
    
    # GUI Nightly Updatemanager
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30121))
    oGuiElement.setSiteName('devUpdates')
    oGuiElement.setFunction('devUpdates')
    oGuiElement.setThumbnail(os.path.join(ART, 'manuel_update.png'))
    DevUpdateMan = oGuiElement
    return PluginInfo, SystemStatus, xStreamSettings, resolveurlSettings, DevUpdateMan


def globalSearchGuiElement():
    ART = os.path.join(cConfig().getAddonInfo('path'), 'resources', 'art')

    # Create a gui element for global search
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30040))
    oGuiElement.setSiteName('globalSearch')
    oGuiElement.setFunction('globalSearch')
    oGuiElement.setThumbnail(os.path.join(ART, 'search.png'))
    return oGuiElement


def showHosterGui(sFunction):
    from resources.lib.gui.hoster import cHosterGui
    oHosterGui = cHosterGui()
    function = getattr(oHosterGui, sFunction)
    function()
    return True


def _filterGlobalResults(results, searchText, searchYear=None, searchImdbId=None, partialMatch=False):
    """Filter titles; optionally allow substrings only for the free global search."""
    import re
    import unicodedata

    def normalized(value):
        value = re.sub(r'\[[^\]]*\]', ' ', str(value or ''))
        value = unicodedata.normalize('NFKD', value)
        value = ''.join(ch for ch in value if not unicodedata.combining(ch))
        return ' '.join(re.findall(r'[^\W_]+', value.casefold(), re.UNICODE))

    def title_and_year(value):
        value = str(value or '').strip()
        # Scraper may append quality flags and use "Title - (Year)".
        # Remove only trailing technical tags, preserving genuine title text.
        value = re.sub(r'(?:\s*\[(?:HD|SD|FHD|UHD|4K|720p|1080p|2160p|WEB[- .]?DL|WEB[- .]?Rip|BluRay|BDRip|HDRip|CAM|TS|DVDRip)(?:[^\]]*)\]\s*)+$', '', value, flags=re.I).strip()
        match = re.search(r'\s*[-–]?\s*\((19\d{2}|20\d{2})\)\s*$', value)
        if match:
            return value[:match.start()].strip(' -–'), match.group(1)
        return value, None

    wanted, embedded_year = title_and_year(searchText)
    wanted = normalized(wanted)
    year = str(searchYear or embedded_year or '').strip()
    filtered = []
    for result in results:
        item = result['guiElement']
        title, title_year = title_and_year(item.getTitle())
        candidate = normalized(title)
        if (wanted not in candidate) if partialMatch else (candidate != wanted):
            continue
        item_year = str(getattr(item, '_sYear', '') or title_year or '').strip()
        if year and item_year and item_year != year:
            continue
        if searchImdbId:
            imdb = item.getItemProperties().get('imdbID')
            if imdb and imdb != searchImdbId:
                continue
        filtered.append(result)
    return filtered


def searchGlobal(sSearchText=False):
    import threading
    oGui = cGui()
    oGui.globalSearch = True
    oGui._collectMode = True
    if not sSearchText:
        sSearchText = oGui.showKeyBoard(sHeading=cConfig().getLocalizedString(30280)) # Bitte Suchbegriff eingeben
    if not sSearchText: 
        oGui.setEndOfDirectory()
        return True
    aPlugins = []
    aPlugins = cPluginHandler().getAvailablePlugins()
    dialog = xbmcgui.DialogProgress()
    dialog.create(cConfig().getLocalizedString(30122), cConfig().getLocalizedString(30123))
    numPlugins = len(aPlugins)
    threads = []
    for count, pluginEntry in enumerate(aPlugins):
        if pluginEntry['globalsearch'] == 'false':
            continue
        if pluginEntry['globalsearch'] == '': # Wenn die Globale Suche im Siteplugin direkt auf False gesetzt ist "SITE_GLOBAL_SEARCH = False" und in der settings.xml der Eintrag fehlt.
            continue
        dialog.update((count + 1) * 50 // numPlugins, cConfig().getLocalizedString(30124) + str(pluginEntry['name']) + '...')
        if dialog.iscanceled(): 
            oGui.setEndOfDirectory()
            return
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Searching for %s at %s' % (sSearchText, pluginEntry['id']), LOGNOTICE)
        t = threading.Thread(target=_pluginSearch, args=(pluginEntry, sSearchText, oGui), name=pluginEntry['name'])
        threads += [t]
        t.start()

    # Fortschritt anhand der wirklich noch laufenden Such-Threads anzeigen.
    # Die Anbieter suchen weiterhin parallel; die normale Suchlogik bleibt gleich.
    import time
    total_threads = len(threads)
    # Mehrere Anbieter laufen parallel. Einen tatsaechlich aktiven Anbieter
    # reihum anzeigen, statt den Eindruck einer sequenziellen Suche zu erwecken.
    display_index = 0
    last_display_change = 0
    displayed_provider = None
    while any(t.is_alive() for t in threads):
        if dialog.iscanceled():
            # Bereits gestartete Threads nicht durch ein blockierendes join() aufhalten.
            oGui.setEndOfDirectory()
            return
        active = [t.name for t in threads if t.is_alive()]
        finished = total_threads - len(active)
        percent = 50 + (finished * 50 // total_threads) if total_threads else 100
        now = time.monotonic()
        if displayed_provider not in active or now - last_display_change >= 1.0:
            if active:
                if displayed_provider in active and len(active) > 1:
                    display_index = (active.index(displayed_provider) + 1) % len(active)
                else:
                    display_index %= len(active)
                displayed_provider = active[display_index]
            else:
                displayed_provider = None
            last_display_change = now
        dialog.update(percent, 'Aktive Indexseite: %s\nNoch %d von %d Anbietern aktiv (parallele Suche)' %
                      (displayed_provider or '-', len(active), total_threads))
        time.sleep(0.2)
    for t in threads:
        t.join()
    dialog.update(100, 'Alle %d Anbieter durchsucht' % total_threads)
    dialog.close()
    # deactivate collectMode attribute because now we want the elements really added
    oGui._collectMode = False
    oGui.searchResults = _filterGlobalResults(oGui.searchResults, sSearchText, partialMatch=True)
    total = len(oGui.searchResults)
    dialog = xbmcgui.DialogProgress()
    dialog.create(cConfig().getLocalizedString(30126), cConfig().getLocalizedString(30127))
    for count, result in enumerate(sorted(oGui.searchResults, key=lambda k: k['guiElement'].getSiteName()), 1):
        if dialog.iscanceled(): 
            oGui.setEndOfDirectory()
            return
        oGui.addFolder(result['guiElement'], result['params'], bIsFolder=result['isFolder'], iTotal=total)
        dialog.update(count * 100 // total, str(count) + cConfig().getLocalizedString(30128) + str(total) + ': ' + result['guiElement'].getTitle())
    dialog.close()
    oGui.setView()
    oGui.setEndOfDirectory()
    return True


def searchAlter(params):
    searchTitle = params.getValue('searchTitle')
    searchImdbId = params.getValue('searchImdbID')
    searchYear = params.getValue('searchYear')
    # Wenn sYear im searchTitle vorhanden
    if ' (19' in searchTitle or ' (20' in searchTitle:
        isMatch, aYear = cParser.parse(searchTitle, '(.*?) \((\d{4})\)')
        if isMatch:
            searchTitle = aYear[0][0]
            # Wenn kein Jahr vorhanden nutze Jahr aus searchTitle
            if searchYear is False:
                searchYear = str(aYear[0][1])
            #searchYear(aYear[0][1])
    # Wenn zusätzlich Staffel oder Episoden Markierungen im Titel sind dann abschneiden
    if ' S0' in searchTitle or ' E0' in searchTitle or ' - Staffel' in searchTitle or ' Staffel' in searchTitle:
        if ' S0' in searchTitle:
            searchTitle = searchTitle.split(' S0')[0].strip()
        elif ' E0' in searchTitle:
            searchTitle = searchTitle.split(' E0')[0].strip()
        elif ' - Staffel' in searchTitle:
            searchTitle = searchTitle.split(' - Staffel')[0].strip()
        elif ' Staffel' in searchTitle:
            searchTitle = searchTitle.split(' Staffel')[0].strip()

    import threading
    oGui = cGui()
    oGui.globalSearch = True
    oGui._collectMode = True
    aPlugins = []
    aPlugins = cPluginHandler().getAvailablePlugins()
    dialog = xbmcgui.DialogProgress()
    dialog.create(cConfig().getLocalizedString(30122), cConfig().getLocalizedString(30123))
    numPlugins = len(aPlugins)
    threads = []
    for count, pluginEntry in enumerate(aPlugins):
        if pluginEntry['globalsearch'] == 'false':
            continue
        if pluginEntry['globalsearch'] == '': # Wenn die Globale Suche im Siteplugin direkt auf False gesetzt ist "SITE_GLOBAL_SEARCH = False" und in der settings.xml der Eintrag fehlt.
            continue
        if dialog.iscanceled(): 
            oGui.setEndOfDirectory()
            return
        dialog.update((count + 1) * 50 // numPlugins, cConfig().getLocalizedString(30124) + str(pluginEntry['name']) + '...')
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Searching for ' + searchTitle + pluginEntry['id'], LOGNOTICE)
        t = threading.Thread(target=_pluginSearch, args=(pluginEntry, searchTitle, oGui), name=pluginEntry['name'])
        threads += [t]
        t.start()
    # Fortschritt wie bei der globalen Suche anhand aktiver Threads anzeigen.
    import time
    total_threads = len(threads)
    display_index = 0
    last_display_change = 0
    displayed_provider = None
    while any(t.is_alive() for t in threads):
        if dialog.iscanceled():
            oGui.setEndOfDirectory()
            return
        active = [t.name for t in threads if t.is_alive()]
        finished = total_threads - len(active)
        percent = 50 + (finished * 50 // total_threads) if total_threads else 100
        now = time.monotonic()
        if displayed_provider not in active or now - last_display_change >= 1.0:
            if active:
                if displayed_provider in active and len(active) > 1:
                    display_index = (active.index(displayed_provider) + 1) % len(active)
                else:
                    display_index %= len(active)
                displayed_provider = active[display_index]
            else:
                displayed_provider = None
            last_display_change = now
        dialog.update(percent, 'Aktive Indexseite: %s\nNoch %d von %d Anbietern aktiv (parallele Suche)' %
                      (displayed_provider or '-', len(active), total_threads))
        time.sleep(0.2)
    for t in threads:
        t.join()
    dialog.update(100, 'Alle %d Anbieter durchsucht' % total_threads)
    dialog.close()
    filteredResults = _filterGlobalResults(oGui.searchResults, searchTitle, searchYear, searchImdbId)
    oGui._collectMode = False
    total = len(filteredResults)
    for result in sorted(filteredResults, key=lambda k: k['guiElement'].getSiteName()):
        oGui.addFolder(result['guiElement'], result['params'], bIsFolder=result['isFolder'], iTotal=total)
    oGui.setView()
    oGui.setEndOfDirectory()
    xbmc.executebuiltin('Container.Update')
    return True


def searchTMDB(params):
    sSearchText = params.getValue('searchTitle')
    import threading
    oGui = cGui()
    oGui.globalSearch = True
    oGui._collectMode = True
    if not sSearchText: 
        oGui.setEndOfDirectory()
        return True
    aPlugins = []
    aPlugins = cPluginHandler().getAvailablePlugins()
    dialog = xbmcgui.DialogProgress()
    dialog.create(cConfig().getLocalizedString(30122), cConfig().getLocalizedString(30123))
    numPlugins = len(aPlugins)
    threads = []
    for count, pluginEntry in enumerate(aPlugins):
        if pluginEntry['globalsearch'] == 'false':
            continue
        if dialog.iscanceled(): 
            oGui.setEndOfDirectory()
            return
        dialog.update((count + 1) * 50 // numPlugins, cConfig().getLocalizedString(30124) + str(pluginEntry['name']) + '...')
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Searching for %s at %s' % (sSearchText, pluginEntry['id']), LOGNOTICE)

        t = threading.Thread(target=_pluginSearch, args=(pluginEntry, sSearchText, oGui), name=pluginEntry['name'])
        threads += [t]
        t.start()
    # Fortschritt wie bei der globalen Suche anhand aktiver Threads anzeigen.
    import time
    total_threads = len(threads)
    display_index = 0
    last_display_change = 0
    displayed_provider = None
    while any(t.is_alive() for t in threads):
        if dialog.iscanceled():
            oGui.setEndOfDirectory()
            return
        active = [t.name for t in threads if t.is_alive()]
        finished = total_threads - len(active)
        percent = 50 + (finished * 50 // total_threads) if total_threads else 100
        now = time.monotonic()
        if displayed_provider not in active or now - last_display_change >= 1.0:
            if active:
                if displayed_provider in active and len(active) > 1:
                    display_index = (active.index(displayed_provider) + 1) % len(active)
                else:
                    display_index %= len(active)
                displayed_provider = active[display_index]
            else:
                displayed_provider = None
            last_display_change = now
        dialog.update(percent, 'Aktive Indexseite: %s\nNoch %d von %d Anbietern aktiv (parallele Suche)' %
                      (displayed_provider or '-', len(active), total_threads))
        time.sleep(0.2)
    for t in threads:
        t.join()
    dialog.update(100, 'Alle %d Anbieter durchsucht' % total_threads)
    dialog.close()
    # deactivate collectMode attribute because now we want the elements really added
    oGui._collectMode = False
    oGui.searchResults = _filterGlobalResults(oGui.searchResults, sSearchText, params.getValue('searchYear'))
    total = len(oGui.searchResults)
    dialog = xbmcgui.DialogProgress()
    dialog.create(cConfig().getLocalizedString(30126), cConfig().getLocalizedString(30127))
    for count, result in enumerate(sorted(oGui.searchResults, key=lambda k: k['guiElement'].getSiteName()), 1):
        if dialog.iscanceled(): 
            oGui.setEndOfDirectory()
            return
        oGui.addFolder(result['guiElement'], result['params'], bIsFolder=result['isFolder'], iTotal=total)
        dialog.update(count * 100 // total, str(count) + cConfig().getLocalizedString(30128) + str(total) + ': ' + result['guiElement'].getTitle())
    dialog.close()
    oGui.setView()
    oGui.setEndOfDirectory()
    return True


def _pluginSearch(pluginEntry, sSearchText, oGui):
    try:
        plugin = __import__(pluginEntry['id'], globals(), locals())
        function = getattr(plugin, '_search')
        function(oGui, sSearchText)
    except Exception:
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: ' + pluginEntry['name'] + ': search failed', LOGERROR)
        import traceback
        log(traceback.format_exc())