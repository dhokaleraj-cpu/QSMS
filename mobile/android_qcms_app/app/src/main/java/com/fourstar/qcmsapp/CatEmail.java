package com.fourstar.qcmsapp;

import java.util.List;

/**
 * More tab → Email (app_pages/email_center.py): Send Email, My Sent Emails, Email Groups - all native.
 * "My Email Settings" (personal mailbox / From identity) is intentionally not in the app: personal mail
 * passwords and mailbox connections are handled only on the QCMS website.
 */
public final class CatEmail {
    private CatEmail() { }

    private static final String EMAIL = "Email";

    public static void register(List<Module> list) {
        list.add(new Module("email_send", "Send Email", Catalog.MORE, EMAIL, "")
            .desc("Email employees, departments and groups through the company mailbox (shows your name & email)")
            .readOnly().noEdit()
            .custom(SndEmailSend::new));

        list.add(new Module("email_sent", "My Sent Emails", Catalog.MORE, EMAIL, "")
            .desc("Your emails with delivery status, server errors and Retry")
            .readOnly().noEdit()
            .custom(SndEmailSent::new));

        list.add(new Module("email_groups", "Email Groups", Catalog.MORE, EMAIL, "qcms_mail_groups")
            .desc("Saved distribution lists (e.g. Quality Team, Plant Heads)")
            .filter("&status=eq.ACTIVE")
            .readOnly().noEdit()
            .custom(SndEmailGroups::new));
    }
}
