# -*- coding: utf-8 -*-
# Python 3

import json
import os
import sys
import xbmc

from resources.lib.config import cConfig
from xbmc import LOGINFO as LOGNOTICE, LOGERROR, log
from resources.lib import utils
from resources.lib.handler.requestHandler import cRequestHandler
from xbmcgui import Dialog
from xbmcvfs import translatePath
from resources.lib.tools import platform, getDNS, getRepofromAddonsDB


ADDON_PATH = translatePath(os.path.join('special://home/addons/', '%s'))

class cPluginHandler:
    def __init__(self):
        self.rootFolder = translatePath(cConfig().getAddonInfo('path'))
        self.settingsFile = os.path.join(self.rootFolder, 'resources', 'settings.xml')
        self.profilePath = translatePath(cConfig().getAddonInfo('profile'))
        self.pluginDBFile = os.path.join(self.profilePath, 'pluginDB')

        log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: profile folder: %s' % self.profilePath, LOGNOTICE)
        log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: root folder: %s' % self.rootFolder, LOGNOTICE)
        self.defaultFolder = os.path.join(self.rootFolder, 'sites')
        log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: default sites folder: %s' % self.defaultFolder, LOGNOTICE)


    def getAvailablePlugins(self):
        global globalSearchStatus
        pluginDB = self.__getPluginDB()
        # default plugins
        update = False
        fileNames = self.__getFileNamesFromFolder(self.defaultFolder)
        for fileName in fileNames:
            plugin = {'name': '', 'identifier': '', 'icon': '', 'domain': '', 'globalsearch': '', 'modified': 0}
            if fileName in pluginDB:
                plugin.update(pluginDB[fileName])
            try:
                modTime = os.path.getmtime(os.path.join(self.defaultFolder, fileName + '.py'))
            except OSError:
                modTime = 0
            try:
                globalSearchStatus = cConfig().getSetting('global_search_' + fileName)
            except Exception:
                pass
            if fileName not in pluginDB or modTime > plugin['modified'] or globalSearchStatus:
                log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: load plugin Informations for ' + str(fileName), LOGNOTICE)
                # try to import plugin
                pluginData = self.__getPluginData(fileName, self.defaultFolder)
                if pluginData:
                    pluginData['globalsearch'] = globalSearchStatus
                    pluginData['modified'] = modTime # Wenn Datei (Zeitstempel) verändert, werden die Daten aktualisiert
                    pluginDB[fileName] = pluginData
                    update = True
        # check pluginDB for obsolete entries
        deletions = []
        for pluginID in pluginDB:
            if pluginID not in fileNames:
                deletions.append(pluginID)
        for id in deletions:
            del pluginDB[id]
        if update or deletions:
            self.__updateSettings(pluginDB)
            log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: settings.xml informations updated.', LOGNOTICE)
            self.__updatePluginDB(pluginDB) # Aktualisiert PluginDB in Addon_data
            log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: PluginDB informations updated.', LOGNOTICE)
        return self.getAvailablePluginsFromDB()


    def getAvailablePluginsFromDB(self):
        plugins = []
        iconFolder = os.path.join(self.rootFolder, 'resources', 'art', 'sites')
        pluginDB = self.__getPluginDB() # Erstelle PluginDB
        # PluginID = Siteplugin Name
        for pluginID in pluginDB:
            plugin = pluginDB[pluginID] # Aus PluginDB lese PluginID
            pluginSettingsName = 'plugin_%s' % pluginID # Name des Siteplugins
            plugin['id'] = pluginID
            if 'icon' in plugin:
                plugin['icon'] = os.path.join(iconFolder, plugin['icon'])
            else:
                plugin['icon'] = ''
            # existieren zu diesem plugin die an/aus settings
            if cConfig().getSetting(pluginSettingsName) == 'true': # Lese aus settings.xml welche Plugins eingeschaltet sind
                plugins.append(plugin)
        return plugins


    def __updatePluginDB(self, data): # Aktualisiere PluginDB
        if not os.path.exists(self.profilePath):
            os.makedirs(self.profilePath)
        file = open(self.pluginDBFile, 'w')
        json.dump(data, file)
        file.close()


    def __getPluginDB(self): # Erstelle PluginDB
        if not os.path.exists(self.pluginDBFile): # Wenn Datei nicht verfügbar dann erstellen
            return dict()
        file = open(self.pluginDBFile, 'r')
        try:
            data = json.load(file)
        except ValueError:
            log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: pluginDB seems corrupt, creating new one', LOGERROR)
            data = dict()
        file.close()
        return data

    def __updateSettings(self, pluginDB):
        """
        Aktualisiert die settings.xml basierend auf den verfügbaren Plugins.
        Entfernt Plugins, die nicht mehr existieren, und behält die saubere Formatierung bei.

        Args:
            pluginDB: Dictionary mit Plugin-Informationen
        """
        #import traceback
        from resources.lib.handler.xmlHandler import cXmlHandler

        if not os.path.exists(self.settingsFile):
            return

        try:
            available_plugins = [p for p in pluginDB.keys() if p != 'globalSearch'] 
            
            xmlTree, xmlRoot = cXmlHandler.read_xml(self.settingsFile)

            groups_deleted = cXmlHandler.delete_groups_from_categories(xmlRoot, ['indexsite1', 'indexsite2', 'indexsiteVoD'], available_plugins)
 
            fileNames = self.__getFileNamesFromFolder(self.defaultFolder)
            settings_dict = {}
            for fileName in fileNames:
                pluginData = self.__getPluginData(fileName, self.defaultFolder)
                if pluginData and 'identifier' in pluginData and 'settings' in pluginData:
                    settings_dict[pluginData['identifier']] = pluginData['settings']
                    
            groups_synced = cXmlHandler.sync_group_from_scraper_settings(xmlRoot, settings_dict, ['indexsite1', 'indexsite2', 'indexsiteVoD'])
            
            if groups_deleted or groups_synced:
                cXmlHandler.write_xml(xmlTree, self.settingsFile)
                log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: settings.xml updated successfully.', LOGNOTICE)

        except Exception as e:
            log(cConfig().getLocalizedString(30166) + f' -> [pluginHandler]: Error on updating settings.xml: {str(e)}', LOGERROR)
            #xbmc.log(traceback.format_exc(), LOGERROR)

    def __getFileNamesFromFolder(self, sFolder): # Hole Namen vom Dateiname.py
        aNameList = []
        items = os.listdir(sFolder)
        for sItemName in items:
            if sItemName.endswith('.py'):
                sItemName = os.path.basename(sItemName[:-3])
                aNameList.append(sItemName)
        return aNameList


    def __getPluginData(self, fileName, defaultFolder): # Hole Plugin Daten aus dem Siteplugin
        pluginData = {}
        if not defaultFolder in sys.path: sys.path.append(defaultFolder)
        try:
            plugin = __import__(fileName, globals(), locals())
            pluginData['name'] = plugin.SITE_NAME
        except Exception as e:
            log(cConfig().getLocalizedString(30166) + " -> [pluginHandler]: Can't import plugin: %s" % fileName, LOGERROR)
            return False
        try:
            pluginData['identifier'] = plugin.SITE_IDENTIFIER
        except Exception:
            pass
        try:
            pluginData['icon'] = plugin.SITE_ICON
        except Exception:
            pass
        try:
            pluginData['domain'] = plugin.DOMAIN
        except Exception:
            pass
        try:
            pluginData['settings'] = plugin.SCRAPER_SETTINGS
        except Exception:
            pass
        try:
            pluginData['globalsearch'] = plugin.SITE_GLOBAL_SEARCH
        except Exception:
            pluginData['globalsearch'] = True
            pass
        return pluginData


    def __getPluginDataIndex(self, fileName, defaultFolder): # Hole Plugin Daten aus dem Siteplugin
        pluginData = {}
        if not defaultFolder in sys.path: sys.path.append(defaultFolder)
        try:
            plugin = __import__(fileName, globals(), locals())
            pluginData['name'] = plugin.SITE_NAME
        except Exception as e:
            log(cConfig().getLocalizedString(30166) + " -> [pluginHandler]: Can't import plugin: %s" % fileName, LOGERROR)
            return False
        try:
            pluginData['active'] = plugin.ACTIVE
        except Exception:
            pass
        try:
            pluginData['domain'] = plugin.DOMAIN
        except Exception:
            pass
        try:
            pluginData['status'] = plugin.STATUS
            if '403' <= pluginData['status'] <= '503':
                pluginData['status'] = pluginData['status'] + ' - ' + cConfig().getLocalizedString(30429)
            elif '300' <= pluginData['status'] <= '400':
                pluginData['status'] = pluginData['status'] + ' - ' + cConfig().getLocalizedString(30428)
            elif pluginData['status'] == '200':
                pluginData['status'] = pluginData['status'] + ' - ' + cConfig().getLocalizedString(30427)
        except Exception:
            pass
        try:
            pluginData['globalsearch'] = plugin.SITE_GLOBAL_SEARCH
        except Exception:
            pluginData['globalsearch'] = True
            pass
        return pluginData


    def __getPluginDataDomain(self, fileName, defaultFolder): # Hole Plugin Daten für Domains
        pluginDataDomain = {}
        if not defaultFolder in sys.path: sys.path.append(defaultFolder)
        try:
            plugin = __import__(fileName, globals(), locals())
            pluginDataDomain['identifier'] = plugin.SITE_IDENTIFIER
        except Exception as e:
            log(cConfig().getLocalizedString(30166) + " -> [pluginHandler]: Can't import plugin: %s" % fileName, LOGERROR)
            return False
        try:
            pluginDataDomain['domain'] = plugin.DOMAIN
        except Exception:
            pass
        return pluginDataDomain

    # Plugin Support Informationen
    def pluginInfo(self):
        # Erstelle Liste mit den Indexseiten Informationen
        list_of_plugins = []
        fileNames = self.__getFileNamesFromFolder(self.defaultFolder) # Hole Plugins aus xStream
        for fileName in fileNames:
            pluginData = self.__getPluginDataIndex(fileName, self.defaultFolder) # Hole Plugin Daten
            list_of_plugins.append(pluginData)
        result_list = [''.join([f"{key}:  {value}\n" for key, value in dictionary.items()]) for dictionary in list_of_plugins]
        # String Übersetzungen
        result_string = '\n'.join(result_list)
        result_string = result_string.replace('name', cConfig().getLocalizedString(30423))
        result_string = result_string.replace('active', cConfig().getLocalizedString(30430))
        result_string = result_string.replace('domain', cConfig().getLocalizedString(30424))
        result_string = result_string.replace('status', cConfig().getLocalizedString(30425))
        result_string = result_string.replace('globalsearch', cConfig().getLocalizedString(30426))
        result_string = result_string.replace('True', cConfig().getLocalizedString(30418))
        result_string = result_string.replace('False', cConfig().getLocalizedString(30419))
        result_string = result_string.replace('true', cConfig().getLocalizedString(30418))
        result_string = result_string.replace('false', cConfig().getLocalizedString(30419))
        list_of_PluginData = (result_string) # Ergebnis der Liste
        # Settings Abragen
        if cConfig().getSetting('githubUpdateResolver') == 'true':  # Resolver Update An/Aus
            UPDATERU = cConfig().getLocalizedString(30415)  # Aktiv
        else:
            UPDATERU = cConfig().getLocalizedString(30416)  # Inaktiv
        if cConfig().getSetting('bypassDNSlock') == 'true':  # DNS Bypass
            BYPASS = cConfig().getLocalizedString(30418)  # Aktiv
        else:
            BYPASS = cConfig().getLocalizedString(30419)  # Inaktiv
        if os.path.exists(ADDON_PATH % 'repository.resolveurl'):
            RESOLVEURL = cConfig('repository.resolveurl').getAddonInfo('name') + ':  ' + cConfig('repository.resolveurl').getAddonInfo('id') + ' - ' + cConfig('repository.resolveurl').getAddonInfo('version') + '\n'
        else:
            RESOLVEURL = ''

        # Support Informationen anzeigen
        Dialog().textviewer(cConfig().getLocalizedString(30265),
            cConfig().getLocalizedString(30413) + '\n'  # Geräte Informationen
            + 'Kodi Version:  ' + xbmc.getInfoLabel('System.BuildVersion')[:4] + ' (Code Version: ' + xbmc.getInfoLabel('System.BuildVersionCode') + ')' + '\n'  # Kodi Version
            + cConfig().getLocalizedString(30266) + '   {0}'.format(platform().title()) + '\n'  # System Plattform
            + '\n'  # Absatz
            + cConfig().getLocalizedString(30414) + '\n'  # Plugin Informationen
            + cConfig().getAddonInfo('name') + ' Version:  ' + cConfig().getAddonInfo('id') + ' - ' + cConfig().getAddonInfo('version') + '\n'  # xStream ID und Version
            + cConfig('script.module.resolveurl').getAddonInfo('name') + ' Version:  ' + cConfig('script.module.resolveurl').getAddonInfo('id') + ' - ' + cConfig('script.module.resolveurl').getAddonInfo('version') + '\n'  # Resolver ID und Version
            + cConfig('script.module.resolveurl').getAddonInfo('name') + ' Status:  ' + UPDATERU + cConfig().getSettingString('resolver.branch') + '\n'  # Resolver Update Status und Branch
            + cConfig().getLocalizedString(30435) + ' ' + getRepofromAddonsDB(cConfig().getAddonInfo('id')) + '\n' # Repo-Info
            + '\n'  # Absatz
            + cConfig().getLocalizedString(30420) + '\n'  # DNS Informationen
            + cConfig().getLocalizedString(30417) + ' ' + BYPASS + '\n'  # xStream DNS Bypass aktiv/inaktiv
            + cConfig().getLocalizedString(30434) + '1' + ' ' + getDNS('Network.DNS1Address') + '\n' # DNS Nameserver 1
            + cConfig().getLocalizedString(30434) + '2' + ' ' + getDNS('Network.DNS2Address') + '\n' # DNS Nameserver 2
            + '\n'  # Absatz
            + cConfig().getLocalizedString(30421) + '\n'  # Repo Informationen
            + cConfig('repository.xstream').getAddonInfo('name') + ':  ' + cConfig('repository.xstream').getAddonInfo('id') + ' - ' + cConfig('repository.xstream').getAddonInfo('version') + '\n'  # xStream Repository ID und Version
            + RESOLVEURL
            + '\n'  # Absatz
            + cConfig().getLocalizedString(30422) + '\n'  # Indexseiten Informationen
            + list_of_PluginData # Liste mit den Indexseiten Informationen
            )


