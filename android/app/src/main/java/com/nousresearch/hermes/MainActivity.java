package com.nousresearch.hermes;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
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

    // The dashboard server blocks for its whole life, so it runs on a process-wide
    // executor that is never shut down: onDestroy() must not be able to interrupt it.
    // Interrupting here would kill a running server while the static flag below still
    // says it is up, and the next Activity would then wait out the whole ready timeout
    // for a server nobody will ever start again.
    private static final ExecutorService SERVER_EXECUTOR = Executors.newSingleThreadExecutor();
    private static final Object SERVER_LOCK = new Object();

    // This Activity's own pool: only the launch and the ready-poll, both safe to interrupt.
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    // Process-wide launch state. The Python runtime and the dashboard outlive this
    // Activity (rotation, relaunch from the launcher while the foreground service keeps
    // the process alive), so a new MainActivity must attach to the running server instead
    // of starting a second one, which would only ever fail with "port already in use".
    private static volatile boolean dashboardRunning = false;
    private static volatile String dashboardError = null;

    private volatile boolean launching = false;

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

        if (dashboardError != null) {
            // The previous launch failed: show that instead of auto-retrying on every
            // recreation. Retry is the user's call. Nothing is running, so drop the
            // service a failed launch may have left behind.
            HermesService.stop(getApplicationContext());
            showFailure(dashboardError);
        } else {
            launchAgent();
        }
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
        dashboardError = null;
        startButton.setEnabled(false);
        startButton.setVisibility(View.GONE);
        progressBar.setVisibility(View.VISIBLE);
        statusText.setText(R.string.starting_python);

        // Now, while the app is in the foreground: Android 12+ throws
        // ForegroundServiceStartNotAllowedException if a foreground service is started
        // from the background, which is where a dashboard that becomes ready after the
        // user pressed Home would be. Starting here also covers the launch itself —
        // the longest and most killable phase — instead of only the result.
        HermesService.start(this, HermesService.STATE_STARTING);

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

        HermesService.update(getApplicationContext(), HermesService.STATE_RUNNING);
        runOnUiThread(() -> statusText.setText(R.string.starting_dashboard));

        // Path (not a Context) so the static executor never keeps this Activity alive.
        final File hermesHome = new File(getApplicationContext().getFilesDir(), "hermes-home");
        // One launch at a time: without this, two Activities racing through the window
        // would both submit a server and the loser would fail to bind port 9119.
        synchronized (SERVER_LOCK) {
            if (!dashboardRunning) {
                dashboardRunning = true;
                SERVER_EXECUTOR.execute(() -> {
                    try {
                        int rc = PythonManager.startDashboard(hermesHome, DASHBOARD_PORT);
                        // 0: the server this call started has stopped. 1: another thread already
                        // owns it, so this one was a no-op and the server keeps running.
                        if (rc == 0) {
                            dashboardRunning = false;
                        }
                    } catch (Throwable t) {
                        Log.e(TAG, "Hermes dashboard stopped", t);
                        dashboardRunning = false;
                        dashboardError = messageOf(t);
                    }
                });
            }
        }

        long deadline = System.currentTimeMillis() + READY_TIMEOUT_MS;
        while (System.currentTimeMillis() < deadline) {
            String error = dashboardError;
            if (error != null) {
                fail("Hermes failed to start: " + error);
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
        // The poll thread can win the race against onDestroy(); never touch a dead WebView.
        if (isDestroyed()) {
            return;
        }
        statusText.setText(R.string.loading_dashboard);
        progressBar.setVisibility(View.GONE);
        introPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        webView.loadUrl(DASHBOARD_URL);
    }

    private void fail(String reason) {
        launching = false;
        dashboardError = reason;
        Log.e(TAG, reason);
        // A failed launch has nothing to keep alive, and this must hold even when the
        // Activity is already gone and showFailure() will never run.
        HermesService.stop(getApplicationContext());
        runOnUiThread(() -> {
            if (isDestroyed()) {
                return;
            }
            showFailure(reason);
        });
    }

    /** UI half of {@link #fail}: launch screen with the reason and a working Retry. */
    private void showFailure(String reason) {
        progressBar.setVisibility(View.GONE);
        introPanel.setVisibility(View.VISIBLE);
        webView.setVisibility(View.GONE);
        statusText.setText(reason);
        startButton.setText(R.string.retry);
        startButton.setVisibility(View.VISIBLE);
        startButton.setEnabled(true);
        Toast.makeText(this, R.string.error_message, Toast.LENGTH_LONG).show();
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
