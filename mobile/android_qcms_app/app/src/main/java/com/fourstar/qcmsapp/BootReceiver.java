package com.fourstar.qcmsapp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** R35: re-schedules the 15-minute notification check after the phone restarts or the app is updated. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent == null ? "" : String.valueOf(intent.getAction());
        if (Intent.ACTION_BOOT_COMPLETED.equals(action) || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) {
            Notif.schedule(context);
        }
    }
}
