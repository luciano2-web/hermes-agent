package com.nousresearch.hermes;

import android.content.Context;
import android.util.Log;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;

/**
 * Owns the process-wide Python runtime and the bridge module that starts Hermes.
 *
 * The Python runtime itself cannot be restarted once started, so initialization
 * is idempotent and there is deliberately no "close": shutting the runtime down
 * is not something Chaquopy supports, and the dashboard server is owned by the
 * thread that started it.
 */
public class PythonManager {
    private static final String TAG = "PythonManager";
    private static Python pythonInstance;
    private static boolean isInitialized = false;

    /** Starts the runtime (once) with HERMES_HOME already pointed at app-private storage. */
    public static synchronized void initialize(Context context) {
        if (isInitialized) {
            Log.i(TAG, "Python already initialized");
            return;
        }

        Context app = context.getApplicationContext();
        File hermesHome = new File(app.getFilesDir(), "hermes-home");
        if (!hermesHome.exists() && !hermesHome.mkdirs()) {
            throw new IllegalStateException("Cannot create HERMES_HOME at " + hermesHome);
        }

        Log.i(TAG, "Starting Python runtime (HERMES_HOME=" + hermesHome + ")");
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(app));
        }
        pythonInstance = Python.getInstance();
        isInitialized = true;
    }

    /**
     * Runs the Hermes web dashboard and blocks until the server stops.
     *
     * Must be called from a background thread: uvicorn serves the request loop on
     * the calling thread.
     */
    public static void startDashboard(File hermesHome, int port) {
        PyObject bridge = getPython().getModule("hermes_android");
        bridge.callAttr("start", hermesHome.getAbsolutePath(), port);
    }

    public static Python getPython() {
        if (!isInitialized) {
            throw new IllegalStateException("Python not initialized. Call initialize() first.");
        }
        return pythonInstance;
    }

    public static boolean isPythonInitialized() {
        return isInitialized;
    }

    public static void shutdown() {
        // The Chaquopy runtime lives for the whole process; only our handle to it is dropped.
        pythonInstance = null;
        isInitialized = false;
        Log.i(TAG, "Python handle released");
    }
}
