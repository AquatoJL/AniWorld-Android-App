package com.example.aniworld;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.content.Context;
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
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import android.util.Log;
import android.net.http.SslError;
import android.webkit.SslErrorHandler;
import android.webkit.WebResourceRequest;
import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import java.util.HashMap;
import java.util.Map;

public class MainActivity extends AppCompatActivity {
    private static final String BASE = "https://aniworld.to";
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private LinearLayout catalog, navigation;
    private TextView sectionTitle;
    private EditText search;
    private WebView player;
    private ScrollView catalogScroll;
    private final List<Show> currentShows = new ArrayList<>();
    private String currentUrl = BASE + "/animes";
    private String currentTitle = "Entdecken";
    // 0 = Katalog, 1 = Staffeln, 2 = Episoden, 3 = Hoster
    private int level = 0;
    private Show selectedAnime;
    private Show selectedSeason;

    private LinearLayout mainContent;

    private static class Show {
        String title, url;
        Show(String t, String u) { title=t; url=u; }
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_main);
        mainContent = findViewById(R.id.mainContent);
        hideSystemBars();
        catalog = findViewById(R.id.catalog); navigation = findViewById(R.id.navigation);
        sectionTitle = findViewById(R.id.sectionTitle); search = findViewById(R.id.search);
        player = findViewById(R.id.playerWeb); catalogScroll = findViewById(R.id.catalogScroll);
        getOnBackPressedDispatcher().addCallback(this,
                new OnBackPressedCallback(true) {
                    @Override
                    public void handleOnBackPressed() {

                        // Player schließen und zur Hoster-Auswahl
                        if (player.getVisibility() == View.VISIBLE) {
                            showCatalog();
                            return;
                        }

                        // Hoster-Auswahl -> Episodenliste
                        if (level == 3 && selectedSeason != null) {
                            loadEpisodes(selectedSeason);
                            return;
                        }

                        // Episodenliste -> Staffel-Auswahl
                        if (level == 2 && selectedAnime != null) {
                            openSeries(selectedAnime);
                            return;
                        }

                        // Staffel-Auswahl -> Anime-Katalog
                        if (level == 1) {
                            level = 0;
                            loadCatalog(currentUrl, currentTitle);
                            return;
                        }

                        // Auf der Startseite: App schließen
                        setEnabled(false);
                        getOnBackPressedDispatcher().onBackPressed();
                    }
                });
        WebSettings ws = player.getSettings();
        android.util.Log.i(
                "AniWorld",
                "WebView User-Agent: " + ws.getUserAgentString()
        );

        android.util.Log.i(
                "AniWorld",
                "WebView Version: "
                        + WebView.getCurrentWebViewPackage().versionName
        );
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setLoadsImagesAutomatically(true);
        ws.setJavaScriptCanOpenWindowsAutomatically(true);
        ws.setSupportMultipleWindows(true);
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(player, true);
        player.setWebChromeClient(new WebChromeClient());
        player.setWebViewClient(new WebViewClient() {

            @Override
            public boolean shouldOverrideUrlLoading(
                    WebView view,
                    WebResourceRequest request
            ) {
                Log.d("AniWorld", "URL-Aufruf: " + request.getUrl());
                return false;
            }

            @Override
            public void onReceivedError(
                    WebView view,
                    WebResourceRequest request,
                    android.webkit.WebResourceError error
            ) {
                if (request.isForMainFrame()) {
                    Log.e("AniWorld",
                            "WebView-Netzwerkfehler: "
                                    + error.getErrorCode()
                                    + " - " + error.getDescription()
                                    + " URL: " + request.getUrl());
                }
            }

            @Override
            public void onReceivedSslError(
                    WebView view,
                    SslErrorHandler handler,
                    SslError error
            ) {
                Log.e("AniWorld",
                        "SSL-Fehler: " + error.toString()
                                + " URL: " + error.getUrl());

                // SSL-Fehler nicht ignorieren
                handler.cancel();
            }

            @Override
            public void onReceivedHttpError(
                    WebView view,
                    WebResourceRequest request,
                    android.webkit.WebResourceResponse response
            ) {
                if (request.isForMainFrame()) {
                    Log.e("AniWorld",
                            "HTTP-Fehler: " + response.getStatusCode()
                                    + " URL: " + request.getUrl());
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);

                // Cookies dauerhaft speichern
                CookieManager.getInstance().flush();

                // Versuch, direkt eingebundene Videos automatisch zu starten
                view.evaluateJavascript(
                        "(function() {" +
                                "  document.querySelectorAll('video').forEach(function(v) {" +
                                "    v.autoplay = true;" +
                                "    var p = v.play();" +
                                "    if (p && p.catch) p.catch(function() {});" +
                                "  });" +
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
            if (action == EditorInfo.IME_ACTION_SEARCH || (event != null && event.getKeyCode()==KeyEvent.KEYCODE_ENTER)) {
                String q = search.getText().toString().trim(); if (!q.isEmpty()) search(q); return true;
            } return false;
        });
        loadCatalog(BASE + "/animes", "Alle Anime");
    }

    private Map<String, String> getCookiesFor(String url) {
        Map<String, String> cookies = new HashMap<>();

        String cookieString = CookieManager.getInstance().getCookie(url);

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

    private void hideSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        WindowInsetsControllerCompat controller =
                WindowCompat.getInsetsController(
                        getWindow(),
                        getWindow().getDecorView()
                );

        controller.hide(WindowInsetsCompat.Type.systemBars());

        controller.setSystemBarsBehavior(
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        );
    }

    private void buildNavigation() {
        String[][] items = {{"Start", BASE + "/"}, {"Neue Folgen", BASE + "/neue-episoden"}, {"Beliebt", BASE + "/beliebte-animes"}, {"Alle Anime", BASE + "/animes"}, {"Benachrichtigungen", BASE + "/account/notifications"}};
        for (String[] item : items) {
            Button b = new Button(this); b.setText(item[0]); b.setAllCaps(false); b.setTextColor(Color.WHITE); b.setTextSize(14);
            b.setBackground(round(0xFF1D2940, 0xFF394967, 8)); b.setFocusable(true);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, dp(42)); lp.setMargins(0,0,dp(10),0); navigation.addView(b, lp);
            b.setOnClickListener(v -> { level=0; loadCatalog(item[1], item[0]); });
            b.setOnFocusChangeListener((v, hasFocus) -> {
                if (hasFocus) {
                    v.setBackground(round(
                            0xFF493A75,
                            0xFF9B7BFF,
                            8
                    ));
                } else {
                    v.setBackground(round(
                            0xFF1D2940,
                            0xFF394967,
                            8
                    ));
                }
            });

        }
        Button accountButton = new Button(this);
        accountButton.setText("Account");
        accountButton.setAllCaps(false);
        accountButton.setTextColor(Color.WHITE);
        accountButton.setTextSize(14);
        accountButton.setBackground(round(0xFF493A75, 0xFF9B7BFF, 8));
        accountButton.setFocusable(true);

        LinearLayout.LayoutParams accountLp =
                new LinearLayout.LayoutParams(-2, dp(42));
        accountLp.setMargins(0, 0, dp(10), 0);

        navigation.addView(accountButton, accountLp);

        accountButton.setOnClickListener(v ->
                openPlayer(BASE + "/account"));
    }

    private GradientDrawable round(int color, int stroke, int radius) {
        GradientDrawable d = new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius)); d.setStroke(dp(1), stroke); return d;
    }
    private int dp(float v) { return (int)(v * getResources().getDisplayMetrics().density + .5f); }

    private void loadCatalog(String url, String title) {
        currentUrl=url; currentTitle=title; sectionTitle.setText(title); showCatalog();
        catalog.removeAllViews(); addMessage("Lade Inhalte …");
        io.execute(() -> {
            List<Show> result = new ArrayList<>(); String error=null;
            try {
                Document doc = Jsoup.connect(url)
                        .cookies(getCookiesFor(url))
                        .userAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")
                        .header("Accept-Language", "de-DE,de;q=0.9,en;q=0.8")
                        .referrer(BASE + "/")
                        .timeout(20000)
                        .get();

                // Gleiche robuste Erkennung wie im funktionierenden Python-Client:
                // Neue-Folgen-, Beliebt- und Alle-Anime-Seiten haben teils
                // unterschiedliche Wrapper und Linkpfade.
                Elements links = doc.select("a[href*='/anime/']");
                for (Element a : links) {
                    String href = a.attr("href").trim();
                    String name = a.text().trim();
                    if (name.isEmpty()) {
                        Element img = a.selectFirst("img[alt]");
                        if (img != null) name = img.attr("alt").trim();
                    }
                    if (!href.startsWith("/anime/") || name.isEmpty()) continue;
                    String lowerName = name.toLowerCase(java.util.Locale.ROOT);
                    if (lowerName.equals("mehr") || lowerName.equals("ansehen") || lowerName.equals("anime")) continue;
                    String absoluteUrl = a.absUrl("href");
                    if (absoluteUrl.isEmpty()) absoluteUrl = new java.net.URL(new java.net.URL(BASE + "/"), href).toString();
                    if (!containsUrl(result, absoluteUrl)) result.add(new Show(name, absoluteUrl));
                    if (result.size() >= 100) break;
                }
                if (result.isEmpty()) error="Auf der Seite wurden keine Serien gefunden.";
            } catch(Exception e) { error="AniWorld konnte nicht geladen werden: "+e.getMessage(); }
            final String err=error; final List<Show> data=result;
            runOnUiThread(() -> {
                catalog.removeAllViews();
                currentShows.clear();
                currentShows.addAll(data);
                if(err!=null) addMessage(err);
                else renderShows(data); });
        });
    }

    private void search(String query) {
        String searchQuery = normalizeSearch(query);

        if (searchQuery.isEmpty()) {
            loadCatalog(BASE + "/animes", "Alle Anime");
            return;
        }

        level = 0;
        currentUrl = BASE + "/animes";
        currentTitle = "Suche: " + query;
        sectionTitle.setText(currentTitle);

        showCatalog();
        catalog.removeAllViews();
        addMessage("Suche Anime …");

        io.execute(() -> {
            List<Show> results = new ArrayList<>();
            String error = null;

            try {
                Document doc = Jsoup.connect(BASE + "/animes")
                        .cookies(getCookiesFor(BASE + "/animes"))
                        .userAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")
                        .header("Accept-Language", "de-DE,de;q=0.9,en;q=0.8")
                        .referrer(BASE + "/")
                        .timeout(20000)
                        .get();

                Elements links = doc.select("a[href*='/anime/']");

                for (Element a : links) {
                    String href = a.attr("href").trim();
                    String name = a.text().trim();

                    if (name.isEmpty()) {
                        Element img = a.selectFirst("img[alt]");
                        if (img != null) {
                            name = img.attr("alt").trim();
                        }
                    }

                    if (!href.startsWith("/anime/") || name.isEmpty()) {
                        continue;
                    }

                    String normalizedName = normalizeSearch(name);

                    if (normalizedName.contains(searchQuery)) {
                        String absoluteUrl = a.absUrl("href");

                        if (!absoluteUrl.isEmpty()
                                && !containsUrl(results, absoluteUrl)) {
                            results.add(new Show(name, absoluteUrl));
                        }
                    }
                }

                if (results.isEmpty()) {
                    error = "Keine Anime für \"" + query + "\" gefunden.";
                }

            } catch (Exception e) {
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
        if (text == null) return "";

        return java.text.Normalizer.normalize(
                        text.toLowerCase(java.util.Locale.ROOT),
                        java.text.Normalizer.Form.NFD
                )
                .replaceAll("\\p{M}", "")
                .replaceAll("[^a-z0-9]", "");
    }

    private void renderShows(List<Show> shows) {
        for (int i=0;i<shows.size();i+=4) {
            LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL);
            int end=Math.min(i+4,shows.size());
            for(int j=i;j<end;j++) {
                Show s=shows.get(j); TextView card=new TextView(this); card.setText(s.title+"\n\nÖffnen  ›"); card.setTextColor(Color.WHITE); card.setTextSize(16); card.setTypeface(null,Typeface.BOLD);
                card.setGravity(Gravity.CENTER_VERTICAL); card.setPadding(dp(16),dp(12),dp(12),dp(12)); card.setMinHeight(dp(104)); card.setBackground(round(0xFF141B2B,0xFF493A75,12)); card.setFocusable(true);
                card.setOnFocusChangeListener((v,has) -> card.setBackground(round(has?0xFF493A75:0xFF141B2B,has?0xFF9B7BFF:0xFF493A75,12)));
                card.setOnClickListener(v -> openSeries(s));
                LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(112),1); lp.setMargins(0,0,dp(12),dp(12)); row.addView(card,lp);
            }
            catalog.addView(row);
        }
    }

    private void openSeries(Show show) {
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
                        .userAgent("Mozilla/5.0 (Linux; Android 10; Fire TV) AppleWebKit/537.36 Chrome/120 Safari/537.36")
                        .timeout(18000)
                        .get();

                // Wie im PC-Client: Staffel- und Film-Links aus der AniWorld-Navigation lesen.
                Elements seasons = doc.select(".hosterSiteDirectNav a[href]");
                if (seasons.isEmpty()) {
                    seasons = doc.select("a[href*=/staffel], a[href*=/filme]");
                }

                for (Element a : seasons) {
                    String href = a.attr("href").trim();
                    String title = a.attr("title").trim();
                    if (title.isEmpty()) title = a.text().trim();

                    String lowerHref = href.toLowerCase();
                    if (href.isEmpty() || !(lowerHref.contains("staffel") || lowerHref.contains("filme"))) {
                        continue;
                    }
                    if (title.isEmpty()) title = "Staffel";
                    String fullUrl = a.absUrl("href");
                    if (!fullUrl.isEmpty() && !containsUrl(items, fullUrl)) {
                        items.add(new Show(title, fullUrl));
                    }
                }

                if (items.isEmpty()) {
                    error = "Auf dieser Anime-Seite wurden keine Staffeln gefunden.";
                }
            } catch (Exception e) {
                error = "Staffeln konnten nicht geladen werden: " + e.getMessage();
            }

            final String err = error;
            final List<Show> data = items;
            runOnUiThread(() -> {
                catalog.removeAllViews();
                if (err != null) {
                    addMessage(err);
                    addAction("Anime-Seite im Player öffnen", () -> openPlayer(show.url));
                } else {
                    renderSeasons(data);
                }
            });
        });
    }

    private void renderSeasons(List<Show> seasons) {
        level = 1;
        for (Show season : seasons) {
            if (season.title != null && !season.title.contains("Episode")) {
                addAction(season.title, () -> loadEpisodes(season));
            }
        }
    }

    private void loadEpisodes(Show season) {
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
                        .userAgent("Mozilla/5.0 (Linux; Android 10; Fire TV) AppleWebKit/537.36 Chrome/120 Safari/537.36")
                        .timeout(18000)
                        .get();

                // AniWorld listet Folgen normalerweise in der Staffel-Episoden-Tabelle.
                Element table = doc.selectFirst("table.seasonEpisodesList");
                Elements links = table != null
                        ? table.select("tr a[href]")
                        : doc.select("a[href*=/episode/]");

                for (Element a : links) {
                    String href = a.attr("href").trim();
                    String title = a.text().trim();
                    if (href.isEmpty()) continue;

                    String fullUrl = a.absUrl("href");
                    if (title.isEmpty()) title = "Episode " + (episodes.size() + 1);
                    if (!fullUrl.isEmpty() && !containsUrl(episodes, fullUrl)) {
                        episodes.add(new Show(title, fullUrl));
                    }
                }

                // Zusätzlicher Fallback, falls die Tabelle vorhanden, aber leer ist.
                if (episodes.isEmpty()) {
                    Elements fallback = doc.select("a[href*=/episode/]");
                    for (Element a : fallback) {
                        String fullUrl = a.absUrl("href");
                        if (fullUrl.isEmpty() || containsUrl(episodes, fullUrl)) continue;
                        String title = a.text().trim();
                        if (title.isEmpty()) title = "Episode " + (episodes.size() + 1);
                        episodes.add(new Show(title, fullUrl));
                    }
                }

                if (episodes.isEmpty()) {
                    error = "In dieser Staffel wurden keine Episoden gefunden.";
                }
            } catch (Exception e) {
                error = "Episoden konnten nicht geladen werden: " + e.getMessage();
            }

            final String err = error;
            final List<Show> data = episodes;
            runOnUiThread(() -> {
                catalog.removeAllViews();
                if (err != null) {
                    addMessage(err);
                } else {
                    for (Show episode : data) {
                        addAction(episode.title, () -> openEpisode(episode));
                    }
                }
            });
        });
    }

    private void openEpisode(Show episode) {
        level = 3;
        catalog.removeAllViews();
        sectionTitle.setText(episode.title);
        addMessage("Suche Video-Hoster …");

        io.execute(() -> {
            List<Show> hosters = new ArrayList<>();
            String error = null;

            try {
                Document doc = Jsoup.connect(episode.url)
                        .cookies(getCookiesFor(episode.url))
                        .userAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")
                        .header("Accept-Language", "de-DE,de;q=0.9,en;q=0.8")
                        .referrer(BASE + "/")
                        .timeout(20000)
                        .get();

                // AniWorld verwendet li.episodeLink bzw. li[data-link-target].
                // Diese Selektoren entsprechen dem funktionierenden Python-PC-Client.
                for (Element li : doc.select("li.episodeLink, li[data-link-target]")) {
                    String target = li.attr("data-link-target").trim();
                    Element heading = li.selectFirst("h4");
                    String name = heading != null
                            ? heading.text().trim()
                            : li.text().trim();

                    if (target.isEmpty()) {
                        Element link = li.selectFirst("a[href]");
                        if (link != null) target = link.attr("href").trim();
                    }

                    if (!target.isEmpty()) {
                        String absoluteUrl = new java.net.URL(new java.net.URL(episode.url), target).toString();
                        if (!containsUrl(hosters, absoluteUrl)) {
                            hosters.add(new Show(name.isEmpty() ? "Hoster" : name, absoluteUrl));
                        }
                    }
                }

                if (hosters.isEmpty()) {
                    error = "Auf der Episodenseite wurden keine Hoster-Links gefunden.";
                }
            } catch (Exception e) {
                error = "Hoster konnten nicht geladen werden: " + e.getMessage();
            }

            final String err = error;
            final List<Show> data = hosters;
            runOnUiThread(() -> {
                catalog.removeAllViews();
                sectionTitle.setText(episode.title);

                if (err != null) {
                    addMessage(err);
                    addAction("Episodenseite im Browser öffnen", () -> openPlayer(episode.url));
                } else {
                    for (Show hoster : data) {
                        addAction(hoster.title + "  ·  Abspielen",
                                () -> openPlayer(hoster.url));
                    }
                }
            });
        });
    }

    private void openPlayer(String url) {
        mainContent.setVisibility(View.GONE);
        player.setVisibility(View.VISIBLE);
        player.bringToFront();
        player.onResume();
        player.loadUrl(url);
    }
    private void showCatalog() {
        player.stopLoading();
        player.setVisibility(View.GONE);
        mainContent.setVisibility(View.VISIBLE);
    }
    private boolean containsUrl(List<Show> items, String url) { for (Show item : items) if (item.url.equals(url)) return true; return false; }

    private void addMessage(String message){TextView t=new TextView(this);t.setText(message);t.setTextColor(0xFFA8B2C7);t.setTextSize(16);t.setPadding(dp(8),dp(20),dp(8),dp(20));catalog.addView(t);}
    private void addAction(String label,Runnable action){
        Button b=new Button(this);
        b.setFocusable(true);
        b.setOnFocusChangeListener((v, hasFocus) -> {
            if (hasFocus) {
                v.setBackground(round(
                        0xFF493A75,
                        0xFF9B7BFF,
                        8
                ));
            } else {
                v.setBackground(round(
                        0xFF1D2940,
                        0xFF394967,
                        8
                ));
            }
        });
        b.setText(label);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(16);
        b.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
        b.setPadding(dp(18),0,dp(18),0);
        b.setBackground(round(0xFF141B2B,0xFF493A75,10));
        b.setFocusable(true);
        b.setOnClickListener(v->action.run());
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(54));
        lp.setMargins(0,0,0,dp(9));
        catalog.addView(b,lp);
    }

    @Override protected void onDestroy(){io.shutdownNow();player.destroy();super.onDestroy();}
}
