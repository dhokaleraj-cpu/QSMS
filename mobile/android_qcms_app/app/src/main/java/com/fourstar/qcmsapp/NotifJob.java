package com.fourstar.qcmsapp;

import android.app.job.JobParameters;
import android.app.job.JobService;

/**
 * R35: JobScheduler job (every 15 minutes, on app start / resume and after reboot) that asks
 * qcms_my_notifications(p_unread_only = true) with the stored session and shows the new ones as
 * Android notifications. Quietly does nothing when nobody is signed in. No Firebase SDK needed.
 */
public class NotifJob extends JobService {
    @Override
    public boolean onStartJob(JobParameters params) {
        new Thread(() -> {
            try { Notif.check(getApplicationContext()); } catch (Exception ignored) { }
            jobFinished(params, false);
        }, "qcms-notif-job").start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return true;
    }
}
