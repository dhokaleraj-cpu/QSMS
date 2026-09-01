# QCMS / QSMS Handover — v4.14.19

Authoritative release: **4.14.19**  
Build: **41419-PO-LIVE-EMPLOYEE-DELETE-USER-STATUS-SAME-HEAT-CONFIRMATION-IMAGES**

Continue from v4.14.19 only. Preserve all Supabase production data, Git history, Streamlit Cloud configuration, secrets, uploads, logs and exports.

## Latest controlled contracts

1. Purchase Order Create permission must be enforced consistently by UI and Supabase; Employee identity is resolved live, not only from stale session state.
2. User ↔ Employee link persists unless explicit unlink is confirmed. Employee Master email is independent from login email.
3. Delete/Archive permission controls transaction deletion; password confirmation is mandatory; downstream genealogy blocks unsafe deletion. OSP uses dedicated reversal-aware delete RPCs.
4. Transaction registers expose Created By User, Last Modified By User and Data Entry Status.
5. Same Heat may have multiple RMTC/TC certificates if Supplier RMTC Number differs; all reuse canonical Internal Heat Code and participate in the Heat ledger/Material Inward independently after approval.
6. MetLAB/RMTC microstructure accepts PNG/JPG/JPEG/BMP/TIF/TIFF/WEBP/GIF.
7. PO approval is followed by Supplier Purchase Order Confirmation with attachment. An immediate request plus daily priority supplier reminder continues until confirmed.
8. Every future release remains one self-contained macOS `.command` updater with automatic Supabase verification/migration, tests, Git push and remote SHA verification.
