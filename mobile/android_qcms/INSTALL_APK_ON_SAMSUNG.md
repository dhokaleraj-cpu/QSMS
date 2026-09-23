# QCMS Mobile v0.2.4 — Samsung internal test

Package: `com.fourstar.qcms.test`

The correct v0.2.4 screen always has a maroon native top bar with **MENU** at the upper-left and version `0.2.4` on the right.

## GitHub build
Use GitHub → Actions → **QCMS Android Test APK**. Download the `QCMS-Mobile-TEST-APK` artifact and install `QCMS_Mobile_v0.2.4_TEST.apk`.

## Local build + install
Run:

```bash
/Users/dhokaleraj/QSMS/mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command
```

The helper verifies the signature, installs the exact test package, verifies versionName/versionCode on the phone, and launches the verified app automatically.
