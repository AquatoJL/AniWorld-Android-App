# -*- coding: utf-8 -*-
# Python 3
#
# 24.01.23 - Heptamer: Korrektur getpriorities (nun werden alle Hoster gelesen und sortiert)
# 22.12.24 - Heptamer: m3u8 und mpd Files über inputstream adaptive abspielen lassen

import xbmc
import xbmcgui 
import xbmcplugin
from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.gui.gui import cGui
from resources.lib.config import cConfig
from resources.lib.player import cPlayer
from resources.lib.tools import logger


class cHosterGui:
    SITE_NAME = 'cHosterGui'

    def __init__(self):
        self.maxHoster = int(cConfig().getSetting('maxHoster', 100))
        self.dialog = False
        self._silentResolveErrors = False

    # TODO: unify parts of play, download etc.
    def _getInfoAndResolve(self, siteResult):
        oGui = cGui()
        params = ParameterHandler()
        # get data
        mediaUrl = params.getValue('sMediaUrl')
        fileName = params.getValue('MovieTitle')
        try:
            try:
                import resolveurl as resolver
            except:
                import urlresolver as resolver
            # resolve
            if siteResult:
                mediaUrl = siteResult.get('streamUrl', False)
                mediaId = siteResult.get('streamID', False)
                if mediaUrl:
                    logger.info('-> [hoster]: resolve: ' + mediaUrl)
                    link = mediaUrl if siteResult['resolved'] else resolver.resolve(mediaUrl)
                elif mediaId:
                    logger.info('-> [hoster]: resolve: hoster: %s - mediaID: %s' % (siteResult['host'], mediaId))
                    link = resolver.HostedMediaFile(host=siteResult['host'].lower(), media_id=mediaId).resolve()
                else:
                    if not self._silentResolveErrors:
                        oGui.showError('xStream', cConfig().getLocalizedString(30134), 5)
                    return False
            elif mediaUrl:
                logger.info('-> [hoster]: resolve: ' + mediaUrl)
                link = resolver.resolve(mediaUrl)
            else:
                if not self._silentResolveErrors:
                    oGui.showError('xStream', cConfig().getLocalizedString(30134), 5)
                return False
        except resolver.resolver.ResolverError as e:
            logger.error('-> [hoster]: ResolverError: %s' % e)
            if not self._silentResolveErrors:
                oGui.showError('xStream', cConfig().getLocalizedString(30135), 7)
            return False
        # resolver response
        if link is not False:
            data = {'title': fileName, 'season': params.getValue('season'), 'episode': params.getValue('episode'), 'showTitle': params.getValue('TVShowTitle'), 'thumb': params.getValue('thumb'), 'link': link}
            return data
        return False

    def play(self, siteResult=False):
        logger.info('-> [hoster]: attempt to play file')
        data = self._getInfoAndResolve(siteResult)
        if not data:
            return False
        if self.dialog:
            try:
                self.dialog.close()
            except:
                pass

        vers = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])

        logger.info('-> [hoster]: play file link: ' + str(data['link']))
        list_item = xbmcgui.ListItem(path=data['link'])
        #m3u8 und mpd via inputstream, exklusive Filemoon, da IA mit dem Hoster nicht unter Android läuft
        if not 'filemoon' in siteResult['streamUrl']:
            if '.m3u8' in data['link'] or '.mpd' in data['link']:
                list_item.setProperty("inputstream", "inputstream.adaptive")
                if '.mpd' in data['link']:
                    if vers < 21: list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
                    list_item.setMimeType('application/dash+xml')
                else:
                    if vers < 21: list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                    list_item.setMimeType("application/vnd.apple.mpegurl")
                if '|' in data['link']:
                    data['link'], header = data['link'].split('|')
                    list_item.setProperty('inputstream.adaptive.stream_headers', header)
                    if vers > 19: list_item.setProperty('inputstream.adaptive.manifest_headers', header)

        if 'youtube' in data['link']:
            import time
            time.sleep(1)
        info = {'Title': data['title']}
        if data['thumb']:
            list_item.setArt(data['thumb'])
        if data['showTitle']:
            info['Episode'] = data['episode']
            info['Season'] = data['season']
            info['TVShowTitle'] = data['showTitle']

        #Neuer Video-Tag, mit Kodi 19 nicht kompatibel, daher folgende Abfrage
        kodi_version = xbmc.getInfoLabel('System.BuildVersion')
        if kodi_version[:2] < '20':
            list_item.setInfo(type="Video", infoLabels=info)
        else:
            vtag = list_item.getVideoInfoTag()
            vtag.setMediaType('video')
            if 'Title' in info:
                try:
                    vtag.setTitle(str(info['Title']))
                except: pass
            if 'Season' in info:
                try:
                    vtag.setSeason(int(info['Season']))
                except: pass
            if 'Episode' in info:
                try:
                    vtag.setEpisode(int(info['Episode']))
                except: pass
            if 'TVShowTitle' in info:
                try:
                    vtag.setTvShowTitle(info['TVShowTitle'])
                except: pass

        list_item.setProperty('IsPlayable', 'true')
        if cGui().pluginHandle > 0:
            xbmcplugin.setResolvedUrl(cGui().pluginHandle, True, list_item)
        else:
            xbmc.Player().play(data['link'], list_item)
        return cPlayer().startPlayer()

    def addToPlaylist(self, siteResult=False):
        oGui = cGui()
        logger.info('-> [hoster]: attempt addToPlaylist')
        data = self._getInfoAndResolve(siteResult)
        if not data: return False
        logger.info('-> [hoster]: addToPlaylist file link: ' + str(data['link']))
        oGuiElement = cGuiElement()
        oGuiElement.setSiteName(self.SITE_NAME)
        oGuiElement.setMediaUrl(data['link'])
        oGuiElement.setTitle(data['title'])
        if data['thumb']:
            oGuiElement.setThumbnail(data['thumb'])
        if data['showTitle']:
            oGuiElement.setEpisode(data['episode'])
            oGuiElement.setSeason(data['season'])
            oGuiElement.setTVShowTitle(data['showTitle'])
        if self.dialog:
            self.dialog.close()
        oPlayer = cPlayer()
        oPlayer.addItemToPlaylist(oGuiElement)
        oGui.showInfo(cConfig().getLocalizedString(30136), cConfig().getLocalizedString(30137), 5)
        return True

    def download(self, siteResult=False):
        from resources.lib.download import cDownload
        logger.info('-> [hoster]: attempt download')
        data = self._getInfoAndResolve(siteResult)
        if not data: return False
        logger.info('-> [hoster]: download file link: ' + data['link'])
        if self.dialog:
            self.dialog.close()
        oDownload = cDownload()
        oDownload.download(data['link'], data['title'])
        return True

    def sendToPyLoad(self, siteResult=False):
        from resources.lib.handler.pyLoadHandler import cPyLoadHandler
        logger.info('-> [hoster]: attempt download with pyLoad')
        data = self._getInfoAndResolve(siteResult)
        if not data: return False
        cPyLoadHandler().sendToPyLoad(data['title'], data['link'])
        return True

    def sendToJDownloader(self, sMediaUrl=False):
        from resources.lib.handler.jdownloaderHandler import cJDownloaderHandler
        params = ParameterHandler()
        if not sMediaUrl:
            sMediaUrl = params.getValue('sMediaUrl')
        if self.dialog:
            self.dialog.close()
        logger.info('-> [hoster]: call send to JDownloader: ' + sMediaUrl)
        cJDownloaderHandler().sendToJDownloader(sMediaUrl)

    def sendToJDownloader2(self, sMediaUrl=False):
        from resources.lib.handler.jdownloader2Handler import cJDownloader2Handler
        params = ParameterHandler()
        if not sMediaUrl:
            sMediaUrl = params.getValue('sMediaUrl')
        if self.dialog:
            self.dialog.close()
        logger.info('-> [hoster]: call send to JDownloader2: ' + sMediaUrl)
        cJDownloader2Handler().sendToJDownloader2(sMediaUrl)

    def sendToMyJDownloader(self, sMediaUrl=False, sMovieTitle='xStream'):
        from resources.lib.handler.myjdownloaderHandler import cMyJDownloaderHandler
        params = ParameterHandler()
        if not sMediaUrl:
            sMediaUrl = params.getValue('sMediaUrl')
        sMovieTitle = params.getValue('MovieTitle')
        if not sMovieTitle:
            sMovieTitle = params.getValue('Title')
        if not sMovieTitle:  # only temporary
            sMovieTitle = params.getValue('sMovieTitle')
        if not sMovieTitle:
            sMovieTitle = params.getValue('title')
        if self.dialog:
            self.dialog.close()
        logger.info('-> [hoster]: call send to My.JDownloader: ' + sMediaUrl)
        cMyJDownloaderHandler().sendToMyJDownloader(sMediaUrl, sMovieTitle)

    def __getPriorities(self, hosterList, filter=True):
        # Sort hosters based on their resolvers priority.
        ranking = []
        # handles multihosters but is about 10 times slower
        for hoster in hosterList:

            # we try to load resolveurl within the loop, making sure that the resolver loads new with every cycle
            try:
                import resolveurl as resolver
            except:
                import urlresolver as resolver
                 
            # accept hoster which is marked as resolveable by sitePlugin
            if hoster.get('resolveable', False):
                ranking.append([0, hoster])
                continue
             
            try:
                # serienstream VOE hoster = {'link': [sUrl, sName], aus array "[0]" True bzw. False
                link = hoster['link'][0] if isinstance(hoster['link'], list) else hoster['link']
                hmf = resolver.HostedMediaFile(url=link)
                #hmf = resolver.HostedMediaFile(url=hoster['link'])
            except:
                continue

            if not hmf.valid_url():
                hmf = resolver.HostedMediaFile(host=hoster['name'].lower(), media_id='dummy')

            if len(hmf.get_resolvers()):
                priority = False
                for resolver in hmf.get_resolvers():
                    # prefer individual priority
                    if not resolver.isUniversal():
                        priority = resolver._get_priority()
                        break
                    if not priority:
                        priority = resolver._get_priority()
                if priority:
                    ranking.append([priority, hoster])
            elif not filter:
                ranking.append([999, hoster])

            # Reset resolver so we have a fresh instance when loop starts again
            del(resolver) 

        # Existing AutoPlay quality preference, made robust for site plugins that
        # expose the resolution either as quality="1080" or only in the label.
        try:
            import re
            pref_map = {'0': 240, '1': 360, '2': 480, '3': 720, '4': 1080}
            pref_setting = cConfig().getSetting('preferedQuality')
            target = pref_map.get(str(pref_setting))

            def get_quality(item):
                hoster = item[1]
                values = [hoster.get('quality', ''), hoster.get('displayedName', ''), hoster.get('name', '')]
                text = ' '.join(str(v) for v in values if v is not None)
                match = re.search(r'(?<!\d)(2160|1440|1080|720|576|540|480|360|240)\s*p?(?!\d)', text, re.I)
                if match:
                    return int(match.group(1))
                upper = text.upper()
                if 'UHD' in upper or '4K' in upper:
                    return 2160
                if 'FULLHD' in upper or 'FULL HD' in upper or 'FHD' in upper:
                    return 1080
                if 'HD' in upper:
                    return 720
                return 0

            if target is None:  # "Beste Qualität"
                ranking = sorted(ranking, key=lambda item: get_quality(item), reverse=True)
            else:
                # Requested quality first. Then lower resolutions, then higher
                # resolutions, and unknown quality as the final fallback.
                def quality_key(item):
                    quality = get_quality(item)
                    if quality == target:
                        return (0, 0)
                    if quality and quality < target:
                        return (1, target - quality)
                    if quality:
                        return (2, quality - target)
                    return (3, 0)
                ranking = sorted(ranking, key=quality_key)
        except Exception as e:
            logger.debug('-> [hoster]: quality sorting failed: %s' % e)
        # After sorting Quality, we sort for Hoster-Priority :) -Hep 24.01.23
        # ranking = sorted(ranking, key=lambda ranking: ranking[0])

        # Hoster Sprache über sLang im Siteplugin Prio nach sLang Code Reihenfolge (Deutsch, Englisch, Englisch mit untertitel
        if ranking:
            if  "languageCode" in ranking[0][1]:
                ranking = sorted(ranking, key=lambda ranking: (ranking[1]["languageCode"],ranking[0]))
            else:
                ranking = sorted(ranking, key=lambda ranking: ranking[0])
        
        
        hosterQueue = []
        
        for i, hoster in ranking:
            hosterQueue.append(hoster)
        return hosterQueue

    def stream(self, playMode, siteName, function, url):
        self.dialog = xbmcgui.DialogProgress()
        self.dialog.create('xStream', cConfig().getLocalizedString(30138))
        # load site as plugin and run the function
        self.dialog.update(5, cConfig().getLocalizedString(30139))
        plugin = __import__(siteName, globals(), locals())
        function = getattr(plugin, function)
        self.dialog.update(10, cConfig().getLocalizedString(30140))
        if url:
            siteResult = function(url)
        else:
            siteResult = function()
        self.dialog.update(40)
        if not siteResult:
            self.dialog.close()
            cGui().showInfo('xStream', cConfig().getLocalizedString(30141))
            return
        # if result is not a list, make in one
        if not type(siteResult) is list:
            temp = [siteResult]
            siteResult = temp
        # field "name" marks hosters
        if 'name' in siteResult[0]:
            functionName = siteResult[-1]
            del siteResult[-1]
            if not siteResult:
                self.dialog.close()
                cGui().showInfo('xStream', cConfig().getLocalizedString(30142))
                return

            self.dialog.update(60, cConfig().getLocalizedString(30143))
            # Sitplugins VOD mit in automatische Abspielliste aufnehmen (Da Links bei der Überprüfung der Verfügbarkeit gekickt werden)
            if (playMode != 'jd') and (playMode != 'jd2') and (playMode != 'pyload') and (cConfig().getSetting('presortHoster') == 'true') and (playMode != 'myjd'):
            #if (not siteName.startswith('vod_')) and (playMode != 'jd') and (playMode != 'jd2') and (playMode != 'pyload') and (cConfig().getSetting('presortHoster') == 'true') and (playMode != 'myjd'):
                siteResult = self.__getPriorities(siteResult)
            if not siteResult:
                self.dialog.close()
                cGui().showInfo('xStream', cConfig().getLocalizedString(30144))
                return False
            self.dialog.update(90)
            # self.dialog.close()
            if len(siteResult) > self.maxHoster:
                siteResult = siteResult[:self.maxHoster - 1]
            if cConfig().getSetting('hosterSelect') == 'List':
                self.showHosterFolder(siteResult, siteName, functionName)
                return
            if len(siteResult) > 1:
                # choose hoster
                siteResult = self._chooseHoster(siteResult)
                if not siteResult:
                    return
            else:
                siteResult = siteResult[0]
            # get stream links
            logger.info(siteResult['link'])
            function = getattr(plugin, functionName)
            siteResult = function(siteResult['link'])
            # if result is not a list, make in one
            if not type(siteResult) is list:
                temp = [siteResult]
                siteResult = temp
        # choose part
        if len(siteResult) > 1:
            siteResult = self._choosePart(siteResult)
            if not siteResult:
                logger.info('-> [hoster]: no part selected')
                return
        else:
            siteResult = siteResult[0]

        self.dialog = xbmcgui.DialogProgress()
        self.dialog.create('xStream', cConfig().getLocalizedString(30145))
        self.dialog.update(95, cConfig().getLocalizedString(30146))
        if playMode == 'play':
            self.play(siteResult)
        elif playMode == 'download':
            self.download(siteResult)
        elif playMode == 'enqueue':
            self.addToPlaylist(siteResult)
        elif playMode == 'jd':
            self.sendToJDownloader(siteResult['streamUrl'])
        elif playMode == 'jd2':
            self.sendToJDownloader2(siteResult['streamUrl'])
        elif playMode == 'myjd':
            self.sendToMyJDownloader(siteResult['streamUrl'])
        elif playMode == 'pyload':
            self.sendToPyLoad(siteResult)

    def streamAuto(self, playMode, siteName, function):
        # Existing xStream AutoPlay path. It deliberately remains separate from
        # manual hoster selection; only sorting and user feedback are refined.
        logger.info('-> [hoster]: auto stream initiated')
        self.dialog = xbmcgui.DialogProgress()
        self.dialog.create('xStream', cConfig().getLocalizedString(30138))
        self.dialog.update(5, cConfig().getLocalizedString(30139))
        plugin = __import__(siteName, globals(), locals())
        function = getattr(plugin, function)
        self.dialog.update(10, cConfig().getLocalizedString(30140))
        try:
            siteResult = function()
        except Exception as e:
            # A site request may fail before a hoster list exists (for example
            # an iframe/container timeout). Keep AutoPlay from leaking the
            # Python exception into Kodi's GUI. Resolver-specific code such as
            # dropload.py is intentionally untouched.
            logger.error('-> [hoster]: hoster discovery failed: %s' % e)
            try:
                self.dialog.close()
            except Exception:
                pass
            xbmcgui.Dialog().ok('xStream', 'Stream konnte nicht gestartet werden.\nKeine Hoster konnten geladen werden.')
            return False
        if not siteResult:
            self.dialog.close()
            cGui().showInfo('xStream', cConfig().getLocalizedString(30141))
            return False
        if not type(siteResult) is list:
            siteResult = [siteResult]

        if 'name' in siteResult[0]:
            self.dialog.update(90, cConfig().getLocalizedString(30143))
            functionName = siteResult[-1]
            del siteResult[-1]
            if siteName.startswith('dummy'):
                hosters = siteResult
            else:
                hosters = self.__getPriorities(siteResult)
            if not hosters:
                self.dialog.close()
                cGui().showInfo('xStream', cConfig().getLocalizedString(30144))
                return False
            hosters = hosters[:self.maxHoster]
            total = len(hosters)
            icon = 'special://home/addons/plugin.video.xstream/resources/icon.png'
            self._silentResolveErrors = True
            try:
                for count, hoster in enumerate(hosters):
                    if self.dialog.iscanceled() or xbmc.Monitor().abortRequested():
                        return False
                    percent = (count + 1) * 100 // max(1, total)
                    name = hoster.get('displayedName') or hoster.get('name') or 'Hoster'
                    quality = ''
                    try:
                        import re
                        qtext = ' '.join(str(hoster.get(k, '')) for k in ('quality', 'displayedName', 'name'))
                        qm = re.search(r'(?<!\d)(2160|1440|1080|720|576|540|480|360|240)\s*p?(?!\d)', qtext, re.I)
                        if qm:
                            quality = ' [%sp]' % qm.group(1)
                    except Exception:
                        pass
                    # Some site plugins already include the quality in displayedName/name.
                    # Remove any existing resolution marker and append the detected quality once.
                    try:
                        clean_name = re.sub(r'\s*[\[\(]?\s*(?:2160|1440|1080|720|576|540|480|360|240)\s*p?\s*[\]\)]?', '', str(name), flags=re.I).strip()
                    except Exception:
                        clean_name = str(name).strip()
                    display = '%s%s' % (clean_name or str(name).strip(), quality)
                    try:
                        logger.info('-> [hoster]: try hoster %s' % display)
                        self.dialog.update(percent, 'Hoster: %s' % display)
                        xbmcgui.Dialog().notification('xStream', 'Hoster: %s - Wird gestartet ...' % display, icon, 1800, False)
                        result = getattr(plugin, functionName)(hoster['link'])
                        if self.__autoEnqueue(result, playMode):
                            return True
                    except Exception as e:
                        logger.error('-> [hoster]: playback with hoster %s failed: %s' % (display, e))
                        # No error popup here: AutoPlay continues with the next hoster.
                        continue
            finally:
                self._silentResolveErrors = False
            try:
                self.dialog.close()
            except Exception:
                pass
            xbmcgui.Dialog().ok('xStream', 'Stream konnte nicht gestartet werden.\nKein verfügbarer Hoster war erfolgreich.')
            return False

        elif 'resolved' in siteResult[0]:
            self._silentResolveErrors = True
            try:
                for stream in siteResult:
                    try:
                        if self.__autoEnqueue([stream], playMode):
                            self.dialog.close()
                            return True
                    except Exception:
                        pass
            finally:
                self._silentResolveErrors = False
            try:
                self.dialog.close()
            except Exception:
                pass
            xbmcgui.Dialog().ok('xStream', 'Stream konnte nicht gestartet werden.\nKein verfügbarer Stream war erfolgreich.')
            return False

    def _chooseHoster(self, siteResult):
        dialog = xbmcgui.Dialog()
        titles = []
        for result in siteResult:
            if 'displayedName' in result:
                titles.append(str(result['displayedName']))
            else:
                titles.append(str(result['name']))
        index = dialog.select(cConfig().getLocalizedString(30149), titles)
        if index > -1:
            siteResult = siteResult[index]
            return siteResult
        else:
            logger.info('-> [hoster]: no hoster selected')
            return False

    def _choosePart(self, siteResult):
        self.dialog = xbmcgui.Dialog()
        titles = []
        for result in siteResult:
            titles.append(str(result['title']))
        index = self.dialog.select(cConfig().getLocalizedString(30150), titles)
        if index > -1:
            siteResult = siteResult[index]
            return siteResult
        else:
            return False

    def showHosterFolder(self, siteResult, siteName, functionName):
        oGui = cGui()
        total = len(siteResult)
        params = ParameterHandler()
        for hoster in siteResult:
            if 'displayedName' in hoster:
                name = hoster['displayedName']
            else:
                name = hoster['name']
            oGuiElement = cGuiElement(name, siteName, functionName)
            oGuiElement.setThumbnail(str(params.getValue('thumb')))
            params.setParam('url', hoster['link'])
            params.setParam('isHoster', 'true')
            oGui.addFolder(oGuiElement, params, iTotal=total, isHoster=True)
        oGui.setEndOfDirectory()

    def __autoEnqueue(self, partList, playMode):
        # choose part
        if not partList:
            return False
        for i in range(len(partList) - 1, -1, -1):
            try:
                if playMode == 'play' and i == 0:
                    if not self.play(partList[i]):
                        return False
                elif playMode == 'download':
                    self.download(partList[i])
                elif playMode == 'enqueue' or (playMode == 'play' and i > 0):
                    self.addToPlaylist(partList[i])
            except:
                return False
        logger.info('-> [hoster]: autoEnqueue successful')
        return True


class Hoster:
    def __init__(self, name, link):
        self.name = name
        self.link = link