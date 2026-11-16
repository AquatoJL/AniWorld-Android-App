package com.example.aniworld;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.content.Context;
import android.content.SharedPreferences;
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
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

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
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.Collections;
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
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

public class MainActivity extends AppCompatActivity {

    private static final String BASE = "https://aniworld.to";

    private static final int ORANGE = 0xFFF47521;
    private static final int BACKGROUND = 0xFF101010;
    private static final int CARD_BACKGROUND = 0xFF1C1C1C;
    private static final int SEARCH_BACKGROUND = 0xFF242424;

    private final ExecutorService io =
            Executors.newSingleThreadExecutor();

    private final ThreadPoolExecutor imageExecutor =
            (ThreadPoolExecutor) Executors.newFixedThreadPool(3);

    private volatile PosterBatch activePosterBatch;

    private final LruCache<String, Bitmap> posterCache =
            new LruCache<String, Bitmap>(
                    (int) (Runtime.getRuntime().maxMemory() / 8)
            ) {
                @Override
                protected int sizeOf(String key, Bitmap bitmap) {
                    return bitmap.getByteCount();
                }
            };

    // Verhindert parallele Downloads derselben Poster-URL.
    private final ConcurrentHashMap<String, Object> posterLocks =
            new ConcurrentHashMap<>();

    private LinearLayout catalog;
    private LinearLayout navigation;
    private TextView sectionTitle;
    private EditText search;
    private WebView player;
    private View customView;
    private WebChromeClient.CustomViewCallback customViewCallback;
    private PlayerWebChromeClient playerChromeClient;
    private ScrollView catalogScroll;

    private final List<Show> currentShows = new ArrayList<>();

    private String currentUrl = BASE + "/animes-alphabet";
    private String currentTitle = "Entdecken";

    // 0 = Katalog, 1 = Staffeln, 2 = Episoden, 3 = Hoster
    private int level = 0;

    private Show selectedAnime;
    private Show selectedSeason;

    private String currentEpisodeId = null;
    private boolean currentEpisodeMarked = false;

    private final Handler watchHandler = new Handler(Looper.getMainLooper());

    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private Runnable watchEpisodeRunnable;
    private Runnable playerStartSequence;

    private LinearLayout mainContent;

    private static class Show {
        String title;
        String url;
        String posterUrl;

        Show(String title, String url) {
            this(title, url, "");
        }

        Show(String title, String url, String posterUrl) {
            this.title = title;
            this.url = url;
            this.posterUrl = posterUrl;
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
    public void onCreate(Bundle state) {
        super.onCreate(state);

        setContentView(R.layout.activity_main);

        mainContent = findViewById(R.id.mainContent);

        hideSystemBars();

        catalog = findViewById(R.id.catalog);
        navigation = findViewById(R.id.navigation);
        sectionTitle = findViewById(R.id.sectionTitle);
        search = findViewById(R.id.search);
        player = findViewById(R.id.playerWeb);
        catalogScroll = findViewById(R.id.catalogScroll);

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

                        if (player.getVisibility() == View.VISIBLE) {
                            showCatalog();
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

                        setEnabled(false);
                        getOnBackPressedDispatcher().onBackPressed();
                    }
                }
        );

        WebSettings ws = player.getSettings();

        Log.i(
                "AniWorld",
                "WebView User-Agent: " + ws.getUserAgentString()
        );

        if (WebView.getCurrentWebViewPackage() != null) {
            Log.i(
                    "AniWorld",
                    "WebView Version: "
                            + WebView.getCurrentWebViewPackage().versionName
            );
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

                    Log.d(
                            "AniWorld",
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

                    Log.d("AniWorld", "Sende ersten Enter-Druck");

                    dispatchEnterKey();

                    watchHandler.postDelayed(() -> {
                        Log.d("AniWorld", "Sende zweiten Enter-Druck");
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

        loadCatalog(BASE + "/animes-alphabet", "Alle Anime");
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

        Log.d(
                "AniWorld",
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

                Log.i(
                        "AniWorld",
                        "lastseen Antwort HTTP "
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
                {"Neue Folgen", BASE + "/neue-episoden"},
                {"Beliebt", BASE + "/beliebte-animes"},
                {"Alle Anime", BASE + "/animes-alphabet"},
                {"Benachrichtigungen", BASE + "/account/notifications"}
        };

        for (String[] item : items) {

            Button b = new Button(this);

            b.setText(item[0]);
            b.setAllCaps(false);
            b.setTextColor(Color.WHITE);
            b.setTextSize(14);
            b.setTypeface(null, Typeface.BOLD);
            b.setGravity(Gravity.CENTER);

            b.setBackground(
                    round(0xFF252525, 0xFF444444, 24)
            );

            b.setFocusable(true);

            LinearLayout.LayoutParams lp =
                    new LinearLayout.LayoutParams(
                            -2,
                            dp(42)
                    );

            lp.setMargins(0, 0, dp(10), 0);

            navigation.addView(b, lp);

            b.setOnClickListener(v -> {
                level = 0;
                loadCatalog(item[1], item[0]);
            });

            b.setOnFocusChangeListener((v, hasFocus) -> {

                b.setBackground(
                        round(
                                hasFocus ? ORANGE : 0xFF252525,
                                hasFocus ? ORANGE : 0xFF444444,
                                24
                        )
                );
            });
        }

        Button accountButton = new Button(this);

        accountButton.setText("Account");
        accountButton.setAllCaps(false);
        accountButton.setTextColor(Color.WHITE);
        accountButton.setTextSize(14);
        accountButton.setTypeface(null, Typeface.BOLD);

        accountButton.setBackground(
                round(0xFF252525, 0xFF444444, 24)
        );

        accountButton.setFocusable(true);

        LinearLayout.LayoutParams accountLp =
                new LinearLayout.LayoutParams(
                        -2,
                        dp(42)
                );

        accountLp.setMargins(0, 0, dp(10), 0);

        navigation.addView(accountButton, accountLp);

        accountButton.setOnFocusChangeListener((v, hasFocus) -> {

            accountButton.setBackground(
                    round(
                            hasFocus ? ORANGE : 0xFF252525,
                            hasFocus ? ORANGE : 0xFF444444,
                            24
                    )
            );
        });

        accountButton.setOnClickListener(v ->
                openPlayer(BASE + "/account")
        );
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

            Log.d(
                    "AniWorld",
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

        // Bei URLs der Form /anime/slug/stream/episode-...
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
                Log.d(
                        "AniWorld",
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

        Log.i(
                "AniWorld",
                "Poster-Verarbeitung wird abgebrochen: "
                        + batch.finished.get() + "/" + batch.total
        );

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

                boolean diskHit = false;
                boolean downloaded = false;
                boolean memoryHit = false;

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
                        memoryHit = true;
                        batch.memoryHits.incrementAndGet();
                    }

                    // 4. Festplatten-Cache prüfen.
                    if (bitmap == null) {

                        File posterFile = getPosterFile(imageUrl);

                        if (posterFile.exists() && posterFile.length() > 0) {

                            bitmap = BitmapFactory.decodeFile(
                                    posterFile.getAbsolutePath()
                            );

                            if (bitmap != null) {
                                diskHit = true;
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

                            bitmap = BitmapFactory.decodeFile(
                                    posterFile.getAbsolutePath()
                            );

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

            Log.i(
                    "AniWorld",
                    "Poster-Fortschritt: "
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

            Log.i(
                    "AniWorld",
                    "Poster-Verarbeitung abgeschlossen: "
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

                Log.i(
                        "AniWorld",
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

        if (shows.isEmpty()) {
            addMessage("Keine Anime gefunden.");
            return;
        }
        Log.i(
                "AniWorld",
                "Alle Shows: "
                        + shows
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
        row.setClipChildren(false);
        row.setClipToPadding(false);

        PosterBatch posterBatch = new PosterBatch(shows.size());
        activePosterBatch = posterBatch;

        if (shows.isEmpty()) {
            Log.i("AniWorld", "Keine Anime für Poster vorhanden.");
            return;
        }

        Log.i(
                "AniWorld",
                "Poster-Verarbeitung gestartet: "
                        + shows.size()
                        + " Anime werden geprüft"
        );

        for (Show show : shows) {

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

            poster.setScaleType(
                    ImageView.ScaleType.CENTER_CROP
            );

            poster.setBackgroundColor(0xFF252525);
            poster.setFocusable(false);

            poster.setScaleType(ImageView.ScaleType.CENTER_CROP);
            poster.setVisibility(View.VISIBLE);

            posterFrame.addView(
                    poster,
                    new FrameLayout.LayoutParams(
                            FrameLayout.LayoutParams.MATCH_PARENT,
                            FrameLayout.LayoutParams.MATCH_PARENT
                    )
            );

            // Platzhalter, falls AniWorld kein Poster liefert.
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

            loadPoster(
                    poster,
                    placeholder,
                    show,
                    posterBatch
            );

            TextView title = new TextView(this);

            title.setText(show.title);
            title.setTextColor(Color.WHITE);
            title.setTextSize(14);
            title.setTypeface(null, Typeface.BOLD);
            title.setGravity(
                    Gravity.TOP | Gravity.START
            );

            title.setPadding(
                    dp(5),
                    dp(10),
                    dp(5),
                    dp(8)
            );

            title.setMaxLines(2);

            title.setEllipsize(
                    android.text.TextUtils.TruncateAt.END
            );

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

                    card.setScaleX(1.04f);
                    card.setScaleY(1.04f);

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

            row.addView(card, cardParams);
        }

        horizontalScroll.addView(row);

        catalog.addView(horizontalScroll);
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
        level = 2;
        sectionTitle.setText(season.title);
        catalog.removeAllViews();
        addMessage("Lade Episoden …");

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

                    episodes.add(
                            new Show(title, fullUrl)
                    );
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

                        episodes.add(
                                new Show(title, fullUrl)
                        );
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

                        addAction(
                                episode.title,
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

        level = 3;

        catalog.removeAllViews();

        sectionTitle.setText(episode.title);

        addMessage("Suche Video-Hoster …");

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

                hosters.sort((a, b) ->
                        Integer.compare(
                                a.languagePriority,
                                b.languagePriority
                        )
                );

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
                                    startEpisodeWatchTimer();
                                    openPlayer(hoster.url);
                                }
                        );
                    }
                }
            });
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

            Log.d("AniWorld", "Pop-up blockiert");

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
        cancelPosterBatch();
        imageExecutor.shutdownNow();

        if (playerStartSequence != null) {

            watchHandler.removeCallbacks(playerStartSequence);

            playerStartSequence = null;
        }

        player.destroy();

        super.onDestroy();
    }
}
