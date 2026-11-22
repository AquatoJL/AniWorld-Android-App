package com.example.aniworld;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;

import android.content.SharedPreferences;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.provider.Settings;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.webkit.WebChromeClient;
import android.webkit.WebViewClient;
import android.webkit.CookieManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;
import org.jsoup.Connection;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;

import java.io.InputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.Collections;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.security.MessageDigest;

import android.util.Log;
import android.util.LruCache;
import android.net.http.SslError;
import android.webkit.SslErrorHandler;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebResourceResponse;

import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.MediaSource;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.ui.PlayerView;


@androidx.media3.common.util.UnstableApi
public class MainActivity extends AppCompatActivity {

    private static final String BASE = "https://aniworld.to";
    private static final String UPDATE_METADATA_URL =
            "https://api.github.com/repos/AquatoJL/AniWorld-Android-App/contents/app-release.apk?ref=main";
    private static final int REQUEST_INSTALL_PERMISSION = 7101;
    private static final int REQUEST_INSTALL_APK = 7102;
    private static final long MAX_UPDATE_APK_SIZE = 250L * 1024L * 1024L;

    private static final int ORANGE = 0xFFF47521;
    private static final int CARD_BACKGROUND = 0xFF1C1C1C;
    private static final int SEARCH_BACKGROUND = 0xFF242424;

    private long lastLeftPress = 0;
    private long lastRightPress = 0;
    private long firstExitBackPressAt = -1;
    private int exitBackPressCount = 0;
    private static final long EXIT_BACK_PRESS_INTERVAL_MS = 2_000;
    private static final int EXIT_BACK_PRESS_COUNT = 3;
    private static final long DOUBLE_PRESS_TIME = 200;
    private static final long SEEK_NORMAL = 10_000;
    private static final long SEEK_DOUBLE = 70_000;

    private final ExecutorService io =
            Executors.newSingleThreadExecutor();

    private final ExecutorService updateExecutor =
            Executors.newSingleThreadExecutor();

    private final ThreadPoolExecutor imageExecutor =
            (ThreadPoolExecutor) Executors.newFixedThreadPool(1);

    private volatile PosterBatch activePosterBatch;

    private final LruCache<String, Bitmap> posterCache =
            new LruCache<>(
                    (int) Math.max(
                            4L * 1024 * 1024,
                            Math.min(
                                    Runtime.getRuntime().maxMemory() / 16,
                                    24L * 1024 * 1024
                            )
                    )
            ) {
                @Override
                protected int sizeOf(String key, Bitmap bitmap) {
                    return bitmap.getByteCount();
                }
            };

    private LinearLayout catalog;
    private LinearLayout navigation;
    private Button selectedNavigationButton;
    private boolean suppressNavigationFocusLoad = false;
    private boolean pendingFirstAnimeFocus = false;
    private TextView sectionTitle;
    private EditText search;
    private LinearLayout recentSearches;
    private Object searchBackCallback;
    private WebView player;
    private PlayerView nativePlayerView;
    private ExoPlayer nativePlayer;
    private volatile boolean nativeResolveInProgress = false;
    private View customView;
    private WebChromeClient.CustomViewCallback customViewCallback;
    private PlayerWebChromeClient playerChromeClient;

    private final List<Show> currentShows = new ArrayList<>();

    private String currentUrl = BASE + "/";
    private String currentTitle = "Start";

    // 0 = Katalog, 1 = Staffeln, 2 = Episoden, 3 = Hoster
    private int level = 0;

    private Show selectedAnime;
    private Show selectedSeason;
    private Show selectedEpisode;

    private String currentEpisodeId = null;
    private boolean currentEpisodeMarked = false;

    private final Handler watchHandler = new Handler(Looper.getMainLooper());

    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private Runnable watchEpisodeRunnable;
    private Runnable playerStartSequence;

    private LinearLayout mainContent;

    private static final boolean DEBUG = false;
    private static final boolean INFO = false;

    private void logDebug(String message) {
        if (DEBUG) {
            Log.d("AniWorld", message);
        }
    }
    private void logInfo(String message) {
        if (INFO) {
            Log.i("AniWorld", message);
        }
    }

    private static class Show {
        String title;
        String url;
        String posterUrl;
        boolean seen;

        Show(String title, String url) {
            this(title, url, "");
        }

        Show(String title, String url, String posterUrl) {
            this.title = title;
            this.url = url;
            this.posterUrl = posterUrl;
            this.seen = false;
        }
    }

    private static class StreamHoster extends Show {

        String language;
        int languagePriority;

        StreamHoster(
                String title,
                String url,
                String language,
                int languagePriority
        ) {
            super(title, url);
            this.language = language;
            this.languagePriority = languagePriority;
        }
    }

    private static class PosterCard {
        final ImageView imageView;
        final TextView placeholder;
        final Show show;
        boolean requested;

        PosterCard(
                ImageView imageView,
                TextView placeholder,
                Show show
        ) {
            this.imageView = imageView;
            this.placeholder = placeholder;
            this.show = show;
        }
    }

    private static class PosterBatch {
        final int total;
        final AtomicInteger finished = new AtomicInteger(0);
        final AtomicInteger downloaded = new AtomicInteger(0);
        final AtomicInteger diskHits = new AtomicInteger(0);
        final AtomicInteger memoryHits = new AtomicInteger(0);
        final AtomicInteger failed = new AtomicInteger(0);
        volatile boolean cancelled = false;
        final List<Future<?>> tasks =
                Collections.synchronizedList(new ArrayList<>());
        final List<HttpURLConnection> connections =
                Collections.synchronizedList(new ArrayList<>());
        PosterBatch(int total) {
            this.total = total;
        }
    }

    private String getCachedPosterUrl(String animeUrl) {
        SharedPreferences prefs = getSharedPreferences(
                "poster_urls",
                MODE_PRIVATE
        );

        return prefs.getString(animeUrl, "");
    }

    private void saveCachedPosterUrl(String animeUrl, String posterUrl) {
        if (animeUrl == null || animeUrl.isEmpty()
                || posterUrl == null || posterUrl.isEmpty()) {
            return;
        }

        SharedPreferences prefs = getSharedPreferences(
                "poster_urls",
                MODE_PRIVATE
        );

        prefs.edit()
                .putString(animeUrl, posterUrl)
                .apply();
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {

        if (search != null
                && search.getVisibility() == View.VISIBLE
                && (event.getKeyCode() == KeyEvent.KEYCODE_BACK
                || event.getKeyCode() == KeyEvent.KEYCODE_ESCAPE)) {
            if (event.getAction() == KeyEvent.ACTION_DOWN
                    && event.getRepeatCount() == 0) {
                closeSearch();
            }
            return true;
        }

        if (nativePlayerView != null
                && nativePlayerView.getVisibility() == View.VISIBLE
                && nativePlayer != null) {

            if (event.getAction() == KeyEvent.ACTION_DOWN
                    && event.getRepeatCount() == 0) {

                switch (event.getKeyCode()) {

                    case KeyEvent.KEYCODE_DPAD_RIGHT: {
                        long now = SystemClock.uptimeMillis();

                        if (now - lastRightPress < DOUBLE_PRESS_TIME) {
                            nativePlayer.seekTo(
                                    nativePlayer.getCurrentPosition() + SEEK_DOUBLE
                            );
                            lastRightPress = 0;
                        } else {
                            nativePlayer.seekTo(
                                    nativePlayer.getCurrentPosition() + SEEK_NORMAL
                            );
                            lastRightPress = now;
                        }

                        return true;
                    }

                    case KeyEvent.KEYCODE_DPAD_LEFT: {
                        long now = SystemClock.uptimeMillis();

                        if (now - lastLeftPress < DOUBLE_PRESS_TIME) {
                            nativePlayer.seekTo(
                                    Math.max(0,
                                            nativePlayer.getCurrentPosition() - SEEK_DOUBLE)
                            );
                            lastLeftPress = 0;
                        } else {
                            nativePlayer.seekTo(
                                    Math.max(0,
                                            nativePlayer.getCurrentPosition() - SEEK_NORMAL)
                            );
                            lastLeftPress = now;
                        }

                        return true;
                    }

                    case KeyEvent.KEYCODE_DPAD_CENTER:
                    case KeyEvent.KEYCODE_ENTER:
                    case KeyEvent.KEYCODE_NUMPAD_ENTER:

                        if (nativePlayer.isPlaying()) {
                            nativePlayer.pause();
                        } else {
                            nativePlayer.play();
                        }

                        return true;
                }
            }

            if (event.getKeyCode() == KeyEvent.KEYCODE_DPAD_LEFT
                    || event.getKeyCode() == KeyEvent.KEYCODE_DPAD_RIGHT
                    || event.getKeyCode() == KeyEvent.KEYCODE_DPAD_CENTER
                    || event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                    || event.getKeyCode() == KeyEvent.KEYCODE_NUMPAD_ENTER) {
                return true;
            }
        }

        if (event.getAction() == KeyEvent.ACTION_DOWN
                && event.getKeyCode() == KeyEvent.KEYCODE_DPAD_UP
                && search != null
                && search.getVisibility() == View.VISIBLE) {
            View focused = getCurrentFocus();
            if (isViewInside(focused, recentSearches)) {
                search.requestFocus();
                return true;
            }
            if (focused == search) {
                closeSearch();
                return true;
            }
        }

        if (event.getAction() == KeyEvent.ACTION_DOWN
                && event.getKeyCode() == KeyEvent.KEYCODE_DPAD_UP
                && level == 0
                && selectedNavigationButton != null
                && isViewInsideCatalog(getCurrentFocus())) {
            selectedNavigationButton.requestFocus();
            return true;
        }

        if (event.getAction() == KeyEvent.ACTION_DOWN
                && event.getKeyCode() == KeyEvent.KEYCODE_DPAD_DOWN
                && level == 0
                && isViewInsideNavigation(getCurrentFocus())) {
            pendingFirstAnimeFocus = !focusFirstAnimeCard();
            return true;
        }

        return super.dispatchKeyEvent(event);
    }

    private boolean isViewInsideCatalog(View view) {
        return isViewInside(view, catalog);
    }

    private boolean isViewInsideNavigation(View view) {
        return isViewInside(view, navigation);
    }

    private boolean isViewInside(View view, View parent) {
        View current = view;
        while (current != null) {
            if (current == parent) {
                return true;
            }
            current = current.getParent() instanceof View
                    ? (View) current.getParent()
                    : null;
        }
        return false;
    }

    private boolean focusFirstAnimeCard() {
        if (catalog == null) {
            return false;
        }

        for (int i = 0; i < catalog.getChildCount(); i++) {
            View child = catalog.getChildAt(i);
            if (!(child instanceof HorizontalScrollView)) {
                continue;
            }

            View row = ((HorizontalScrollView) child).getChildAt(0);
            if (row instanceof android.view.ViewGroup
                    && ((android.view.ViewGroup) row).getChildCount() > 0) {
                View firstCard = ((android.view.ViewGroup) row).getChildAt(0);
                if (firstCard.isFocusable()) {
                    return firstCard.requestFocus();
                }
            }
        }

        return false;
    }

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);

        setContentView(R.layout.activity_main);

        mainContent = findViewById(R.id.mainContent);

        hideSystemBars();

        catalog = findViewById(R.id.catalog);
        navigation = findViewById(R.id.navigation);
        sectionTitle = findViewById(R.id.sectionTitle);
        search = findViewById(R.id.search);
        recentSearches = findViewById(R.id.recentSearches);
        player = findViewById(R.id.playerWeb);
        nativePlayerView = findViewById(R.id.nativePlayerView);

        // Suchfeld auch beim Fokus dunkel halten.
        search.setBackground(
                round(
                        SEARCH_BACKGROUND,
                        0xFF444444,
                        10
                )
        );

        search.setPadding(
                dp(16),
                0,
                dp(16),
                0
        );

        search.setOnFocusChangeListener((v, hasFocus) -> {
            search.setBackground(
                    round(
                            SEARCH_BACKGROUND,
                            hasFocus ? ORANGE : 0xFF444444,
                            10
                    )
            );

            if (!hasFocus && search.getVisibility() == View.VISIBLE) {
                search.post(() -> {
                    if (!search.hasFocus()
                            && search.getVisibility() == View.VISIBLE
                            && !isViewInside(
                                    getCurrentFocus(),
                                    recentSearches
                            )) {
                        closeSearch();
                    }
                });
            }
        });

        getOnBackPressedDispatcher().addCallback(
                this,
                new OnBackPressedCallback(true) {
                    @Override
                    public void handleOnBackPressed() {

                        if (customView != null
                                && playerChromeClient != null) {
                            playerChromeClient.onHideCustomView();
                            return;
                        }

                        if (search.getVisibility() == View.VISIBLE) {
                            closeSearch();
                            return;
                        }

                        if (player.getVisibility() == View.VISIBLE
                                || nativePlayerView.getVisibility() == View.VISIBLE) {
                            showCatalog();
                            if (level == 3 && selectedEpisode != null) {
                                openEpisode(selectedEpisode);
                            }
                            return;
                        }

                        if (level == 3 && selectedSeason != null) {
                            loadEpisodes(selectedSeason);
                            return;
                        }

                        if (level == 2 && selectedAnime != null) {
                            openSeries(selectedAnime);
                            return;
                        }

                        if (level == 1) {
                            level = 0;
                            loadCatalog(currentUrl, currentTitle);
                            return;
                        }

                        long now = SystemClock.uptimeMillis();
                        if (firstExitBackPressAt < 0
                                || now - firstExitBackPressAt
                                > EXIT_BACK_PRESS_INTERVAL_MS) {
                            firstExitBackPressAt = now;
                            exitBackPressCount = 1;
                        } else {
                            exitBackPressCount++;
                        }

                        if (exitBackPressCount >= EXIT_BACK_PRESS_COUNT) {
                            finish();
                            firstExitBackPressAt = -1;
                            exitBackPressCount = 0;
                        }
                    }
                }
        );

        WebSettings ws = player.getSettings();

        logInfo(
                "WebView User-Agent: " + ws.getUserAgentString()
        );

        if (WebView.getCurrentWebViewPackage() != null) {
            logInfo("WebView Version: " + WebView.getCurrentWebViewPackage().versionName);
        }

        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setLoadsImagesAutomatically(true);
        ws.setJavaScriptCanOpenWindowsAutomatically(false);
        ws.setSupportMultipleWindows(true);

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(player, true);

        playerChromeClient = new PlayerWebChromeClient();
        player.setWebChromeClient(playerChromeClient);

        player.setWebViewClient(new WebViewClient() {

            @Override
            public boolean shouldOverrideUrlLoading(
                    WebView view,
                    WebResourceRequest request
            ) {

                String scheme = request.getUrl().getScheme();

                if (scheme == null
                        || (!scheme.equals("http")
                        && !scheme.equals("https"))) {

                    logDebug(
                            "Externer Aufruf blockiert: "
                                    + request.getUrl()
                    );

                    return true;
                }

                return false;
            }

            @Override
            public void onReceivedError(
                    WebView view,
                    WebResourceRequest request,
                    WebResourceError error
            ) {

                if (request.isForMainFrame()) {
                    Log.e(
                            "AniWorld",
                            "WebView-Netzwerkfehler: "
                                    + error.getErrorCode()
                                    + " - "
                                    + error.getDescription()
                                    + " URL: "
                                    + request.getUrl()
                    );
                }
            }

            @Override
            public void onReceivedSslError(
                    WebView view,
                    SslErrorHandler handler,
                    SslError error
            ) {

                Log.e(
                        "AniWorld",
                        "SSL-Fehler: "
                                + error.toString()
                                + " URL: "
                                + error.getUrl()
                );

                handler.cancel();
            }

            @Override
            public void onReceivedHttpError(
                    WebView view,
                    WebResourceRequest request,
                    WebResourceResponse response
            ) {

                if (request.isForMainFrame()) {
                    Log.e(
                            "AniWorld",
                            "HTTP-Fehler: "
                                    + response.getStatusCode()
                                    + " URL: "
                                    + request.getUrl()
                    );
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);

                CookieManager.getInstance().flush();

                if (playerStartSequence != null) {
                    watchHandler.removeCallbacks(playerStartSequence);
                }

                playerStartSequence = () -> {

                    if (player.getVisibility() != View.VISIBLE) {
                        return;
                    }

                    player.requestFocus(View.FOCUS_DOWN);

                    logDebug("Sende Enter für Vollbild");
                    dispatchEnterKey();

                    watchHandler.postDelayed(() -> {
                        dispatchEnterKey();
                    }, 150);
                };

                watchHandler.postDelayed(
                        playerStartSequence,
                        2500
                );

                view.evaluateJavascript(
                        "(function() {" +
                                "var video = document.querySelector('video');" +
                                "if (video) {" +
                                "video.muted = false;" +
                                "var p = video.play();" +
                                "if (p && p.catch) p.catch(function() {});" +
                                "}" +
                                "})();",
                        null
                );

                view.evaluateJavascript(
                        "(function() {" +
                                "function installFullscreenKeys(doc) {" +
                                "if (!doc || doc.__aniworldFullscreenKeys) return;" +
                                "doc.__aniworldFullscreenKeys = true;" +
                                "var lastPress = 0;" +
                                "doc.addEventListener('keydown', function(e) {" +
                                "var key = e.key || '';" +
                                "var isSelect = key === 'Enter' || key === ' ' || key === 'Spacebar' || e.keyCode === 13 || e.keyCode === 32;" +
                                "if (!isSelect || e.repeat) return;" +
                                "var now = Date.now();" +
                                "if (now - lastPress > 500) { lastPress = now; return; }" +
                                "lastPress = 0;" +
                                "var d = doc;" +
                                "if (d.fullscreenElement || d.webkitFullscreenElement) return;" +
                                "var selectors = 'button[aria-label*=fullscreen i],button[title*=fullscreen i],button[aria-label*=vollbild i],button[title*=vollbild i],.vjs-fullscreen-control,.jw-icon-fullscreen,.plyr__control[data-plyr=fullscreen],.fp-fullscreen,[data-testid*=fullscreen]';" +
                                "var fsButton = d.querySelector(selectors);" +
                                "if (fsButton) { e.preventDefault(); e.stopPropagation(); fsButton.click(); return; }" +
                                "var video = d.querySelector('video');" +
                                "if (!video) return;" +
                                "var target = video.closest('.plyr, .video-js, .jwplayer, .fp-player, .player, .video-container') || video;" +
                                "var request = target.requestFullscreen || target.webkitRequestFullscreen || video.requestFullscreen || video.webkitRequestFullscreen;" +
                                "if (request) { e.preventDefault(); e.stopPropagation(); try { var result = request.call(target); if (result && result.catch) result.catch(function() {}); } catch(err) {} }" +
                                "}, true);" +
                                "Array.prototype.forEach.call(doc.querySelectorAll('iframe'), function(frame) {" +
                                "try { installFullscreenKeys(frame.contentDocument); } catch(err) {}" +
                                "});" +
                                "var observer = new MutationObserver(function() {" +
                                "Array.prototype.forEach.call(doc.querySelectorAll('iframe'), function(frame) {" +
                                "try { installFullscreenKeys(frame.contentDocument); } catch(err) {}" +
                                "});" +
                                "});" +
                                "if (doc.documentElement) observer.observe(doc.documentElement, {childList:true, subtree:true});" +
                                "}" +
                                "installFullscreenKeys(document);" +
                                "})();",
                        null
                );
            }
        });

        player.setOnApplyWindowInsetsListener((view, insets) -> {
            hideSystemBars();
            return view.onApplyWindowInsets(insets);
        });

        buildNavigation();

        search.setOnEditorActionListener((v, action, event) -> {

            if (action == android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH
                    || (event != null
                    && event.getKeyCode() == KeyEvent.KEYCODE_ENTER)) {

                String q = search.getText().toString().trim();

                if (!q.isEmpty()) {
                    search(q);
                }

                return true;
            }

            return false;
        });

        loadCatalog(BASE + "/", "Start");
        checkForAppUpdate();
    }

    // ---------------------------------------------------------
    // APP UPDATES
    // ---------------------------------------------------------

    private void checkForAppUpdate() {
        updateExecutor.execute(() -> {
            File updateFile = null;

            try {
                JSONObject metadata = requestUpdateMetadata();
                String remoteSha = metadata.optString("sha", "");
                String downloadUrl = metadata.optString("download_url", "");
                long expectedSize = metadata.optLong("size", -1);

                if (remoteSha.isEmpty()
                        || expectedSize <= 0
                        || expectedSize > MAX_UPDATE_APK_SIZE
                        || !isTrustedUpdateUrl(downloadUrl)) {
                    throw new IOException("Ungültige GitHub-Update-Metadaten");
                }

                SharedPreferences preferences =
                        getSharedPreferences("app_update", MODE_PRIVATE);
                if (remoteSha.equals(
                        preferences.getString("last_checked_sha", "")
                )) {
                    return;
                }

                File updateDirectory = new File(getCacheDir(), "updates");
                if (!updateDirectory.exists() && !updateDirectory.mkdirs()) {
                    throw new IOException("Update-Ordner konnte nicht erstellt werden");
                }

                updateFile = new File(updateDirectory, "aniworld-update.apk");
                downloadUpdateApk(downloadUrl, updateFile, expectedSize);

                if (!remoteSha.equalsIgnoreCase(computeGitHubBlobSha1(updateFile))) {
                    throw new IOException("Die heruntergeladene APK stimmt nicht mit GitHub überein");
                }

                PackageManager packageManager = getPackageManager();
                int packageFlags = PackageManager.GET_SIGNING_CERTIFICATES;
                PackageInfo remotePackage = packageManager.getPackageArchiveInfo(
                        updateFile.getAbsolutePath(),
                        packageFlags
                );
                PackageInfo installedPackage = packageManager.getPackageInfo(
                        getPackageName(),
                        packageFlags
                );

                if (remotePackage == null
                        || !getPackageName().equals(remotePackage.packageName)) {
                    throw new IOException("Die APK gehört nicht zu AniWorld");
                }

                if (remotePackage.getLongVersionCode()
                        <= installedPackage.getLongVersionCode()) {
                    preferences.edit()
                            .putString("last_checked_sha", remoteSha)
                            .apply();
                    updateFile.delete();
                    return;
                }

                Set<String> remoteCertificates =
                        getSigningCertificateIds(remotePackage);
                Set<String> installedCertificates =
                        getSigningCertificateIds(installedPackage);
                if (remoteCertificates.isEmpty()
                        || installedCertificates.isEmpty()
                        || !remoteCertificates.equals(installedCertificates)) {
                    preferences.edit()
                            .putString("last_checked_sha", remoteSha)
                            .apply();
                    updateFile.delete();
                    runOnUiThread(() -> Toast.makeText(
                            MainActivity.this,
                            "Das Update ist mit einem anderen Schlüssel signiert.",
                            Toast.LENGTH_LONG
                    ).show());
                    return;
                }

                File verifiedUpdateFile = updateFile;
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        Toast.makeText(
                                MainActivity.this,
                                "Update verfügbar – Installation wird gestartet.",
                                Toast.LENGTH_SHORT
                        ).show();
                        installDownloadedUpdate(verifiedUpdateFile);
                    }
                });
            } catch (Exception e) {
                if (updateFile != null && updateFile.exists()) {
                    updateFile.delete();
                }
                Log.w("AniWorldUpdate", "Update-Prüfung fehlgeschlagen", e);
            }
        });
    }

    private JSONObject requestUpdateMetadata() throws Exception {
        HttpURLConnection connection =
                (HttpURLConnection) new URL(UPDATE_METADATA_URL).openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(20000);
        connection.setInstanceFollowRedirects(true);
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        connection.setRequestProperty("User-Agent", "AniWorld-Android-App");

        try {
            int responseCode = connection.getResponseCode();
            if (responseCode != HttpURLConnection.HTTP_OK) {
                throw new IOException("GitHub antwortete mit HTTP " + responseCode);
            }

            try (InputStream input = connection.getInputStream();
                 java.io.ByteArrayOutputStream output =
                         new java.io.ByteArrayOutputStream()) {
                byte[] buffer = new byte[4096];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    output.write(buffer, 0, count);
                    if (output.size() > 1024 * 1024) {
                        throw new IOException("GitHub-Metadaten sind zu groß");
                    }
                }
                return new JSONObject(
                        new String(output.toByteArray(), java.nio.charset.StandardCharsets.UTF_8)
                );
            }
        } finally {
            connection.disconnect();
        }
    }

    private boolean isTrustedUpdateUrl(String value) {
        try {
            URL url = new URL(value);
            return "https".equalsIgnoreCase(url.getProtocol())
                    && "raw.githubusercontent.com".equalsIgnoreCase(url.getHost());
        } catch (Exception ignored) {
            return false;
        }
    }

    private void downloadUpdateApk(
            String downloadUrl,
            File destination,
            long expectedSize
    ) throws Exception {
        File temporaryFile = new File(
                destination.getParentFile(),
                destination.getName() + ".part"
        );
        HttpURLConnection connection =
                (HttpURLConnection) new URL(downloadUrl).openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(20000);
        connection.setReadTimeout(45000);
        connection.setInstanceFollowRedirects(true);
        connection.setRequestProperty("User-Agent", "AniWorld-Android-App");

        try {
            if (connection.getResponseCode() != HttpURLConnection.HTTP_OK) {
                throw new IOException(
                        "APK-Download fehlgeschlagen: HTTP "
                                + connection.getResponseCode()
                );
            }

            long downloadedBytes = 0;
            try (InputStream input = connection.getInputStream();
                 FileOutputStream output = new FileOutputStream(temporaryFile)) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    downloadedBytes += count;
                    if (downloadedBytes > MAX_UPDATE_APK_SIZE
                            || downloadedBytes > expectedSize) {
                        throw new IOException("APK ist größer als erwartet");
                    }
                    output.write(buffer, 0, count);
                }
                output.getFD().sync();
            }

            if (downloadedBytes != expectedSize) {
                throw new IOException("APK-Download ist unvollständig");
            }

            if (destination.exists() && !destination.delete()) {
                throw new IOException("Alte Update-Datei konnte nicht entfernt werden");
            }
            if (!temporaryFile.renameTo(destination)) {
                throw new IOException("Update-Datei konnte nicht gespeichert werden");
            }
        } finally {
            connection.disconnect();
            if (temporaryFile.exists()) {
                temporaryFile.delete();
            }
        }
    }

    private String computeGitHubBlobSha1(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-1");
        digest.update(
                ("blob " + file.length() + "\0")
                        .getBytes(java.nio.charset.StandardCharsets.US_ASCII)
        );

        try (InputStream input = new java.io.FileInputStream(file)) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                digest.update(buffer, 0, count);
            }
        }

        byte[] hash = digest.digest();
        StringBuilder result = new StringBuilder(hash.length * 2);
        for (byte value : hash) {
            result.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        }
        return result.toString();
    }

    private Set<String> getSigningCertificateIds(PackageInfo packageInfo)
            throws Exception {
        Set<String> certificateIds = new HashSet<>();
        if (packageInfo.signingInfo == null) {
            return certificateIds;
        }

        Signature[] signatures = packageInfo.signingInfo.getApkContentsSigners();
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        for (Signature signature : signatures) {
            byte[] hash = digest.digest(signature.toByteArray());
            StringBuilder id = new StringBuilder(hash.length * 2);
            for (byte value : hash) {
                id.append(String.format(Locale.ROOT, "%02x", value & 0xff));
            }
            certificateIds.add(id.toString());
        }
        return certificateIds;
    }

    private void installDownloadedUpdate(File apkFile) {
        if (android.os.Build.VERSION.SDK_INT >= 26
                && !getPackageManager().canRequestPackageInstalls()) {
            getSharedPreferences("app_update", MODE_PRIVATE)
                    .edit()
                    .putString("pending_apk", apkFile.getAbsolutePath())
                    .apply();

            Intent settingsIntent = new Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName())
            );
            try {
                startActivityForResult(
                        settingsIntent,
                        REQUEST_INSTALL_PERMISSION
                );
            } catch (Exception e) {
                Log.e("AniWorldUpdate", "Installations-Einstellungen nicht verfügbar", e);
                Toast.makeText(
                        this,
                        "Installation unbekannter Apps für AniWorld erlauben.",
                        Toast.LENGTH_LONG
                ).show();
            }
            return;
        }

        launchPackageInstaller(apkFile);
    }

    private void launchPackageInstaller(File apkFile) {
        try {
            Uri apkUri = FileProvider.getUriForFile(
                    this,
                    getPackageName() + ".fileprovider",
                    apkFile
            );
            Intent installIntent = new Intent(Intent.ACTION_INSTALL_PACKAGE);
            installIntent.setDataAndType(
                    apkUri,
                    "application/vnd.android.package-archive"
            );
            installIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            installIntent.putExtra(Intent.EXTRA_RETURN_RESULT, true);
            startActivityForResult(installIntent, REQUEST_INSTALL_APK);
        } catch (Exception e) {
            Log.e("AniWorldUpdate", "APK-Installation konnte nicht gestartet werden", e);
            Toast.makeText(
                    this,
                    "Das Update konnte nicht geöffnet werden.",
                    Toast.LENGTH_LONG
            ).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode != REQUEST_INSTALL_PERMISSION) {
            return;
        }

        SharedPreferences preferences =
                getSharedPreferences("app_update", MODE_PRIVATE);
        String pendingPath = preferences.getString("pending_apk", "");
        preferences.edit().remove("pending_apk").apply();

        if (android.os.Build.VERSION.SDK_INT >= 26
                && getPackageManager().canRequestPackageInstalls()
                && !pendingPath.isEmpty()) {
            launchPackageInstaller(new File(pendingPath));
        } else {
            Toast.makeText(
                    this,
                    "AniWorld darf keine Updates installieren.",
                    Toast.LENGTH_LONG
            ).show();
        }
    }

    // ---------------------------------------------------------
    // COOKIES
    // ---------------------------------------------------------

    private Map<String, String> getCookiesFor(String url) {

        Map<String, String> cookies = new HashMap<>();

        String cookieString =
                CookieManager.getInstance().getCookie(url);

        if (cookieString != null && !cookieString.isEmpty()) {

            for (String cookie : cookieString.split(";")) {

                String[] parts = cookie.trim().split("=", 2);

                if (parts.length == 2) {
                    cookies.put(parts[0], parts[1]);
                }
            }
        }

        return cookies;
    }

    // ---------------------------------------------------------
    // EPISODE WATCH TIMER
    // ---------------------------------------------------------

    private void startEpisodeWatchTimer() {

        cancelEpisodeWatchTimer();

        if (currentEpisodeId == null
                || currentEpisodeId.isEmpty()) {

            Log.w(
                    "AniWorld",
                    "Watch-Timer nicht gestartet: Episoden-ID fehlt"
            );

            return;
        }

        final String episodeIdForTimer = currentEpisodeId;

        watchEpisodeRunnable = () -> {

            watchEpisodeRunnable = null;

            if (!episodeIdForTimer.equals(currentEpisodeId)
                    || currentEpisodeMarked) {
                return;
            }

            currentEpisodeMarked = true;
            markEpisodeAsSeen(episodeIdForTimer);
        };

        watchHandler.postDelayed(
                watchEpisodeRunnable,
                2 * 60 * 1000L
        );

        logDebug(
                "Watch-Timer gestartet für Episode: "
                        + episodeIdForTimer
        );
    }

    private void cancelEpisodeWatchTimer() {

        if (watchEpisodeRunnable != null) {
            watchHandler.removeCallbacks(watchEpisodeRunnable);
            watchEpisodeRunnable = null;
        }
    }

    private void markEpisodeAsSeen(String episodeId) {

        if (episodeId == null || episodeId.isEmpty()) {
            Log.e(
                    "AniWorld",
                    "Keine Episoden-ID zum Markieren vorhanden"
            );
            return;
        }

        io.execute(() -> {

            try {

                org.jsoup.Connection.Response response =
                        Jsoup.connect(BASE + "/ajax/lastseen")
                                .cookies(getCookiesFor(BASE))
                                .userAgent(
                                        "Mozilla/5.0 (Linux; Android 10; Fire TV)"
                                )
                                .header(
                                        "Content-Type",
                                        "application/x-www-form-urlencoded; charset=UTF-8"
                                )
                                .header(
                                        "X-Requested-With",
                                        "XMLHttpRequest"
                                )
                                .referrer(BASE + "/")
                                .data("episode", episodeId)
                                .method(org.jsoup.Connection.Method.POST)
                                .ignoreContentType(true)
                                .execute();

                logInfo("Lastseen Antwort HTTP "
                        + response.statusCode()
                        + " für Episode "
                        + episodeId
                        + "; Antwort: "
                        + response.body()
                );

            } catch (Exception e) {

                Log.e(
                        "AniWorld",
                        "Fehler beim Markieren der Episode "
                                + episodeId,
                        e
                );
            }
        });
    }

    // ---------------------------------------------------------
    // SYSTEM UI
    // ---------------------------------------------------------

    private void hideSystemBars() {

        WindowCompat.setDecorFitsSystemWindows(
                getWindow(),
                false
        );

        WindowInsetsControllerCompat controller =
                WindowCompat.getInsetsController(
                        getWindow(),
                        getWindow().getDecorView()
                );

        controller.hide(
                WindowInsetsCompat.Type.systemBars()
        );

        controller.setSystemBarsBehavior(
                WindowInsetsControllerCompat
                        .BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        );
    }

    // ---------------------------------------------------------
    // NAVIGATION
    // ---------------------------------------------------------

    private void buildNavigation() {

        String[][] items = {
                {"Start", BASE + "/"},
                {"Benachrichtigungen", BASE + "/account/notifications"},
                {"Neue Folgen", BASE + "/neue-episoden"},
                {"Beliebt", BASE + "/beliebte-animes"},
                {"Alle Anime", BASE + "/animes-alphabet"}
        };

        LinearLayout accountNavigation = findViewById(R.id.accountNavigation);

        ImageButton searchButton = new ImageButton(this);
        searchButton.setImageResource(android.R.drawable.ic_menu_search);
        searchButton.setColorFilter(Color.WHITE);
        searchButton.setContentDescription("Suche");
        searchButton.setBackgroundColor(Color.TRANSPARENT);
        searchButton.setFocusable(true);

        LinearLayout.LayoutParams searchLp =
                new LinearLayout.LayoutParams(dp(32), dp(32));
        searchLp.setMargins(0, 0, dp(5), 0);
        navigation.addView(searchButton, searchLp);

        searchButton.setOnFocusChangeListener((v, hasFocus) -> {
            if (hasFocus) {
                searchButton.post(() -> {
                    if (searchButton.hasFocus()) {
                        showSearch();
                    }
                });
            }
        });

        searchButton.setOnClickListener(v -> showSearch());

        for (String[] item : items) {

            Button b = new Button(this);

            b.setText(item[0]);
            b.setAllCaps(false);
            b.setTextColor(Color.WHITE);
            b.setTextSize(12);
            b.setTypeface(null, Typeface.BOLD);
            b.setIncludeFontPadding(false);
            b.setGravity(Gravity.CENTER);
            b.setPadding(dp(8), 0, dp(8), 0);
            b.setMinWidth(0);
            b.setMinimumWidth(0);
            b.setMinHeight(0);
            b.setMinimumHeight(0);

            b.setBackground(
                    round(0xFF101010, 0xFF101010, 24)
            );

            b.setFocusable(true);

            LinearLayout.LayoutParams lp =
                    new LinearLayout.LayoutParams(
                            -2,
                            dp(32)
                    );

            lp.setMargins(0, 0, dp(5), 0);

            navigation.addView(b, lp);

            b.setOnClickListener(v -> {
                selectNavigationButton(b);
                level = 0;
                loadCatalog(item[1], item[0]);
            });

            b.setOnFocusChangeListener((v, hasFocus) -> {
                if (hasFocus) {
                    selectNavigationButton(b);
                } else if (selectedNavigationButton != b) {
                    b.setBackground(round(0xFF101010, 0xFF101010, 24));
                }

                if (hasFocus
                        && !suppressNavigationFocusLoad
                        && !item[1].equals(currentUrl)) {
                    level = 0;
                    loadCatalog(item[1], item[0]);
                }
            });

            if ("Start".equals(item[0])) {
                b.setFocusedByDefault(true);
                selectNavigationButton(b);
                b.requestFocus();
            }
        }

        Button accountButton = new Button(this);

        accountButton.setText("Account");
        accountButton.setAllCaps(false);
        accountButton.setTextColor(Color.WHITE);
        accountButton.setTextSize(12);
        accountButton.setTypeface(null, Typeface.BOLD);
        accountButton.setIncludeFontPadding(false);
        accountButton.setGravity(Gravity.CENTER);
        accountButton.setPadding(dp(8), 0, dp(8), 0);
        accountButton.setMinWidth(0);
        accountButton.setMinimumWidth(0);
        accountButton.setMinHeight(0);
        accountButton.setMinimumHeight(0);

        accountButton.setBackground(
                round(0xFF101010, 0xFF101010, 24)
        );

        accountButton.setFocusable(true);

        LinearLayout.LayoutParams accountLp =
                new LinearLayout.LayoutParams(
                        -2,
                        dp(32)
                );

        accountLp.setMargins(0, 0, dp(5), 0);

        accountNavigation.addView(accountButton, accountLp);

        accountButton.setOnFocusChangeListener((v, hasFocus) -> {

            accountButton.setBackground(
                    round(
                            hasFocus ? ORANGE : 0xFF101010,
                            hasFocus ? ORANGE : 0xFF101010,
                            24
                    )
            );
        });

        accountButton.setOnClickListener(v ->
                openPlayer(BASE + "/account")
        );
    }

    private List<String> getRecentSearchQueries() {
        SharedPreferences preferences =
                getSharedPreferences("search_history", MODE_PRIVATE);
        String saved = preferences.getString("queries", "[]");
        List<String> queries = new ArrayList<>();

        try {
            org.json.JSONArray array = new org.json.JSONArray(saved);
            for (int i = 0; i < array.length() && queries.size() < 5; i++) {
                String query = array.optString(i, "").trim();
                if (!query.isEmpty()) {
                    queries.add(query);
                }
            }
        } catch (Exception ignored) {
        }

        return queries;
    }

    private void rememberSearch(String query) {
        String trimmed = query == null ? "" : query.trim();
        if (trimmed.isEmpty()) {
            return;
        }

        List<String> queries = getRecentSearchQueries();
        queries.removeIf(existing -> existing.equalsIgnoreCase(trimmed));
        queries.add(0, trimmed);
        while (queries.size() > 5) {
            queries.remove(queries.size() - 1);
        }

        getSharedPreferences("search_history", MODE_PRIVATE)
                .edit()
                .putString("queries", new org.json.JSONArray(queries).toString())
                .apply();
    }

    private void updateRecentSearches() {
        if (recentSearches == null) {
            return;
        }

        recentSearches.removeAllViews();
        List<String> queries = getRecentSearchQueries();
        if (queries.isEmpty()) {
            recentSearches.setVisibility(View.GONE);
            return;
        }

        recentSearches.setVisibility(View.VISIBLE);

        TextView heading = new TextView(this);
        heading.setText("Letzte Suchen");
        heading.setTextColor(0xFFAAAAAA);
        heading.setTextSize(14);
        heading.setPadding(dp(8), dp(4), dp(8), dp(8));
        recentSearches.addView(heading);

        for (String query : queries) {
            TextView item = new TextView(this);
            item.setText(query);
            item.setTextColor(Color.WHITE);
            item.setTextSize(15);
            item.setGravity(Gravity.CENTER_VERTICAL);
            item.setSingleLine(true);
            item.setEllipsize(android.text.TextUtils.TruncateAt.END);
            item.setPadding(dp(12), 0, dp(12), 0);
            item.setFocusable(true);
            item.setClickable(true);
            item.setBackground(round(0xFF101010, 0xFF101010, 8));

            item.setOnFocusChangeListener((view, hasFocus) ->
                    item.setBackground(round(
                            hasFocus ? ORANGE : 0xFF101010,
                            hasFocus ? ORANGE : 0xFF101010,
                            8
                    ))
            );

            item.setOnClickListener(view -> {
                search.setText(query);
                search.setSelection(search.length());
                search.requestFocus();
                search(query);
            });

            LinearLayout.LayoutParams itemParams =
                    new LinearLayout.LayoutParams(
                            LinearLayout.LayoutParams.MATCH_PARENT,
                            dp(42)
                    );
            itemParams.setMargins(0, 0, 0, dp(4));
            recentSearches.addView(item, itemParams);
        }
    }

    private void showSearch() {
        search.setVisibility(View.VISIBLE);
        sectionTitle.setVisibility(View.GONE);
        catalog.setVisibility(View.GONE);
        updateRecentSearches();

        if (android.os.Build.VERSION.SDK_INT >= 33
                && searchBackCallback == null) {
            searchBackCallback =
                    (android.window.OnBackInvokedCallback) this::closeSearch;
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    android.window.OnBackInvokedDispatcher.PRIORITY_OVERLAY,
                    (android.window.OnBackInvokedCallback) searchBackCallback
            );
        }

        search.requestFocus();
    }

    private void closeSearch() {
        if (search == null || search.getVisibility() != View.VISIBLE) {
            return;
        }

        if (android.os.Build.VERSION.SDK_INT >= 33
                && searchBackCallback != null) {
            getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(
                    (android.window.OnBackInvokedCallback) searchBackCallback
            );
            searchBackCallback = null;
        }

        android.view.inputmethod.InputMethodManager inputMethodManager =
                (android.view.inputmethod.InputMethodManager)
                        getSystemService(INPUT_METHOD_SERVICE);
        if (inputMethodManager != null) {
            inputMethodManager.hideSoftInputFromWindow(
                    search.getWindowToken(),
                    0
            );
        }

        View focusToRestore = getCurrentFocus();
        search.clearFocus();
        search.setVisibility(View.GONE);
        recentSearches.setVisibility(View.GONE);
        sectionTitle.setVisibility(View.VISIBLE);
        catalog.setVisibility(View.VISIBLE);

        if (focusToRestore != null
                && focusToRestore != search
                && focusToRestore.isFocusable()
                && focusToRestore.getVisibility() == View.VISIBLE
                && !isViewInside(focusToRestore, recentSearches)) {
            focusToRestore.requestFocus();
        } else {
            focusSelectedNavigationButtonWithoutLoading();
        }
    }

    private void focusSelectedNavigationButtonWithoutLoading() {
        if (selectedNavigationButton == null) {
            return;
        }

        boolean previousValue = suppressNavigationFocusLoad;
        suppressNavigationFocusLoad = true;
        selectedNavigationButton.requestFocus();
        suppressNavigationFocusLoad = previousValue;
    }

    private void selectNavigationButton(Button button) {
        if (selectedNavigationButton != null
                && selectedNavigationButton != button) {
            selectedNavigationButton.setBackground(
                    round(0xFF101010, 0xFF101010, 24)
            );
        }

        selectedNavigationButton = button;
        button.setBackground(round(ORANGE, ORANGE, 24));
    }

    // ---------------------------------------------------------
    // DESIGN / HILFSMETHODEN
    // ---------------------------------------------------------

    private GradientDrawable round(
            int color,
            int stroke,
            int radius
    ) {

        GradientDrawable d = new GradientDrawable();

        d.setColor(color);
        d.setCornerRadius(dp(radius));
        d.setStroke(dp(1), stroke);

        return d;
    }

    private int dp(float value) {

        return (int) (
                value
                        * getResources().getDisplayMetrics().density
                        + 0.5f
        );
    }

    private boolean containsUrl(
            List<Show> items,
            String url
    ) {

        for (Show item : items) {
            if (item.url.equals(url)) {
                return true;
            }
        }

        return false;
    }

    // ---------------------------------------------------------
    // POSTER ERKENNUNG
    // ---------------------------------------------------------



    private String extractPosterUrl(Element element) {

        if (element == null) {
            return "";
        }

        Elements images = element.select("img");

        if ("img".equalsIgnoreCase(element.tagName())) {
            images.add(0, element);
        }

        for (Element img : images) {

            String[] attributes = {
                    "data-src",
                    "data-original",
                    "data-lazy-src",
                    "data-original-src",
                    "src"
            };

            for (String attribute : attributes) {

                String imageUrl = img.absUrl(attribute);

                if (imageUrl != null
                        && imageUrl.contains("/public/img/cover/")) {

                    return imageUrl;
                }
            }
        }

        return "";
    }


    private String fetchPosterUrl(Show show) {

        if (show == null || show.url == null || show.url.isEmpty()) {
            return "";
        }

        try {

            Document doc = Jsoup.connect(show.url)
                    .cookies(getCookiesFor(show.url))
                    .userAgent(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
                    )
                    .header(
                            "Accept-Language",
                            "de-DE,de;q=0.9,en;q=0.8"
                    )
                    .referrer(BASE + "/")
                    .timeout(5000)
                    .get();

            // Exakte Cover-Position auf der Anime-Detailseite.
            Element cover = doc.selectFirst(
                    ".seriesCoverBox img"
            );

            // Fallback.
            if (cover == null) {
                cover = doc.selectFirst(
                        "img[itemprop=image]"
                );
            }

            if (cover == null) {

                Log.w(
                        "AniWorld",
                        "Kein Cover-Element gefunden: " + show.title
                                + " | " + show.url
                );

                return "";
            }

            String imageUrl = extractPosterUrl(cover);

            if (imageUrl.isEmpty()) {

                Log.w(
                        "AniWorld",
                        "Keine gültige Cover-Adresse: " + show.title
                                + " | " + show.url
                );

                return "";
            }

            logDebug(
                    "Cover gefunden: " + show.title
                            + " | " + imageUrl
            );

            return imageUrl;

        } catch (Exception e) {

            Log.w(
                    "AniWorld",
                    "Detailseite konnte nicht geladen werden: "
                            + show.title + " | " + show.url,
                    e
            );

            return "";
        }
    }

    private String resolveUrl(String value) {

        if (value == null || value.trim().isEmpty()) {
            return "";
        }

        value = value.trim();

        try {
            return new URL(new URL(BASE + "/"), value).toString();
        } catch (Exception e) {
            return "";
        }
    }

    private String extractAnimeTitle(Element link) {

        if (link == null) {
            return "";
        }

        String title = firstNonEmpty(
                link.attr("title"),
                link.attr("data-title"),
                link.attr("aria-label"),
                link.text()
        );

        if (title.isEmpty()) {

            Element img = link.selectFirst("img[alt]");

            if (img != null) {
                title = img.attr("alt").trim();
            }
        }

        return cleanTitle(title);
    }

    private String cleanTitle(String title) {

        if (title == null) {
            return "";
        }

        return title.replaceAll("\\s+", " ")
                .replaceAll("(?i)\\s*(ansehen|mehr lesen|Stream anschauen)$", "")
                .trim();
    }

    private String getAnimeUrlFromEpisodeUrl(String episodeUrl) {

        if (episodeUrl == null) {
            return "";
        }

        try {

            java.util.regex.Matcher matcher =
                    java.util.regex.Pattern
                            .compile("(?i)(https?://[^/]+/anime/[^/]+)")
                            .matcher(episodeUrl);

            if (matcher.find()) {
                return matcher.group(1);
            }

        } catch (Exception e) {
            Log.w("AniWorld", "Anime-URL konnte nicht aus Episode gelesen werden", e);
        }

        return "";
    }

    /*
     * Sucht den Anime-Link in der unmittelbaren Umgebung
     * eines Episoden-Links.
     */
    private Show findAnimeAroundEpisode(
            Element episodeLink,
            Document document
    ) {

        if (episodeLink == null) {
            return null;
        }

        Element current = episodeLink;

        for (int depth = 0; depth < 8 && current != null; depth++) {

            Elements animeLinks =
                    current.select("a[href*='/anime/']");

            for (Element animeLink : animeLinks) {

                String href = animeLink.attr("href").trim();

                if (href.isEmpty()
                        || href.contains("/episode/")) {
                    continue;
                }

                String animeUrl = animeLink.absUrl("href");

                if (animeUrl.isEmpty()) {
                    animeUrl = resolveUrl(href);
                }

                String title = extractAnimeTitle(animeLink);
                String poster = extractPosterUrl(animeLink);

                if (!animeUrl.isEmpty()) {

                    if (title.isEmpty()) {
                        title = titleFromAnimeUrl(animeUrl);
                    }

                    return new Show(title, animeUrl, poster);
                }
            }

            current = current.parent();
        }

        // Zusätzlich die Breadcrumb-Navigation prüfen.
        if (document != null) {

            Elements breadcrumbs = document.select(
                    ".breadcrumb a[href*='/anime/'], "
                            + ".breadcrumbs a[href*='/anime/'], "
                            + "nav a[href*='/anime/'], "
                            + "ol a[href*='/anime/']"
            );

            for (Element animeLink : breadcrumbs) {

                String animeUrl = animeLink.absUrl("href");

                if (animeUrl.isEmpty()) {
                    continue;
                }

                String title = extractAnimeTitle(animeLink);

                if (title.isEmpty()) {
                    title = titleFromAnimeUrl(animeUrl);
                }

                return new Show(
                        title,
                        animeUrl,
                        extractPosterUrl(animeLink)
                );
            }
        }

        // Bei URLs der Form /anime/slug/stream/episode-xxx
        // lässt sich der Anime direkt aus dem Pfad ableiten.
        String animeUrl =
                getAnimeUrlFromEpisodeUrl(
                        episodeLink.absUrl("href")
                );

        if (!animeUrl.isEmpty()) {

            return new Show(
                    titleFromAnimeUrl(animeUrl),
                    animeUrl,
                    ""
            );
        }

        return null;
    }

    private String titleFromAnimeUrl(String url) {

        if (url == null || url.isEmpty()) {
            return "Unbekannter Anime";
        }

        try {

            String path = new URL(url).getPath();

            String[] parts = path.split("/");

            for (int i = 0; i < parts.length; i++) {

                if ("anime".equals(parts[i])
                        && i + 1 < parts.length) {

                    String slug = parts[i + 1];

                    return slug.replace("-", " ")
                            .replace("_", " ")
                            .trim();
                }
            }

        } catch (Exception ignored) {
        }

        return "Unbekannter Anime";
    }

    /*
     * Lädt eine Anime-Seite nach, wenn der Anime zwar über
     * die Episoden-URL gefunden wurde, aber Titel oder Poster
     * noch fehlen.
     */
    private Show enrichAnimeShow(Show show) {

        if (show == null || show.url == null || show.url.isEmpty()) {
            return show;
        }

        if (show.posterUrl != null && !show.posterUrl.isEmpty()
                && show.title != null
                && !show.title.equals("Unbekannter Anime")) {
            return show;
        }

        try {

            Document animeDoc = Jsoup.connect(show.url)
                    .cookies(getCookiesFor(show.url))
                    .userAgent(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
                    )
                    .header(
                            "Accept-Language",
                            "de-DE,de;q=0.9,en;q=0.8"
                    )
                    .referrer(BASE + "/")
                    .timeout(12000)
                    .get();

            String title = show.title;
            String poster = show.posterUrl;

            Element heading = animeDoc.selectFirst(
                    "h1, .series-title, .anime-title"
            );

            if (heading != null
                    && !heading.text().trim().isEmpty()) {
                title = heading.text().trim();
            }

            if (poster == null || poster.isEmpty()) {
                poster = fetchPosterUrlFromDocument(animeDoc);
            }

            if (poster == null || poster.isEmpty()) {

                Element animeAnchor = animeDoc.selectFirst(
                        "a[href*='/anime/'] img"
                );

                if (animeAnchor != null) {
                    poster = firstNonEmpty(
                            animeAnchor.absUrl("data-src"),
                            animeAnchor.absUrl("src")
                    );
                }
            }

            return new Show(
                    cleanTitle(title),
                    show.url,
                    poster == null ? "" : poster
            );

        } catch (Exception e) {

            Log.w(
                    "AniWorld",
                    "Anime-Seite konnte nicht für Poster ausgewertet werden: "
                            + show.url,
                    e
            );

            return show;
        }
    }

    private String fetchPosterUrlFromDocument(Document doc) {
        if (doc == null) {
            return "";
        }
        Element cover = doc.selectFirst(
                ".seriesCoverBox img"
        );
        if (cover == null) {
            cover = doc.selectFirst(
                    "img[itemprop=image]"
            );
        }
        return extractPosterUrl(cover);
    }

    /*
     * Sammelt Anime aus normalen Anime-Links und aus
     * Episoden-Links. Episoden werden auf ihren Anime
     * zurückgeführt und anschließend dedupliziert.
     */
    private List<Show> extractShowsFromDocument(
            Document doc,
            boolean includeEpisodes
    ) {

        List<Show> result = new ArrayList<>();
        Set<String> seen = new HashSet<>();

        // Zuerst direkte Anime-Links verarbeiten.
        Elements animeLinks = doc.select(
                "a[href*='/anime/']"
        );

        for (Element a : animeLinks) {
            String href = a.attr("href").trim();
            if (href.isEmpty()
                    || href.contains("/episode/")) {
                continue;
            }
            String animeUrl = a.absUrl("href");

            if (animeUrl.isEmpty()) {
                animeUrl = resolveUrl(href);
            }

            if (animeUrl.isEmpty()) {
                continue;
            }

            String title = extractAnimeTitle(a);

            if (title.isEmpty()) {
                title = titleFromAnimeUrl(animeUrl);
            }

            String poster = extractPosterUrl(a);

            addShowIfNew(
                    result,
                    seen,
                    new Show(title, animeUrl, poster)
            );
        }

        if (!includeEpisodes) {
            return result;
        }

        /*
         * Neue Folgen und Benachrichtigungen können statt
         * Anime-Links direkte Episoden-Links enthalten.
         */
        Elements episodeLinks = doc.select(
                "a[href*='/episode/'], "
                        + "a[href*='/stream/episode-'], "
                        + "a[href*='/stream/episode/']"
        );

        int checkedEpisodeLinks = 0;

        for (Element episodeLink : episodeLinks) {
            String episodeUrl = episodeLink.absUrl("href");

            if (episodeUrl.isEmpty()) {
                episodeUrl = resolveUrl(
                        episodeLink.attr("href")
                );
            }

            if (episodeUrl.isEmpty()) {
                continue;
            }

            Show anime = findAnimeAroundEpisode(
                    episodeLink,
                    doc
            );

            /*
             * Falls nur eine numerische Episoden-ID vorliegt,
             * muss die Episodenseite selbst untersucht werden.
             * Das wird auf 30 Links begrenzt, damit die Seite
             * nicht unnötig viele Einzelabrufe auslöst.
             */
            if (anime == null
                    && checkedEpisodeLinks < 30) {

                checkedEpisodeLinks++;

                try {

                    Document episodeDoc = Jsoup.connect(episodeUrl)
                            .cookies(getCookiesFor(episodeUrl))
                            .userAgent(
                                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
                            )
                            .referrer(BASE + "/")
                            .timeout(10000)
                            .get();

                    Elements episodeAnimeLinks =
                            episodeDoc.select(
                                    "a[href*='/anime/']"
                            );

                    for (Element animeLink : episodeAnimeLinks) {

                        String animeUrl =
                                animeLink.absUrl("href");

                        if (animeUrl.isEmpty()
                                || animeUrl.contains("/episode/")) {
                            continue;
                        }

                        String title =
                                extractAnimeTitle(animeLink);

                        if (title.isEmpty()) {
                            title = titleFromAnimeUrl(animeUrl);
                        }

                        anime = new Show(
                                title,
                                animeUrl,
                                extractPosterUrl(animeLink)
                        );

                        break;
                    }

                    // Falls die Episodenseite einen Anime-Pfad
                    // enthält, diesen ebenfalls verwenden.
                    if (anime == null) {

                        String derivedUrl =
                                getAnimeUrlFromEpisodeUrl(episodeUrl);

                        if (!derivedUrl.isEmpty()) {
                            anime = new Show(
                                    titleFromAnimeUrl(derivedUrl),
                                    derivedUrl,
                                    ""
                            );
                        }
                    }

                } catch (Exception e) {

                    Log.w(
                            "AniWorld",
                            "Anime-Zuordnung für Episode fehlgeschlagen: "
                                    + episodeUrl,
                            e
                    );
                }
            }

            if (anime == null) {
                logDebug(
                        "Kein Anime für Episoden-Link gefunden: "
                                + episodeUrl
                );
                continue;
            }

            anime = enrichAnimeShow(anime);

            addShowIfNew(result, seen, anime);
        }

        return result;
    }

    private void addShowIfNew(
            List<Show> result,
            Set<String> seen,
            Show show
    ) {

        if (show == null
                || show.url == null
                || show.url.isEmpty()) {
            return;
        }

        String key = show.url
                .replaceAll("/+$", "")
                .toLowerCase(Locale.ROOT);

        if (seen.contains(key)) {
            return;
        }

        seen.add(key);
        result.add(show);
    }

    // ---------------------------------------------------------
    // POSTER DOWNLOAD UND CACHE
    // ---------------------------------------------------------


    private File getPosterFile(String imageUrl) throws Exception {

        File posterDirectory = new File(
                getFilesDir(),
                "posters"
        );

        if (!posterDirectory.exists()
                && !posterDirectory.mkdirs()) {

            throw new Exception(
                    "Poster-Cache-Ordner konnte nicht erstellt werden"
            );
        }

        MessageDigest digest =
                MessageDigest.getInstance("SHA-256");

        byte[] hash = digest.digest(
                imageUrl.getBytes("UTF-8")
        );

        StringBuilder hex = new StringBuilder();

        for (byte b : hash) {
            hex.append(String.format("%02x", b));
        }

        return new File(
                posterDirectory,
                hex.toString() + ".img"
        );
    }

    private void cancelPosterBatch() {

        PosterBatch batch = activePosterBatch;

        if (batch == null || batch.cancelled) {
            return;
        }

        batch.cancelled = true;

        logInfo("Poster-Verarbeitung wird abgebrochen: " + batch.finished.get() + "/" + batch.total);

        // Alle noch wartenden und laufenden Aufgaben abbrechen.
        synchronized (batch.tasks) {
            for (Future<?> task : batch.tasks) {
                task.cancel(true);
            }
            batch.tasks.clear();
        }

        // Aktive Bild-Downloads sofort unterbrechen.
        synchronized (batch.connections) {
            for (HttpURLConnection connection : batch.connections) {
                try {
                    connection.disconnect();
                } catch (Exception ignored) {
                }
            }
            batch.connections.clear();
        }

        // Abgebrochene Aufgaben aus der Executor-Warteschlange entfernen.
        imageExecutor.purge();

        activePosterBatch = null;
    }

    private Bitmap decodePoster(File file) {

        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;

        BitmapFactory.decodeFile(
                file.getAbsolutePath(),
                bounds
        );

        int reqWidth = dp(150);
        int reqHeight = dp(225);

        int sampleSize = 1;

        while (
                bounds.outWidth / (sampleSize * 2) >= reqWidth
                        && bounds.outHeight / (sampleSize * 2) >= reqHeight
        ) {
            sampleSize *= 2;
        }

        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sampleSize;

        // Spart gegenüber ARGB_8888 ungefähr die Hälfte des Bitmap-RAMs.
        options.inPreferredConfig = Bitmap.Config.RGB_565;

        return BitmapFactory.decodeFile(
                file.getAbsolutePath(),
                options
        );
    }

    private void loadPoster(
            ImageView imageView,
            TextView placeholder,
            Show show,
            PosterBatch batch
    ) {
        imageView.setTag(show.url);

        synchronized (batch.tasks) {

            if (batch.cancelled) {
                return;
            }

            Future<?> task = imageExecutor.submit(() -> {

                Bitmap bitmap = null;
                String imageUrl = show.posterUrl;

                boolean downloaded = false;

                try {

                    if (batch.cancelled
                            || Thread.currentThread().isInterrupted()) {
                        return;
                    }

                    // 1. Gespeicherten Poster-Link verwenden.
                    if (imageUrl == null || imageUrl.isEmpty()) {
                        imageUrl = getCachedPosterUrl(show.url);
                    }

                    // 2. Nur wenn kein Link gespeichert ist,
                    // die Anime-Detailseite abrufen.
                    if (imageUrl == null || imageUrl.isEmpty()) {
                        imageUrl = fetchPosterUrl(show);
                    }

                    if (batch.cancelled
                            || Thread.currentThread().isInterrupted()) {
                        return;
                    }

                    if (imageUrl == null || imageUrl.isEmpty()) {
                        batch.failed.incrementAndGet();

                        Log.w(
                                "AniWorld",
                                "Kein Poster verfügbar: " + show.title
                        );

                        return;
                    }

                    show.posterUrl = imageUrl;
                    saveCachedPosterUrl(show.url, imageUrl);

                    // 3. RAM-Cache prüfen.
                    bitmap = posterCache.get(imageUrl);

                    if (bitmap != null) {
                        batch.memoryHits.incrementAndGet();
                    }

                    // 4. Festplatten-Cache prüfen.
                    if (bitmap == null) {

                        File posterFile = getPosterFile(imageUrl);

                        if (posterFile.exists() && posterFile.length() > 0) {

                            bitmap = decodePoster(posterFile);

                            if (bitmap != null) {
                                batch.diskHits.incrementAndGet();
                                posterCache.put(imageUrl, bitmap);
                            }
                        }
                    }

                    // 5. Poster herunterladen, falls nicht im Cache.
                    if (bitmap == null) {

                        if (batch.cancelled
                                || Thread.currentThread().isInterrupted()) {
                            return;
                        }

                        URL url = new URL(imageUrl);

                        HttpURLConnection connection =
                                (HttpURLConnection) url.openConnection();

                        synchronized (batch.connections) {

                            if (batch.cancelled) {
                                connection.disconnect();
                                return;
                            }

                            batch.connections.add(connection);
                        }

                        try {

                            connection.setConnectTimeout(5000);
                            connection.setReadTimeout(5000);
                            connection.setRequestMethod("GET");
                            connection.setRequestProperty(
                                    "User-Agent",
                                    "Mozilla/5.0"
                            );

                            connection.connect();

                            if (connection.getResponseCode()
                                    != HttpURLConnection.HTTP_OK) {
                                throw new IOException(
                                        "HTTP-Fehler: "
                                                + connection.getResponseCode()
                                );
                            }

                            File posterFile = getPosterFile(imageUrl);

                            File parent = posterFile.getParentFile();

                            if (parent != null && !parent.exists()) {
                                parent.mkdirs();
                            }

                            try (
                                    InputStream input =
                                            connection.getInputStream();

                                    FileOutputStream output =
                                            new FileOutputStream(posterFile)
                            ) {

                                byte[] buffer = new byte[8192];
                                int length;

                                while ((length = input.read(buffer)) != -1) {

                                    if (batch.cancelled
                                            || Thread.currentThread()
                                            .isInterrupted()) {
                                        return;
                                    }

                                    output.write(buffer, 0, length);
                                }

                                output.flush();
                            }

                            if (batch.cancelled
                                    || Thread.currentThread().isInterrupted()) {
                                return;
                            }

                            bitmap = decodePoster(posterFile);

                            if (bitmap != null) {
                                downloaded = true;
                                posterCache.put(imageUrl, bitmap);
                            }

                        } finally {

                            synchronized (batch.connections) {
                                batch.connections.remove(connection);
                            }

                            connection.disconnect();
                        }
                    }

                    if (bitmap == null) {
                        batch.failed.incrementAndGet();

                        Log.w(
                                "AniWorld",
                                "Poster konnte nicht geladen werden: "
                                        + show.title
                        );

                        return;
                    }

                    // 6. Nur dann UI aktualisieren, wenn der Batch noch aktiv ist.
                    if (batch.cancelled
                            || Thread.currentThread().isInterrupted()) {
                        return;
                    }

                    Bitmap finalBitmap = bitmap;

                    mainHandler.post(() -> {
                        if (batch.cancelled) {
                            return;
                        }
                        Object tag = imageView.getTag();

                        if (tag != null && tag.equals(show.url)) {
                            imageView.setImageBitmap(finalBitmap);
                            imageView.setVisibility(View.VISIBLE);

                            if (placeholder != null) {
                                placeholder.setVisibility(View.GONE);
                            }
                        }
                    });

                    if (downloaded) {
                        batch.downloaded.incrementAndGet();
                    }

                } catch (Exception e) {

                    if (!batch.cancelled) {

                        batch.failed.incrementAndGet();

                        Log.e(
                                "AniWorld",
                                "Poster-Fehler bei "
                                        + show.title + " | " + show.url,
                                e
                        );
                    }

                } finally {

                    if (!batch.cancelled) {
                        finishPosterTask(batch);
                    }
                }
            });

            batch.tasks.add(task);
        }
    }


    private void finishPosterTask(PosterBatch batch) {

        int finished = batch.finished.incrementAndGet();

        if (finished % 25 == 0 || finished == batch.total) {

            logInfo("Poster-Fortschritt: "
                    + finished + "/" + batch.total
                    + " | Neu heruntergeladen: "
                    + batch.downloaded.get()
                    + " | Festplatten-Cache: "
                    + batch.diskHits.get()
                    + " | RAM-Cache: "
                    + batch.memoryHits.get()
                    + " | Fehler: "
                    + batch.failed.get()
            );
        }

        if (finished == batch.total) {

            logInfo("Poster-Verarbeitung abgeschlossen: "
                    + finished + "/" + batch.total
                    + " | Neu: " + batch.downloaded.get()
                    + " | Festplatten-Cache: "
                    + batch.diskHits.get()
                    + " | RAM-Cache: "
                    + batch.memoryHits.get()
                    + " | Fehler: " + batch.failed.get()
            );
        }
    }

    // ---------------------------------------------------------
    // KATALOG LADEN
    // ---------------------------------------------------------

    private void loadCatalog(
            String url,
            String title
    ) {
        cancelPosterBatch();
        currentUrl = url;
        currentTitle = title;

        sectionTitle.setText(title);

        showCatalog();

        catalog.removeAllViews();

        addMessage("Lade Inhalte …");

        io.execute(() -> {

            List<Show> result = new ArrayList<>();
            String error = null;

            try {

                Document doc = Jsoup.connect(url)
                        .cookies(getCookiesFor(url))
                        .userAgent(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
                        )
                        .header(
                                "Accept-Language",
                                "de-DE,de;q=0.9,en;q=0.8"
                        )
                        .referrer(BASE + "/")
                        .timeout(20000)
                        .get();

                boolean includeEpisodes =
                        url.contains("/neue-episoden")
                                || url.contains("/account/notifications")
                                || url.contains("/account/notification");

                result = extractShowsFromDocument(
                        doc,
                        includeEpisodes
                );

                if (result.isEmpty()) {
                    error = "Auf der Seite wurden keine Anime gefunden. "
                            + "Möglicherweise ist eine Anmeldung erforderlich "
                            + "oder die Seitenstruktur hat sich geändert.";
                }

            } catch (Exception e) {

                error = "AniWorld konnte nicht geladen werden: "
                        + e.getMessage();
            }

            final String err = error;
            final List<Show> data = result;

            runOnUiThread(() -> {

                catalog.removeAllViews();

                currentShows.clear();
                currentShows.addAll(data);

                if (err != null) {
                    pendingFirstAnimeFocus = false;
                    addMessage(err);
                } else {
                    renderShows(data);
                }
            });
        });
    }

    // ---------------------------------------------------------
    // SUCHE
    // ---------------------------------------------------------

    private void search(String query) {
        cancelPosterBatch();

        String searchQuery = normalizeSearch(query);

        if (searchQuery.isEmpty()) {
            loadCatalog(BASE + "/animes-alphabet", "Alle Anime");
            return;
        }

        rememberSearch(query);
        closeSearch();
        level = 0;

        currentUrl = BASE + "/animes-alphabet";
        currentTitle = "Suche: " + query;

        sectionTitle.setText(currentTitle);

        showCatalog();

        catalog.removeAllViews();

        addMessage("Lade vollständigen Anime-Katalog …");

        io.execute(() -> {

            List<Show> results = new ArrayList<>();
            String error = null;

            try {

                Document doc = Jsoup.connect(BASE + "/animes-alphabet")
                        .cookies(getCookiesFor(BASE + "/animes-alphabet"))
                        .userAgent(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
                        )
                        .header(
                                "Accept-Language",
                                "de-DE,de;q=0.9,en;q=0.8"
                        )
                        .referrer(BASE + "/")
                        .timeout(30000)
                        .get();

                // Alle Anime von der alphabetischen Übersichtsseite laden.
                List<Show> allShows =
                        extractShowsFromDocument(doc, false);

                logInfo(
                        "Anime im vollständigen Katalog gefunden: "
                                + allShows.size()
                );

                for (Show show : allShows) {

                    String normalizedName =
                            normalizeSearch(show.title);

                    if (normalizedName.contains(searchQuery)) {
                        results.add(show);
                    }
                }

                if (results.isEmpty()) {
                    error = "Keine Anime für \"" + query + "\" gefunden.";
                }

            } catch (Exception e) {

                Log.e("AniWorld", "Suche fehlgeschlagen", e);

                error = "Suche fehlgeschlagen: " + e.getMessage();
            }

            final String err = error;
            final List<Show> data = results;

            runOnUiThread(() -> {

                catalog.removeAllViews();

                currentShows.clear();
                currentShows.addAll(data);

                if (err != null) {
                    addMessage(err);
                } else {
                    renderShows(data);
                }
            });
        });
    }

    private String normalizeSearch(String text) {

        if (text == null) {
            return "";
        }

        return java.text.Normalizer.normalize(
                        text.toLowerCase(Locale.ROOT),
                        java.text.Normalizer.Form.NFD
                )
                .replaceAll("\\p{M}", "")
                .replaceAll("[^a-z0-9]", "");
    }

    // ---------------------------------------------------------
    // POSTER KATALOG
    // ---------------------------------------------------------

    private void renderShows(List<Show> shows) {

        if (shows == null || shows.isEmpty()) {
            pendingFirstAnimeFocus = false;
            addMessage("Keine Anime gefunden.");
            return;
        }

        // Eventuell noch laufende Poster der vorherigen Ansicht abbrechen.
        cancelPosterBatch();

        logInfo(
                "Katalog wird schrittweise aufgebaut: " + shows.size()
                        + " Anime"
        );

        HorizontalScrollView horizontalScroll =
                new HorizontalScrollView(this);

        horizontalScroll.setHorizontalScrollBarEnabled(false);
        horizontalScroll.setVerticalScrollBarEnabled(false);
        horizontalScroll.setFillViewport(false);
        horizontalScroll.setClipChildren(false);
        horizontalScroll.setClipToPadding(false);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.TOP);
        row.setPadding(dp(12), 0, 0, 0);
        row.setClipChildren(false);
        row.setClipToPadding(false);

        horizontalScroll.addView(row);
        catalog.addView(horizontalScroll);

        PosterBatch posterBatch = new PosterBatch(shows.size());
        activePosterBatch = posterBatch;

        // Beim Scrollen werden nur sichtbare und unmittelbar benachbarte
        // Karten zum Laden ihrer Poster freigegeben.
        horizontalScroll.getViewTreeObserver().addOnScrollChangedListener(
                () -> loadVisiblePosters(
                        horizontalScroll,
                        row,
                        posterBatch
                )
        );

        final int[] nextIndex = {0};
        final int cardsPerBatch = 8;

        Runnable renderNextBatch = new Runnable() {
            @Override
            public void run() {

                if (posterBatch.cancelled
                        || activePosterBatch != posterBatch
                        || isFinishing()
                        || isDestroyed()) {
                    return;
                }

                int end = Math.min(
                        nextIndex[0] + cardsPerBatch,
                        shows.size()
                );

                while (nextIndex[0] < end) {

                    Show show = shows.get(nextIndex[0]);
                    LinearLayout card = createShowCard(show, horizontalScroll);

                    row.addView(
                            card,
                            createShowCardLayoutParams()
                    );

                    nextIndex[0]++;
                }

                // Nach jeder kleinen Gruppe das Layout aktualisieren und
                // Poster für den aktuellen sichtbaren Bereich starten.
                horizontalScroll.post(() ->
                        loadVisiblePosters(
                                horizontalScroll,
                                row,
                                posterBatch
                        )
                );

                if (pendingFirstAnimeFocus
                        && isViewInsideNavigation(getCurrentFocus())
                        && row.getChildCount() > 0) {
                    pendingFirstAnimeFocus = false;
                    horizontalScroll.post(() -> {
                        if (isViewInsideNavigation(getCurrentFocus())
                                && row.getChildCount() > 0) {
                            row.getChildAt(0).requestFocus();
                        }
                    });
                }

                if (nextIndex[0] < shows.size()) {
                    mainHandler.postDelayed(this, 16);
                } else {
                    View endSpacer = new View(MainActivity.this);
                    row.addView(endSpacer, new LinearLayout.LayoutParams(
                            horizontalScroll.getWidth(), 1
                    ));
                    logInfo("Alle Anime-Karten erstellt: " + shows.size());
                }
            }
        };

        mainHandler.post(renderNextBatch);
    }

    private LinearLayout createShowCard(Show show, HorizontalScrollView horizontalScroll) {

        LinearLayout card = new LinearLayout(this);

        card.setOrientation(LinearLayout.VERTICAL);
        card.setGravity(Gravity.TOP);
        card.setFocusable(true);
        card.setClickable(true);
        card.setClipChildren(false);
        card.setClipToPadding(false);

        card.setBackground(
                round(
                        CARD_BACKGROUND,
                        0xFF333333,
                        8
                )
        );

        // Feste Posterfläche im Seitenverhältnis 2:3.
        FrameLayout posterFrame = new FrameLayout(this);

        posterFrame.setBackground(
                round(
                        0xFF252525,
                        0xFF333333,
                        8
                )
        );

        posterFrame.setClipToOutline(true);

        ImageView poster = new ImageView(this);
        poster.setScaleType(ImageView.ScaleType.CENTER_CROP);
        poster.setBackgroundColor(0xFF252525);
        poster.setFocusable(false);

        posterFrame.addView(
                poster,
                new FrameLayout.LayoutParams(
                        FrameLayout.LayoutParams.MATCH_PARENT,
                        FrameLayout.LayoutParams.MATCH_PARENT
                )
        );

        // Platzhalter bleibt sichtbar, bis das Poster erfolgreich geladen ist.
        TextView placeholder = new TextView(this);

        String initial = show.title == null
                ? "?"
                : show.title.trim();

        if (initial.length() > 2) {
            initial = initial.substring(0, 2);
        }

        placeholder.setText(initial.toUpperCase(Locale.ROOT));
        placeholder.setTextColor(0xFF777777);
        placeholder.setTextSize(30);
        placeholder.setTypeface(null, Typeface.BOLD);
        placeholder.setGravity(Gravity.CENTER);
        placeholder.setBackground(
                round(0xFF252525, 0xFF333333, 8)
        );

        posterFrame.addView(
                placeholder,
                new FrameLayout.LayoutParams(
                        FrameLayout.LayoutParams.MATCH_PARENT,
                        FrameLayout.LayoutParams.MATCH_PARENT
                )
        );

        LinearLayout.LayoutParams imageParams =
                new LinearLayout.LayoutParams(
                        dp(150),
                        dp(225)
                );

        card.addView(posterFrame, imageParams);

        // PosterCard wird am Card-Tag gespeichert und erst bei Bedarf geladen.
        card.setTag(new PosterCard(poster, placeholder, show));

        TextView title = new TextView(this);
        title.setText(show.title);
        title.setTextColor(Color.WHITE);
        title.setTextSize(14);
        title.setTypeface(null, Typeface.BOLD);
        title.setGravity(Gravity.TOP | Gravity.START);
        title.setPadding(
                dp(5),
                dp(10),
                dp(5),
                dp(8)
        );
        title.setMaxLines(2);
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);

        LinearLayout.LayoutParams titleParams =
                new LinearLayout.LayoutParams(
                        dp(150),
                        dp(52)
                );

        card.addView(title, titleParams);

        card.setOnFocusChangeListener((v, hasFocus) -> {

            if (hasFocus) {
                card.setBackground(
                        round(
                                0xFF292019,
                                ORANGE,
                                8
                        )
                );
                card.setScaleX(1.12f);
                card.setScaleY(1.12f);
                card.setElevation(dp(8));
                card.post(() -> horizontalScroll.smoothScrollTo(
                        Math.max(0, card.getLeft() - dp(12)),
                        horizontalScroll.getScrollY()
                ));

            } else {
                card.setBackground(
                        round(
                                CARD_BACKGROUND,
                                0xFF333333,
                                8
                        )
                );
                card.setScaleX(1.0f);
                card.setScaleY(1.0f);
            }
        });

        card.setOnClickListener(v -> openSeries(show));

        return card;
    }

    private LinearLayout.LayoutParams createShowCardLayoutParams() {

        LinearLayout.LayoutParams cardParams =
                new LinearLayout.LayoutParams(
                        dp(150),
                        dp(277)
                );

        cardParams.setMargins(
                0,
                dp(4),
                dp(18),
                dp(12)
        );

        return cardParams;
    }

    private void loadVisiblePosters(
            HorizontalScrollView horizontalScroll,
            LinearLayout row,
            PosterBatch posterBatch
    ) {

        if (posterBatch.cancelled
                || activePosterBatch != posterBatch
                || horizontalScroll.getWidth() <= 0) {
            return;
        }

        int scrollLeft = horizontalScroll.getScrollX();
        int viewportWidth = horizontalScroll.getWidth();
        int preloadDistance = Math.max(viewportWidth, dp(450));

        int visibleLeft = Math.max(0, scrollLeft - preloadDistance);
        int visibleRight = scrollLeft + viewportWidth + preloadDistance;

        for (int i = 0; i < row.getChildCount(); i++) {

            View child = row.getChildAt(i);

            if (child.getRight() < visibleLeft) {
                continue;
            }

            if (child.getLeft() > visibleRight) {
                break;
            }

            Object tag = child.getTag();

            if (!(tag instanceof PosterCard)) {
                continue;
            }

            PosterCard posterCard = (PosterCard) tag;

            if (posterCard.requested) {
                continue;
            }

            posterCard.requested = true;

            loadPoster(
                    posterCard.imageView,
                    posterCard.placeholder,
                    posterCard.show,
                    posterBatch
            );
        }
    }

    // ---------------------------------------------------------
    // STAFFELN
    // ---------------------------------------------------------

    private void openSeries(Show show) {
        cancelPosterBatch();

        selectedAnime = show;
        level = 1;
        sectionTitle.setText(show.title);
        catalog.removeAllViews();
        addMessage("Lade Staffeln …");
        focusSelectedNavigationButtonWithoutLoading();

        io.execute(() -> {

            List<Show> items = new ArrayList<>();
            String error = null;

            try {

                Document doc = Jsoup.connect(show.url)
                        .cookies(getCookiesFor(show.url))
                        .userAgent(
                                "Mozilla/5.0 (Linux; Android 10; Fire TV) AppleWebKit/537.36 Chrome/120 Safari/537.36"
                        )
                        .timeout(18000)
                        .get();

                Elements seasons =
                        doc.select(".hosterSiteDirectNav a[href]");

                if (seasons.isEmpty()) {
                    seasons = doc.select(
                            "a[href*=/staffel], a[href*=/filme]"
                    );
                }

                for (Element a : seasons) {

                    String href = a.attr("href").trim();
                    String title = a.attr("title").trim();

                    if (title.isEmpty()) {
                        title = a.text().trim();
                    }

                    String lowerHref =
                            href.toLowerCase(Locale.ROOT);

                    if (href.isEmpty()
                            || !(lowerHref.contains("staffel")
                            || lowerHref.contains("filme"))) {
                        continue;
                    }

                    if (title.isEmpty()) {
                        title = "Staffel";
                    }

                    String fullUrl = a.absUrl("href");

                    if (!fullUrl.isEmpty()
                            && !containsUrl(items, fullUrl)) {

                        items.add(
                                new Show(title, fullUrl)
                        );
                    }
                }

                if (items.isEmpty()) {
                    error = "Auf dieser Anime-Seite wurden keine Staffeln gefunden.";
                }

            } catch (Exception e) {

                error = "Staffeln konnten nicht geladen werden: "
                        + e.getMessage();
            }

            final String err = error;
            final List<Show> data = items;

            runOnUiThread(() -> {

                catalog.removeAllViews();

                if (err != null) {

                    addMessage(err);

                    addAction(
                            "Anime-Seite im Player öffnen",
                            () -> openPlayer(show.url)
                    );

                } else {

                    renderSeasons(data);
                }
            });
        });
    }

    private void renderSeasons(List<Show> seasons) {

        level = 1;

        for (Show season : seasons) {

            if (season.title != null
                    && !season.title.contains("Episode")) {

                addAction(
                        season.title,
                        () -> loadEpisodes(season)
                );
            }
        }
    }

    // ---------------------------------------------------------
    // EPISODEN
    // ---------------------------------------------------------

    private void loadEpisodes(Show season) {
        cancelPosterBatch();

        selectedSeason = season;
        selectedEpisode = null;
        level = 2;
        sectionTitle.setText(season.title);
        catalog.removeAllViews();
        addMessage("Lade Episoden …");
        focusSelectedNavigationButtonWithoutLoading();

        io.execute(() -> {

            List<Show> episodes = new ArrayList<>();
            String error = null;

            try {

                Document doc = Jsoup.connect(season.url)
                        .cookies(getCookiesFor(season.url))
                        .userAgent(
                                "Mozilla/5.0 (Linux; Android 10; Fire TV) AppleWebKit/537.36 Chrome/120 Safari/537.36"
                        )
                        .timeout(18000)
                        .get();

                Element table =
                        doc.selectFirst("table.seasonEpisodesList");

                Elements links = table != null
                        ? table.select("tr a[href]")
                        : doc.select("a[href*=/episode/]");

                for (Element a : links) {

                    String href = a.attr("href").trim();

                    if (href.isEmpty()) {
                        continue;
                    }

                    String fullUrl = a.absUrl("href");

                    if (fullUrl.isEmpty()
                            || containsUrl(episodes, fullUrl)) {
                        continue;
                    }

                    String title = extractEpisodeTitle(
                            a,
                            episodes.size() + 1
                    );

                    Show episode = new Show(title, fullUrl);
                    Element tr = a.parent().parent();
                    episode.seen = (tr != null && tr.hasClass("seen"));

                    episodes.add(episode);
                }

                if (episodes.isEmpty()) {

                    Elements fallback =
                            doc.select("a[href*=/episode/]");

                    for (Element a : fallback) {

                        String fullUrl = a.absUrl("href");

                        if (fullUrl.isEmpty()
                                || containsUrl(episodes, fullUrl)) {
                            continue;
                        }

                        String title = extractEpisodeTitle(
                                a,
                                episodes.size() + 1
                        );

                        Show episode = new Show(title, fullUrl);
                        Element tr = a.parent().parent();
                        episode.seen = (tr != null && tr.hasClass("seen"));

                        episodes.add(episode);
                    }
                }

                if (episodes.isEmpty()) {
                    error = "In dieser Staffel wurden keine Episoden gefunden.";
                }

            } catch (Exception e) {

                error = "Episoden konnten nicht geladen werden: "
                        + e.getMessage();
            }

            final String err = error;
            final List<Show> data = episodes;

            runOnUiThread(() -> {

                catalog.removeAllViews();

                if (err != null) {

                    addMessage(err);

                } else {

                    for (Show episode : data) {

                        String label = episode.seen
                                ? "✓  " + episode.title
                                : episode.title;

                        addAction(
                                label,
                                () -> openEpisode(episode)
                        );
                    }
                }
            });
        });
    }

    private String extractEpisodeTitle(
            Element link,
            int fallbackNumber
    ) {

        String linkText = link.text().trim();

        String title = firstNonEmpty(
                link.attr("title"),
                link.attr("data-title"),
                link.attr("aria-label")
        );

        Element row = link;

        while (row != null
                && !"tr".equalsIgnoreCase(row.tagName())) {

            row = row.parent();
        }

        if (row != null) {

            Element titleElement = row.selectFirst(
                    ".episodeTitle, .episode-title, .episodeName, .episode-name, "
                            + "[class*=episodeTitle], [class*=episodeName], [data-title]"
            );

            if (titleElement != null
                    && titleElement != link) {

                String rowTitle = firstNonEmpty(
                        titleElement.attr("data-title"),
                        titleElement.attr("title"),
                        titleElement.text()
                );

                if (!rowTitle.isEmpty()
                        && !isEpisodeNumberOnly(rowTitle)) {

                    title = rowTitle;
                }
            }

            if (title.isEmpty()
                    || isEpisodeNumberOnly(title)) {

                Elements cells = row.select("td");

                int linkCellIndex = -1;

                for (int i = 0; i < cells.size(); i++) {

                    Element cellLink =
                            cells.get(i).selectFirst("a[href]");

                    if (cellLink != null
                            && cellLink.equals(link)) {

                        linkCellIndex = i;
                        break;
                    }
                }

                if (linkCellIndex >= 0) {

                    for (int i = linkCellIndex + 1;
                         i < cells.size();
                         i++) {

                        Element cell = cells.get(i);

                        String candidate = firstNonEmpty(
                                cell.attr("data-title"),
                                cell.attr("title"),
                                cell.text()
                        );

                        if (!candidate.isEmpty()
                                && !isEpisodeNumberOnly(candidate)) {

                            title = candidate;
                            break;
                        }
                    }
                }

                if (title.isEmpty()
                        || isEpisodeNumberOnly(title)) {

                    for (Element cell : cells) {

                        String candidate = cell.text().trim();

                        if (!candidate.isEmpty()
                                && !isEpisodeNumberOnly(candidate)
                                && !candidate.equals(linkText)) {

                            title = candidate;
                            break;
                        }
                    }
                }
            }
        }

        if (title.isEmpty()
                || isEpisodeNumberOnly(title)) {

            if (!linkText.isEmpty()
                    && !isEpisodeNumberOnly(linkText)) {

                title = linkText;
            }
        }

        if (title.isEmpty()
                || isEpisodeNumberOnly(title)) {

            String number =
                    linkText.replaceAll("[^0-9]", "");

            if (number.isEmpty()) {

                java.util.regex.Matcher matcher =
                        java.util.regex.Pattern
                                .compile("/episode/(\\d+)")
                                .matcher(link.attr("href"));

                if (matcher.find()) {
                    number = matcher.group(1);
                }
            }

            if (number.isEmpty()) {
                number = String.valueOf(fallbackNumber);
            }

            return "Episode " + number;
        }

        if (isEpisodeNumberOnly(linkText)
                && !title.toLowerCase(Locale.ROOT)
                .startsWith("episode ")
                && !title.toLowerCase(Locale.ROOT)
                .startsWith("folge ")) {

            String number =
                    linkText.replaceAll("[^0-9]", "");

            if (!number.isEmpty()) {
                return "Episode " + number + " – " + title;
            }
        }

        return title.replaceAll("\\s+", " ").trim();
    }

    private String firstNonEmpty(String... values) {

        for (String value : values) {

            if (value != null
                    && !value.trim().isEmpty()) {

                return value.trim();
            }
        }

        return "";
    }

    private boolean isEpisodeNumberOnly(String value) {

        if (value == null) {
            return true;
        }

        return value.trim().matches(
                "(?i)^(episode|folge)?\\s*\\d+(\\s*[./-]\\s*\\d+)?$"
        );
    }

    // ---------------------------------------------------------
    // HOSTER
    // ---------------------------------------------------------

    private void openEpisode(Show episode) {
        cancelPosterBatch();
        cancelEpisodeWatchTimer();

        currentEpisodeId = null;
        currentEpisodeMarked = false;
        selectedEpisode = episode;

        level = 3;

        catalog.removeAllViews();

        sectionTitle.setText(episode.title);

        addMessage("Suche Video-Hoster …");
        focusSelectedNavigationButtonWithoutLoading();

        io.execute(() -> {

            List<StreamHoster> hosters = new ArrayList<>();

            String error = null;
            String parsedEpisodeId = "";

            try {

                Document doc = Jsoup.connect(episode.url)
                        .cookies(getCookiesFor(episode.url))
                        .userAgent(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
                        )
                        .header(
                                "Accept-Language",
                                "de-DE,de;q=0.9,en;q=0.8"
                        )
                        .referrer(BASE + "/")
                        .timeout(20000)
                        .get();

                Element episodeTitleElement =
                        doc.selectFirst(
                                ".hosterSiteTitle[data-episode-id]"
                        );

                parsedEpisodeId =
                        episodeTitleElement != null
                                ? episodeTitleElement
                                .attr("data-episode-id")
                                .trim()
                                : "";

                Elements languageRows = doc.select(
                        ".hosterSiteVideo ul li[data-lang-key], li.episodeLink[data-lang-key]"
                );

                for (Element li : languageRows) {

                    String languageKey =
                            li.attr("data-lang-key").trim();

                    String language;
                    int priority;

                    switch (languageKey) {

                        case "1":
                            language = "Deutsch";
                            priority = 1;
                            break;

                        case "3":
                            language = "Deutsch mit Untertiteln";
                            priority = 2;
                            break;

                        case "2":
                            language = "Englisch mit Untertiteln";
                            priority = 3;
                            break;

                        default:
                            language = "Weitere Sprache";
                            priority = 99;
                            break;
                    }

                    String target =
                            li.attr("data-link-target").trim();

                    Element link = li.selectFirst("a[href]");

                    if (target.isEmpty() && link != null) {
                        target = link.attr("href").trim();
                    }

                    if (target.isEmpty()) {
                        continue;
                    }

                    String hosterName = "";

                    Element heading = li.selectFirst("h4");

                    if (heading != null) {
                        hosterName = heading.text().trim();
                    }

                    if (hosterName.isEmpty() && link != null) {
                        hosterName = link.text().trim();
                    }

                    if (hosterName.isEmpty()) {
                        hosterName = li.text().trim();
                    }

                    if (hosterName.isEmpty()) {
                        hosterName = "Hoster";
                    }

                    String absoluteUrl = new URL(
                            new URL(episode.url),
                            target
                    ).toString();

                    boolean duplicate = false;

                    for (StreamHoster existing : hosters) {

                        if (existing.url.equals(absoluteUrl)) {
                            duplicate = true;
                            break;
                        }
                    }

                    if (!duplicate) {

                        hosters.add(
                                new StreamHoster(
                                        hosterName,
                                        absoluteUrl,
                                        language,
                                        priority
                                )
                        );
                    }
                }

                if (hosters.isEmpty()) {

                    for (Element li : doc.select(
                            "li.episodeLink, li[data-link-target]"
                    )) {

                        String target =
                                li.attr("data-link-target").trim();

                        Element link = li.selectFirst("a[href]");

                        if (target.isEmpty() && link != null) {
                            target = link.attr("href").trim();
                        }

                        if (target.isEmpty()) {
                            continue;
                        }

                        String name = "";

                        Element heading = li.selectFirst("h4");

                        if (heading != null) {
                            name = heading.text().trim();
                        }

                        if (name.isEmpty() && link != null) {
                            name = link.text().trim();
                        }

                        if (name.isEmpty()) {
                            name = "Hoster";
                        }

                        String absoluteUrl = new URL(
                                new URL(episode.url),
                                target
                        ).toString();

                        boolean duplicate = false;

                        for (StreamHoster existing : hosters) {

                            if (existing.url.equals(absoluteUrl)) {
                                duplicate = true;
                                break;
                            }
                        }

                        if (!duplicate) {

                            hosters.add(
                                    new StreamHoster(
                                            name,
                                            absoluteUrl,
                                            "Sprache unbekannt",
                                            99
                                    )
                            );
                        }
                    }
                }

                filterAndSortHosters(hosters);

                if (hosters.isEmpty()) {
                    error = "Auf der Episodenseite wurden keine Hoster-Links gefunden.";
                }

            } catch (Exception e) {

                error = "Hoster konnten nicht geladen werden: "
                        + e.getMessage();
            }

            final String err = error;
            final List<StreamHoster> data = hosters;
            final String episodeId = parsedEpisodeId;

            runOnUiThread(() -> {

                catalog.removeAllViews();

                sectionTitle.setText(episode.title);

                currentEpisodeId = episodeId;
                currentEpisodeMarked = false;

                if (err != null) {

                    addMessage(err);

                    addAction(
                            "Episodenseite im Browser öffnen",
                            () -> openPlayer(episode.url)
                    );

                } else {

                    String currentLanguage = null;

                    for (StreamHoster hoster : data) {

                        if (!hoster.language.equals(currentLanguage)) {

                            currentLanguage = hoster.language;

                            addMessage(currentLanguage);
                        }

                        addAction(
                                hoster.title + "  ·  Abspielen",
                                () -> {
                                    io.execute(() -> {
                                        try {
                                            String resolvedUrl = resolveRedirect(hoster.url);

                                            runOnUiThread(() -> {
                                                if (resolvedUrl.toLowerCase(Locale.ROOT).contains("vidmoly")) {
                                                    startEpisodeWatchTimer();
                                                    openVidmolyPlayer(resolvedUrl);
                                                } else if (hoster.title != null
                                                        && hoster.title.trim().equalsIgnoreCase("VOE")) {
                                                    startEpisodeWatchTimer();
                                                    openVOEPlayer(resolvedUrl);
                                                } else if (resolvedUrl.toLowerCase(Locale.ROOT).contains("voe.sx")
                                                        || resolvedUrl.toLowerCase(Locale.ROOT).contains("voe.to")) {
                                                    startEpisodeWatchTimer();
                                                    openVOEPlayer(resolvedUrl);
                                                } else {
                                                    startEpisodeWatchTimer();
                                                    openPlayer(resolvedUrl);
                                                }
                                            });

                                        } catch (Exception e) {
                                            Log.e("AniWorld", "Redirect-Auflösung fehlgeschlagen", e);

                                            runOnUiThread(() -> {
                                                startEpisodeWatchTimer();
                                                openPlayer(hoster.url);
                                            });
                                        }
                                    });
                                }
                        );
                    }
                }
            });
        });
    }

    private String resolveRedirect(String url) {
        try {
            Connection.Response response = Jsoup.connect(url)
                    .userAgent("Mozilla/5.0")
                    .followRedirects(true)
                    .ignoreContentType(true)
                    .execute();
            Log.i("AniWorld", "Resolved Url: " + response.url().toString());

            return response.url().toString();
        } catch (IOException e) {
            return url;
        }
    }

    // ---------------------------------------------------------
    // VIDMOLY -> NATIVER MEDIA3-PLAYER
    // ---------------------------------------------------------

    private void openVidmolyPlayer(String embedUrl) {
        if (nativeResolveInProgress) {
            return;
        }

        nativeResolveInProgress = true;
        cancelPosterBatch();
        cancelEpisodeWatchTimer();
        addMessage("Lade Vidmoly-Stream …");

        io.execute(() -> {
            String streamUrl = null;
            String error = null;

            try {
                streamUrl = resolveVidmolyStream(embedUrl);
                if (streamUrl == null || streamUrl.isEmpty()) {
                    error = "In der Vidmoly-Seite wurde keine direkte Videoquelle gefunden.";
                }
            } catch (Exception e) {
                error = "Vidmoly konnte nicht aufgelöst werden: " + e.getMessage();
                Log.e("AniWorld", "Vidmoly-Auflösung fehlgeschlagen", e);
            }

            final String resolved = streamUrl;
            final String failure = error;

            runOnUiThread(() -> {
                nativeResolveInProgress = false;

                if (isFinishing() || isDestroyed()) {
                    return;
                }

                if (failure != null) {
                    addMessage(failure);
                    addMessage("Der Hoster hat möglicherweise seine Einbettung geändert oder liefert die Stream-Adresse erst per JavaScript nach.");
                    return;
                }

                try {
                    startNativePlayback(resolved, embedUrl);
                } catch (Exception e) {
                    Log.e("AniWorld", "Native Wiedergabe konnte nicht gestartet werden", e);
                    addMessage("Native Wiedergabe fehlgeschlagen: " + e.getMessage());
                }
            });
        });
    }

    private String resolveVidmolyStream(String embedUrl) throws Exception {
        String cookieHeader = CookieManager.getInstance().getCookie(embedUrl);

        org.jsoup.Connection connection = Jsoup.connect(embedUrl)
                .userAgent("Mozilla/5.0 (Linux; Android 10; Android TV) AppleWebKit/537.36 Chrome/120 Safari/537.36")
                .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                .header("Accept-Language", "de-DE,de;q=0.9,en;q=0.8")
                .referrer(BASE + "/")
                .timeout(20000)
                .followRedirects(true);

        if (cookieHeader != null && !cookieHeader.isEmpty()) {
            connection.header("Cookie", cookieHeader);
        }

        Document document = connection.get();
        String html = document.html();

        // Vidmoly verwendet je nach Player-Version unterschiedliche Schreibweisen.
        // Wir akzeptieren nur echte Medien-URLs, keine Poster-/Thumbnail-Bilder.
        String[] patterns = {
                "(?is)(?:file|src)\\s*[:=]\\s*['\"](https?:[^'\"]+?\\.(?:m3u8|mp4|mpd)(?:\\?[^'\"]*)?)['\"]",
                "(?is)['\"]file['\"]\\s*:\\s*['\"](https?:[^'\"]+?\\.(?:m3u8|mp4|mpd)(?:\\?[^'\"]*)?)['\"]",
                "(?is)(https?:\\/\\/[^'\"\\s<>]+?\\.(?:m3u8|mp4|mpd)(?:\\?[^'\"\\s<>]*)?)"
        };

        for (String expression : patterns) {
            Matcher matcher = Pattern.compile(expression).matcher(html);
            if (matcher.find()) {
                String candidate = matcher.group(1)
                        .replace("\\/", "/")
                        .replace("&amp;", "&")
                        .replace("\\u0026", "&")
                        .trim();

                if (candidate.startsWith("http://") || candidate.startsWith("https://")) {
                    return candidate;
                }
            }
        }

        // Zweiter Durchlauf: JSON-/JS-escaped URLs mit kodierten Slashes.
        Matcher escaped = Pattern.compile("(?is)(https?:\\\\/\\\\/[^'\"\\s<>]+?\\.(?:m3u8|mp4|mpd)(?:\\?[^'\"\\s<>]*)?)").matcher(html);
        if (escaped.find()) {
            String candidate = escaped.group(1).replace("\\/", "/").replace("&amp;", "&");
            if (candidate.startsWith("http://") || candidate.startsWith("https://")) {
                return candidate;
            }
        }

        return null;
    }

    // ---------------------------------------------------------
    // VOE -> NATIVER MEDIA3-PLAYER
    // ---------------------------------------------------------

    /*
     * VOE verwendet wechselnde Embed-Domains. Deshalb ist der
     * AniWorld-Hostername ("VOE") das zuverlässigste Erkennungsmerkmal.
     * Die bekannte Hauptdomain dient nur als zusätzlicher Fallback.
     */

    private void openVOEPlayer(String embedUrl) {
        if (nativeResolveInProgress) {
            return;
        }

        nativeResolveInProgress = true;
        cancelPosterBatch();
        cancelEpisodeWatchTimer();
        addMessage("Lade VOE-Stream …");

        io.execute(() -> {
            String streamUrl = null;
            String error = null;

            try {
                streamUrl = resolveVOEStream(embedUrl);
                if (streamUrl == null || streamUrl.isEmpty()) {
                    error = "In der VOE-Seite wurde keine direkte HLS- oder Videoquelle gefunden.";
                }
            } catch (Exception e) {
                error = "VOE konnte nicht aufgelöst werden: " + e.getMessage();
                Log.e("AniWorld", "VOE-Auflösung fehlgeschlagen", e);
            }

            final String resolved = streamUrl;
            final String failure = error;

            runOnUiThread(() -> {
                nativeResolveInProgress = false;

                if (isFinishing() || isDestroyed()) {
                    return;
                }

                if (failure != null) {
                    addMessage(failure);
                    addMessage("VOE kann seine Stream-Adresse geändert haben oder sie erst nach JavaScript-Ausführung bereitstellen.");
                    addAction("VOE in WebView öffnen", () -> openPlayer(embedUrl));
                    return;
                }

                try {
                    startNativePlayback(resolved, embedUrl);
                } catch (Exception e) {
                    Log.e("AniWorld", "Native VOE-Wiedergabe konnte nicht gestartet werden", e);
                    addMessage("Native VOE-Wiedergabe fehlgeschlagen: " + e.getMessage());
                    addAction("VOE in WebView öffnen", () -> openPlayer(embedUrl));
                }
            });
        });
    }

    private String documentTitle(String html) {
        return Jsoup.parse(html).title();
    }

    private String resolveVOEStream(String embedUrl) throws Exception {
        String currentUrl = resolveRedirect(embedUrl);
        String html = null;
        String finalVOEUrl = null;

        // JavaScript-Weiterleitungen von VOE manuell verfolgen
        for (int i = 0; i < 5; i++) {

            Log.i("AniWorld", "VOE lade: " + currentUrl);

            String cookieHeader = CookieManager.getInstance().getCookie(currentUrl);

            org.jsoup.Connection connection = Jsoup.connect(currentUrl)
                    .userAgent("Mozilla/5.0 (Linux; Android 10; Android TV) AppleWebKit/537.36 Chrome/120 Safari/537.36")
                    .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                    .header("Accept-Language", "de-DE,de;q=0.9,en;q=0.8")
                    .referrer(BASE + "/")
                    .timeout(20000)
                    .followRedirects(true);

            if (cookieHeader != null && !cookieHeader.isEmpty()) {
                connection.header("Cookie", cookieHeader);
            }

            Connection.Response response = connection.execute();

            finalVOEUrl = response.url().toString();
            html = response.body();

            Log.i("AniWorld", "VOE HTTP Status: " + response.statusCode());
            Log.i("AniWorld", "VOE Final URL: " + finalVOEUrl);
            Log.i("AniWorld", "VOE Titel: " + Jsoup.parse(html).title());

            // JavaScript-Weiterleitung erkennen
            Matcher redirectMatcher = Pattern.compile(
                    "window\\.location\\.href\\s*=\\s*['\"]([^'\"]+)['\"]"
            ).matcher(html);

            if (redirectMatcher.find()) {
                String redirectUrl = redirectMatcher.group(1);

                if (redirectUrl.startsWith("http://")
                        || redirectUrl.startsWith("https://")) {

                    Log.i("AniWorld", "VOE JavaScript-Redirect: " + redirectUrl);
                    currentUrl = redirectUrl;
                    continue;
                }
            }

            // Keine weitere Weiterleitung gefunden
            break;
        }

        if (html == null) {
            throw new Exception("VOE-Seite konnte nicht geladen werden");
        }

        Log.i("AniWorld", "VOE endgültige Seite: " + finalVOEUrl);

        /*
         * Ab hier bleibt die bisherige Stream-Erkennung erhalten.
         */

        /*
         * VOE-Konfiguration aus den application/json-Scripten lesen.
         * Die eigentliche Stream-Adresse steckt in einem verschlüsselten
         * JSON-Array und darf nicht durch eine globale URL-Suche ersetzt werden.
         */
        Document voeDocument = Jsoup.parse(html);

        Elements configScripts = voeDocument.select(
                "script[type=application/json]"
        );

        Log.i("AniWorld", "VOE JSON-Konfigurationen gefunden: "
                + configScripts.size());

        for (Element script : configScripts) {
            String scriptContent = script.data();

            if (scriptContent == null || scriptContent.trim().isEmpty()) {
                scriptContent = script.html();
            }

            scriptContent = scriptContent.trim();

            try {
                // VOE liefert normalerweise ein JSON-Array,
                // dessen erstes Element der verschlüsselte String ist.
                org.json.JSONArray array =
                        new org.json.JSONArray(scriptContent);

                if (array.length() == 0 || !(array.opt(0) instanceof String)) {
                    continue;
                }

                String encoded = array.optString(0);

                JSONObject config = decodeVOEConfig(encoded);

                Log.i("AniWorld", "VOE-Konfiguration erfolgreich entschlüsselt");

                String streamUrl = extractVOEStreamFromConfig(
                        config,
                        finalVOEUrl
                );

                if (streamUrl != null && isSupportedNativeStream(streamUrl)) {
                    Log.i("AniWorld", "VOE-Stream aus Konfiguration gefunden: "
                            + streamUrl);
                    return streamUrl;
                }

                Log.w("AniWorld",
                        "VOE-Konfiguration enthält keine unterstützte Stream-Adresse");

            } catch (Exception e) {
                Log.w("AniWorld",
                        "VOE-Konfiguration konnte nicht entschlüsselt werden", e);
            }
        }

        Log.e("AniWorld",
                "Kein gültiger Stream in der VOE-Konfiguration gefunden.");

        return null;
    }

    /** Entschlüsselt exakt die von loader.a40897e.js verwendete Konfiguration. */
    private JSONObject decodeVOEConfig(String encoded) throws Exception {
        if (encoded == null || encoded.isEmpty()) {
            throw new IllegalArgumentException("Leere VOE-Konfiguration");
        }

        // Schritt 1: ROT13
        StringBuilder rot13 = new StringBuilder(encoded.length());
        for (int i = 0; i < encoded.length(); i++) {
            char c = encoded.charAt(i);
            if (c >= 'A' && c <= 'Z') {
                c = (char) ((c - 'A' + 13) % 26 + 'A');
            } else if (c >= 'a' && c <= 'z') {
                c = (char) ((c - 'a' + 13) % 26 + 'a');
            }
            rot13.append(c);
        }

        // Schritt 2: die sieben Trenner durch '_' ersetzen; Schritt 3: '_' entfernen.
        String cleaned = rot13.toString()
                .replace("@$", "_")
                .replace("^^", "_")
                .replace("~@", "_")
                .replace("%?", "_")
                .replace("*~", "_")
                .replace("!!", "_")
                .replace("#&", "_")
                .replace("_", "");

        // Schritt 4: erstes atob(). atob liefert Byte-Zeichen, daher ISO-8859-1.
        byte[] firstBytes = android.util.Base64.decode(
                cleaned, android.util.Base64.DEFAULT);
        String first = new String(firstBytes, java.nio.charset.StandardCharsets.ISO_8859_1);

        // Schritt 5: jedes Zeichen um 3 reduzieren.
        StringBuilder shifted = new StringBuilder(first.length());
        for (int i = 0; i < first.length(); i++) {
            shifted.append((char) (first.charAt(i) - 3));
        }

        // Schritt 6: umdrehen; Schritt 7: zweites atob(); Schritt 8: JSON parsen.
        String reversed = shifted.reverse().toString();
        byte[] jsonBytes = android.util.Base64.decode(
                reversed, android.util.Base64.DEFAULT);
        String json = new String(jsonBytes, java.nio.charset.StandardCharsets.UTF_8);

        return new JSONObject(json);
    }

    private String extractVOEStreamFromConfig(JSONObject config, String pageUrl) {
        if (config == null) return null;

        // 1. Bevorzugt den HLS-Stream verwenden
        String source = normalizeVOEStreamUrl(
                config.optString("source", ""),
                pageUrl
        );

        if (isSupportedNativeStream(source)) {
            return source;
        }

        // 2. Fallback: MP4-Streams durchgehen
        org.json.JSONArray fallback = config.optJSONArray("fallback");

        if (fallback != null) {
            // Höhere Qualität zuerst
            for (int i = 0; i < fallback.length(); i++) {
                JSONObject item = fallback.optJSONObject(i);
                if (item == null) continue;

                String file = normalizeVOEStreamUrl(
                        item.optString("file", ""),
                        pageUrl
                );

                if (isSupportedNativeStream(file)) {
                    Log.i("AniWorld", "VOE Fallback gefunden: "
                            + item.optString("label", "unbekannt")
                            + " - " + file);

                    return file;
                }
            }
        }

        // 3. Zusätzliche mögliche Felder
        String primary = normalizeVOEStreamUrl(
                config.optString("file", ""),
                pageUrl
        );

        if (isSupportedNativeStream(primary)) {
            return primary;
        }

        return null;
    }

    private String normalizeVOEStreamUrl(String value, String embedUrl) {
        if (value == null) {
            return "";
        }

        String candidate = value.trim()
                .replace("\\/", "/")
                .replace("\\u0026", "&")
                .replace("\\x26", "&")
                .replace("&amp;", "&")
                .replace("\\u002F", "/")
                .replace("\\x2F", "/");

        if (candidate.startsWith("//")) {
            candidate = "https:" + candidate;
        }

        try {
            if (!candidate.startsWith("http://")
                    && !candidate.startsWith("https://")) {
                candidate = new URL(new URL(embedUrl), candidate).toString();
            }
        } catch (Exception ignored) {
            return "";
        }

        return candidate;
    }

    private boolean isSupportedNativeStream(String url) {
        if (url == null || url.isEmpty()) {
            return false;
        }

        String lower = url.toLowerCase(Locale.ROOT);
        return (lower.startsWith("http://") || lower.startsWith("https://"))
                && (lower.contains(".m3u8")
                || lower.contains(".mp4")
                || lower.contains(".mpd"));
    }

    @UnstableApi
    private void startNativePlayback(String streamUrl, String referer) {
        cancelEpisodeWatchTimer();

        if (nativePlayer != null) {
            nativePlayer.release();
            nativePlayer = null;
        }

        player.stopLoading();
        player.setVisibility(View.GONE);

        DefaultHttpDataSource.Factory dataSourceFactory =
                new DefaultHttpDataSource.Factory()
                        .setUserAgent("Mozilla/5.0 (Linux; Android 10; Android TV) AppleWebKit/537.36 Chrome/120 Safari/537.36")
                        .setConnectTimeoutMs(15000)
                        .setReadTimeoutMs(20000)
                        .setAllowCrossProtocolRedirects(true);

        Map<String, String> requestHeaders = new HashMap<>();
        requestHeaders.put("Referer", referer);
        try {
            URL embed = new URL(referer);
            requestHeaders.put("Origin", embed.getProtocol() + "://" + embed.getHost());
        } catch (Exception ignored) {
        }
        // Cookies nur für die tatsächliche Stream-Domain übernehmen.
        String cookies = CookieManager.getInstance().getCookie(streamUrl);
        if (cookies != null && !cookies.isEmpty()) {
            requestHeaders.put("Cookie", cookies);
        }
        dataSourceFactory.setDefaultRequestProperties(requestHeaders);

        MediaItem.Builder mediaItemBuilder = new MediaItem.Builder().setUri(streamUrl);
        String lower = streamUrl.toLowerCase(Locale.ROOT);
        if (lower.contains(".m3u8")) {
            mediaItemBuilder.setMimeType(MimeTypes.APPLICATION_M3U8);
        } else if (lower.contains(".mpd")) {
            mediaItemBuilder.setMimeType(MimeTypes.APPLICATION_MPD);
        }
        MediaItem mediaItem = mediaItemBuilder.build();

        nativePlayer = new ExoPlayer.Builder(this).build();
        nativePlayerView.setPlayer(nativePlayer);
        nativePlayerView.setVisibility(View.VISIBLE);
        nativePlayerView.bringToFront();
        mainContent.setVisibility(View.GONE);

        nativePlayer.addListener(new androidx.media3.common.Player.Listener() {
            private boolean watchTimerStarted = false;

            @Override
            public void onIsPlayingChanged(boolean isPlaying) {
                if (isPlaying && !watchTimerStarted) {
                    watchTimerStarted = true;
                    startEpisodeWatchTimer();
                }
            }

            @Override
            public void onPlayerError(PlaybackException error) {
                cancelEpisodeWatchTimer();
                Log.e("AniWorld", "Media3-Wiedergabefehler: " + error.getErrorCodeName(), error);
                runOnUiThread(() -> {
                    if (nativePlayerView.getVisibility() == View.VISIBLE) {
                        Toast.makeText(MainActivity.this,
                                "Stream kann nicht abgespielt werden: " + error.getErrorCodeName(),
                                Toast.LENGTH_LONG).show();
                    }
                });
            }
        });

        MediaSource mediaSource = new DefaultMediaSourceFactory(dataSourceFactory)
                .createMediaSource(mediaItem);
        nativePlayer.setMediaSource(mediaSource);
        nativePlayer.prepare();
        nativePlayer.setPlayWhenReady(true);
        nativePlayerView.requestFocus();
    }

    private void releaseNativePlayer() {
        if (nativePlayer != null) {
            nativePlayerView.setPlayer(null);
            nativePlayer.release();
            nativePlayer = null;
        }
        nativePlayerView.setVisibility(View.GONE);
    }


    private int getHosterPriority(String title, String url) {
        String value = ((title == null ? "" : title) + " "
                + (url == null ? "" : url))
                .toLowerCase(Locale.ROOT);

        if (value.contains("voe")
                || value.contains("arianathankspecial")) {
            return 0;
        }

        if (value.contains("vidmoly")) {
            return 1;
        }

        if (value.contains("doodstream")
                || value.contains("dood.")) {
            return 2;
        }

        if (value.contains("filemoon")) {
            return 3;
        }

        return 99;
    }

    private void filterAndSortHosters(List<StreamHoster> hosters) {
        // Nur die gewünschten vier Hoster behalten.
        java.util.Iterator<StreamHoster> iterator = hosters.iterator();

        while (iterator.hasNext()) {
            StreamHoster hoster = iterator.next();

            if (getHosterPriority(hoster.title, hoster.url) >= 99) {
                iterator.remove();
            }
        }

        // Erst nach Sprache, anschließend nach Hoster sortieren.
        hosters.sort((a, b) -> {
            int languageCompare = Integer.compare(
                    a.languagePriority,
                    b.languagePriority
            );

            if (languageCompare != 0) {
                return languageCompare;
            }

            return Integer.compare(
                    getHosterPriority(a.title, a.url),
                    getHosterPriority(b.title, b.url)
            );
        });
    }


    // ---------------------------------------------------------
    // WEBVIEW FULLSCREEN
    // ---------------------------------------------------------

    private class PlayerWebChromeClient extends WebChromeClient {

        @Override
        public void onShowCustomView(
                View view,
                CustomViewCallback callback
        ) {

            if (customView != null) {
                callback.onCustomViewHidden();
                return;
            }

            customView = view;
            customViewCallback = callback;

            FrameLayout content =
                    findViewById(android.R.id.content);

            content.addView(
                    customView,
                    new FrameLayout.LayoutParams(
                            FrameLayout.LayoutParams.MATCH_PARENT,
                            FrameLayout.LayoutParams.MATCH_PARENT
                    )
            );

            player.setVisibility(View.GONE);

            hideSystemBars();
        }

        @Override
        public void onHideCustomView() {

            if (customView == null) {
                return;
            }

            FrameLayout content =
                    findViewById(android.R.id.content);

            content.removeView(customView);

            customView = null;

            player.setVisibility(View.VISIBLE);

            WebChromeClient.CustomViewCallback callback =
                    customViewCallback;

            customViewCallback = null;

            if (callback != null) {
                callback.onCustomViewHidden();
            }

            hideSystemBars();
        }

        @Override
        public boolean onCreateWindow(
                WebView view,
                boolean isDialog,
                boolean isUserGesture,
                Message resultMsg
        ) {

            logDebug("Pop-up blockiert");

            return false;
        }
    }

    private void dispatchEnterKey() {

        long downTime = SystemClock.uptimeMillis();

        KeyEvent downEvent = new KeyEvent(
                downTime,
                downTime,
                KeyEvent.ACTION_DOWN,
                KeyEvent.KEYCODE_ENTER,
                0
        );

        player.dispatchKeyEvent(downEvent);

        long upTime = SystemClock.uptimeMillis();

        KeyEvent upEvent = new KeyEvent(
                downTime,
                upTime,
                KeyEvent.ACTION_UP,
                KeyEvent.KEYCODE_ENTER,
                0
        );

        player.dispatchKeyEvent(upEvent);
    }

    // ---------------------------------------------------------
    // PLAYER ÖFFNEN / SCHLIESSEN
    // ---------------------------------------------------------

    private void openPlayer(String url) {

        cancelPosterBatch();
        releaseNativePlayer();

        mainContent.setVisibility(View.GONE);

        player.setVisibility(View.VISIBLE);

        player.bringToFront();

        player.onResume();

        player.loadUrl(url);
    }

    private void showCatalog() {

        cancelEpisodeWatchTimer();

        if (playerStartSequence != null) {

            watchHandler.removeCallbacks(playerStartSequence);

            playerStartSequence = null;
        }

        releaseNativePlayer();

        if (customView != null
                && playerChromeClient != null) {

            playerChromeClient.onHideCustomView();
        }

        player.evaluateJavascript(
                "(function() {" +
                        "document.querySelectorAll('video, audio').forEach(function(media) {" +
                        "try {" +
                        "media.pause();" +
                        "media.removeAttribute('src');" +
                        "media.querySelectorAll('source').forEach(function(source) {" +
                        "source.removeAttribute('src');" +
                        "});" +
                        "media.load();" +
                        "} catch(e) {}" +
                        "});" +
                        "})();",
                null
        );

        player.stopLoading();

        player.setVisibility(View.GONE);

        mainContent.setVisibility(View.VISIBLE);
    }

    // ---------------------------------------------------------
    // MELDUNGEN UND AKTIONEN
    // ---------------------------------------------------------

    private void addMessage(String message) {

        TextView t = new TextView(this);

        t.setText(message);
        t.setTextColor(0xFFAAAAAA);
        t.setTextSize(16);

        t.setPadding(
                dp(8),
                dp(20),
                dp(8),
                dp(20)
        );

        catalog.addView(t);
    }

    private void addAction(
            String label,
            Runnable action
    ) {

        Button b = new Button(this);

        b.setFocusable(true);

        b.setOnFocusChangeListener((v, hasFocus) -> {

            if (hasFocus) {

                v.setBackground(
                        round(
                                ORANGE,
                                ORANGE,
                                8
                        )
                );

            } else {

                v.setBackground(
                        round(
                                0xFF252525,
                                0xFF444444,
                                8
                        )
                );
            }
        });

        b.setText(label);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(16);

        b.setGravity(
                Gravity.START | Gravity.CENTER_VERTICAL
        );

        b.setPadding(
                dp(18),
                0,
                dp(18),
                0
        );

        b.setBackground(
                round(
                        0xFF252525,
                        0xFF444444,
                        10
                )
        );

        b.setFocusable(true);

        b.setOnClickListener(v -> action.run());

        LinearLayout.LayoutParams lp =
                new LinearLayout.LayoutParams(
                        -1,
                        dp(54)
                );

        lp.setMargins(
                0,
                0,
                0,
                dp(9)
        );

        catalog.addView(b, lp);
    }

    // ---------------------------------------------------------
    // APP BEENDEN
    // ---------------------------------------------------------

    @Override
    protected void onDestroy() {

        cancelEpisodeWatchTimer();

        io.shutdownNow();
        updateExecutor.shutdownNow();
        cancelPosterBatch();
        imageExecutor.shutdownNow();

        if (playerStartSequence != null) {

            watchHandler.removeCallbacks(playerStartSequence);

            playerStartSequence = null;
        }

        releaseNativePlayer();
        player.destroy();

        super.onDestroy();
    }
}