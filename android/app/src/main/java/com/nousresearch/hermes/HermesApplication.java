package com.nousresearch.hermes;

import android.app.Application;
import android.util.Log;

public class HermesApplication extends Application {
    private static final String TAG = "HermesApplication";

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "Hermes Application started");
    }
}
