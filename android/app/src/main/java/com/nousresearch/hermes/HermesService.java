package com.nousresearch.hermes;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;

/**
 * Foreground service that keeps the Hermes runtime alive while the app is in the
 * background. Android 14+ requires the foregroundServiceType declared in the
 * manifest to also be passed to {@link #startForeground}.
 *
 * The service is started by {@link MainActivity} when a launch begins — the whole
 * launch is the part most worth protecting from process death — and the ongoing
 * notification follows the runtime's state instead of asserting something that may
 * not be true yet.
 */
public class HermesService extends Service {
    private static final String TAG = "HermesService";
    private static final String CHANNEL_ID = "HermesServiceChannel";
    private static final int NOTIFICATION_ID = 1;

    /** Nothing is running behind the notification (fresh process, or a sticky restart). */
    public static final int STATE_IDLE = 0;
    /** A launch is in progress. */
    public static final int STATE_STARTING = 1;
    /** The Python runtime is up. */
    public static final int STATE_RUNNING = 2;

    // Read by onCreate when the system restarts this service after killing the
    // process: the statics are reset with it, so IDLE then means what it says.
    private static volatile int state = STATE_IDLE;

    /**
     * Starts the foreground service with the notification claiming {@code initialState}.
     *
     * Must be called while the app is in the foreground: Android 12+ throws
     * {@code ForegroundServiceStartNotAllowedException} from the background, which is
     * exactly when a dashboard that just became ready would otherwise call this.
     */
    public static void start(Context context, int initialState) {
        ContextCompat.startForegroundService(context, new Intent(context, HermesService.class));
        // An already-running service only gets onStartCommand, so re-post here to refresh
        // the text. On a cold start this lands before onCreate creates the channel and the
        // post is dropped — onCreate rebuilds the same notification from `state`.
        update(context, initialState);
    }

    /** Re-posts the ongoing notification after the runtime's state changes. */
    public static void update(Context context, int newState) {
        state = newState;
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager != null) {
            manager.notify(NOTIFICATION_ID, buildNotification(context));
        }
    }

    /** Stops the service: a failed launch has nothing to keep alive. */
    public static void stop(Context context) {
        context.stopService(new Intent(context, HermesService.class));
    }

    private static Notification buildNotification(Context context) {
        PendingIntent pendingIntent = PendingIntent.getActivity(
                context, 0, new Intent(context, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);

        int textRes;
        switch (state) {
            case STATE_RUNNING:
                textRes = R.string.notify_running;
                break;
            case STATE_STARTING:
                textRes = R.string.notify_starting;
                break;
            default:
                textRes = R.string.notify_idle;
                break;
        }

        return new NotificationCompat.Builder(context, CHANNEL_ID)
                .setContentTitle(context.getString(R.string.app_name))
                .setContentText(context.getString(textRes))
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .build();
    }

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "HermesService created (state=" + state + ")");
        createNotificationChannel();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIFICATION_ID, buildNotification(this),
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            // The typed overload only exists from API 29 and is only required from 34.
            startForeground(NOTIFICATION_ID, buildNotification(this));
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.i(TAG, "HermesService started");
        return START_STICKY;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel serviceChannel = new NotificationChannel(
                    CHANNEL_ID,
                    "Hermes Agent Service",
                    NotificationManager.IMPORTANCE_LOW
            );
            NotificationManager manager = getSystemService(NotificationManager.class);
            manager.createNotificationChannel(serviceChannel);
        }
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.i(TAG, "HermesService destroyed");
    }
}
