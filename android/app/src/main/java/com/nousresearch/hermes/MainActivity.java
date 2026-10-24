package com.nousresearch.hermes;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.io.File;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Launches the Hermes runtime (Chaquopy Python) and shows its web dashboard.
 *
 * The dashboard server is the app's real UI: it binds 127.0.0.1 inside this
 * process and is rendered in a WebView. Nothing about it needs runtime storage
 * permissions — HERMES_HOME lives in app-private storage.
 */
public class MainActivity extends AppCompatActivity {
    private static final String TAG = "MainActivity";
    private static final int REQUEST_POST_NOTIFICATIONS = 1001;

    private static final int DASHBOARD_PORT = 9119;
    private static final String DASHBOARD_URL = "http://127.0.0.1:" + DASHBOARD_PORT + "/";
    private static final long READY_TIMEOUT_MS = 180_000L;

    private View introPanel;
    private WebView webView;
    private ProgressBar progressBar;
    private TextView statusText;
    private Button startButton;

    // Thread 1 runs the (blocking) dashboard server, thread 2 waits for it to answer.
    private final ExecutorService executor = Executors.newFixedThreadPool(2);
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private volatile boolean launching = false;
    private volatile String serverError = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        introPanel = findViewById(R.id.introPanel);
        webView = findViewById(R.id.webView);
        progressBar = findViewById(R.id.progressBar);
        statusText = findViewById(R.id.statusText);
        startButton = findViewById(R.id.startButton);

        configureWebView();
        requestNotificationPermissionIfNeeded();

        startButton.setOnClickListener(v -> launchAgent());

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView.getVisibility() == View.VISIBLE && webView.canGoBack()) {
                    webView.goBack();
                } else {
                    finish();
                }
            }
        });

        launchAgent();
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        // Keep every navigation inside the app: the dashboard is the whole UI.
        webView.setWebViewClient(new WebViewClient());
    }

    /** Android 13+: ask for the service notification. Purely optional — never blocks startup. */
    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(
                    this, new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQUEST_POST_NOTIFICATIONS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode,
            @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_POST_NOTIFICATIONS) {
            Log.i(TAG, "POST_NOTIFICATIONS granted=" +
                    (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED));
        }
    }

    private void launchAgent() {
        if (launching) {
            return;
        }
        launching = true;
        serverError = null;
        startButton.setEnabled(false);
        startButton.setVisibility(View.GONE);
        progressBar.setVisibility(View.VISIBLE);
        statusText.setText(R.string.starting_python);

        executor.execute(this::startPython);
    }

    private void startPython() {
        try {
            PythonManager.initialize(getApplicationContext());
        } catch (Throwable t) {
            Log.e(TAG, "Python runtime failed to start", t);
            fail("Python runtime failed to start: " + messageOf(t));
            return;
        }

        runOnUiThread(() -> statusText.setText(R.string.starting_dashboard));

        // The dashboard blocks for the lifetime of the server, so it owns its own thread.
        executor.execute(() -> {
            try {
                PythonManager.startDashboard(new File(getFilesDir(), "hermes-home"), DASHBOARD_PORT);
            } catch (Throwable t) {
                Log.e(TAG, "Hermes dashboard stopped", t);
                serverError = messageOf(t);
            }
        });

        long deadline = System.currentTimeMillis() + READY_TIMEOUT_MS;
        while (System.currentTimeMillis() < deadline) {
            if (serverError != null) {
                fail("Hermes failed to start: " + serverError);
                return;
            }
            if (isDashboardReady()) {
                runOnUiThread(this::showDashboard);
                return;
            }
            try {
                Thread.sleep(500L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
        }
        fail("Timed out waiting for the Hermes dashboard to answer on port " + DASHBOARD_PORT + ".");
    }

    /** Any HTTP answer means the server is up and accepting connections. */
    private boolean isDashboardReady() {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(DASHBOARD_URL).openConnection();
            connection.setConnectTimeout(1_000);
            connection.setReadTimeout(1_000);
            connection.setRequestMethod("GET");
            connection.getResponseCode();
            return true;
        } catch (IOException e) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private void showDashboard() {
        statusText.setText(R.string.loading_dashboard);
        progressBar.setVisibility(View.GONE);
        introPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        webView.loadUrl(DASHBOARD_URL);

        // Keep the agent process alive while the user is elsewhere in the app.
        Intent service = new Intent(this, HermesService.class);
        ContextCompat.startForegroundService(this, service);
    }

    private void fail(String reason) {
        launching = false;
        Log.e(TAG, reason);
        runOnUiThread(() -> {
            progressBar.setVisibility(View.GONE);
            introPanel.setVisibility(View.VISIBLE);
            webView.setVisibility(View.GONE);
            statusText.setText(reason);
            startButton.setText(R.string.retry);
            startButton.setVisibility(View.VISIBLE);
            startButton.setEnabled(true);
            Toast.makeText(this, R.string.error_message, Toast.LENGTH_LONG).show();
        });
    }

    private static String messageOf(Throwable t) {
        return t.getMessage() != null ? t.getMessage() : t.toString();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdownNow();
        webView.destroy();
    }
}
