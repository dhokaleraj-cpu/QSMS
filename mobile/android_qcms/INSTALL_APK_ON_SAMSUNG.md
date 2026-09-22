# QCMS Mobile v0.1.8 — Samsung internal test

## APK status
The source release includes a build workflow. The APK exists only after an Android build
finishes successfully. Do not rename a ZIP/source archive to .apk.

## Without Android Studio or a USB cable
1. Deploy QCMS v4.14.40 with the supplied updater. The Git push includes the Android workflow.
2. Open your existing QCMS repository on GitHub. Go to Actions > QCMS Android Test APK.
3. Open the run for the deployed commit; wait for a green successful result.
4. Under Artifacts, download **QCMS-Mobile-TEST-APK**. Extract that ZIP.
5. Transfer QCMS_Mobile_v0.1.8_TEST.apk to your Samsung or download/extract it there.
6. Open the APK from My Files. Allow installation from that source only for this test.
7. Launch QCMS Mobile Test, enter the live QCMS HTTPS URL, then use your normal login.

GitHub Actions must be enabled and allowed by your repository/organisation policy.
Private-repository build-minute limits may apply. If the build fails there is no APK;
open the failed step and retain its log. No Supabase/admin credentials are required.
The workflow is also available via Actions > QCMS Android Test APK > Run workflow.

If Samsung Auto Blocker blocks this trusted internal test, temporarily allow the install
through Settings > Security and privacy > Auto Blocker, then restore that protection.
Revoke the install-from-this-source permission afterwards. Do not bypass organisation IT policy.

## What this app is
A test-signed online WebView wrapper around your existing QCMS, not a native rewrite or
an offline database. Requires the live HTTPS address and an internet connection.
Permissions, approvals and business data come from the existing web application.
It contains no Supabase service-role key and does not request location or contacts access.
Some WebView downloads/authentication may need the 'Open QCMS in browser' option;
sign in there separately when prompted. Test this before broad team rollout.

The test package is com.fourstar.qcms.test so it does not overwrite an earlier
com.fourstar.qcms installation. A cached debug signing key is reused on GitHub when
available. If that cache is lost, a later test APK may need the old TEST app uninstalled
first. This resets the test app's saved URL/session, not QCMS cloud records. Production
release signing must use a company-controlled durable key instead of the test key.

## Optional Mac build
Run mobile/android_qcms/BUILD_APK_ONLY.command. It reuses the SDK bootstrap helper and
writes the built, signature-verified APK to ~/Downloads/QCMS_Mobile_v0.1.8_TEST.apk.
Requires an installed JDK 17+ and network access; a phone need not be connected.

## Documentation
- GitHub Gradle build/artifact guide: https://docs.github.com/en/actions/tutorials/build-and-test-code/java-with-gradle
- Android APK verification: https://developer.android.com/tools/apksigner
- Samsung Auto Blocker: https://www.samsung.com/us/support/answer/ANS10003636/
