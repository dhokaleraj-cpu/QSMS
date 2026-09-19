# QCMS v4.14.34 — Individual PO PDFs and Android APK build workflow

## Purchase Order PDF workspace
Select one or more POs under Supply Chain > Purchase Order > Purchase Order PDF >
Batch Print / Email Multiple Purchase Orders. The main batch download is now a ZIP
containing one complete PDF per distinct PO. Individual PDF download buttons are
also available. Filename is the PO number with unsafe characters normalised and a
suffix only when needed to prevent collisions.

Each file contains its own PO and portrait Terms & Conditions; different POs never
share a PDF. Copies per PO (1–5) repeats that PO within its own file only. The existing
combined helper remains for backwards compatibility but is not called by this UI.
Missing/no-longer-accessible orders or empty items stop the export with a visible
error, rather than silently omitting a selected PO from a supposedly complete batch.

Separate supplier emails, approval gates, customer-safe print behaviour, master Part
Description, portrait terms, raw-material types and previous app functionality remain.
No database migration is added. Previously downloaded PDFs are not rewritten.

## Android
Mobile source version 0.1.2, test application id com.fourstar.qcms.test.
The repository now includes .github/workflows/qcms-android-test-apk.yml. It builds
on mobile-source/workflow pushes and manual dispatch, with Java 17, Gradle 8.9 and
Android API 35. Compilation and Android lint must pass; apksigner, zipalign and package
identity checks must pass before the APK artifact can be downloaded. No production
Supabase or other business-data credentials are passed to this workflow.

The Mac APK-only helper writes the completed APK to Downloads without requiring a phone.
WebView settings navigation no longer relies on an unavailable Settings constant;
unsupported downloads use a user-confirmed browser fallback and safe-area padding is added.

## Verification boundary
A compiled APK was NOT produced in this preparation runtime: Android SDK was absent
and the SDK/toolchain download attempts failed. The CI workflow has not been run here.
The source ZIP is not an APK. No live Mac/cloud deployment, real-device Samsung test,
Supabase check or email delivery was performed in this release preparation.
Use a successful CI or local Android build to produce the actual installable APK.
See mobile/android_qcms/INSTALL_APK_ON_SAMSUNG.md for the build/download steps.
