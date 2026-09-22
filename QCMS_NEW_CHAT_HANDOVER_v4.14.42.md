# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.42

### 1. Controlled baseline
- **Application Version:** `4.14.42`
- **Build:** `41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD`
- **Project path:** `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and local secrets.
- Continue versioning from **v4.14.43+**.

### 2. Permanent local-JDK deployment fix
- Root cause of the v4.14.41 updater failure was the regression test invoking `javac` unconditionally.
- On macOS, `/usr/bin/javac` can exist as an Apple launcher even when no Java/JDK runtime is installed; it exits 1 with “Unable to locate a Java Runtime that supports javac.”
- The regression test now probes `javac -version`. If no functional JDK exists, only that Java compile regression test is skipped instead of failing the complete QCMS deployment suite.
- Static source guards still verify the final/effectively-final Android route capture.
- Full Android Java/Gradle compilation remains mandatory in GitHub Actions with `actions/setup-java` / Temurin 17 and `:app:assembleDebug :app:lintDebug`.

### 3. Android state preserved
- Android remains **v0.1.9 / versionCode 10**.
- Final route lambda capture fix from v4.14.41 remains active.
- Queued session-safe navigation, MutationObserver, Streamlit `st.switch_page` bridge and removed bottom footer remain preserved.
- Dynamic APK identity, v2 signature verification, zipalign and package/version checks remain preserved.

### 4. Database/runtime
- Database schema baseline remains **v4.14.36**.
- v4.14.42 adds no schema change and requires no manual SQL.

### 5. Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, dirty-Git protection, source replacement, dependency verification, Python compile, online-readiness, phase verification, complete pytest, Git commit/push and remote SHA verification. Local QCMS deployment must not require the Android JDK toolchain; authoritative Android compilation is handled by the dedicated GitHub Android workflow or the optional local Android build helper when JDK 17 is installed.
