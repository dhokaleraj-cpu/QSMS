# QCMS 4.10.4

## RMTC numeric stability
- Corrected the `Heat Steel Balance after Plan (kg)` Streamlit `number_input` so minimum, value and step are consistently floating-point values.
- Related projected heat-balance expressions now use `0.0`, preventing `StreamlitMixedNumericTypesError` when the remaining balance is exactly zero.

## Premium login workspace
- Replaced the plain centered sign-in card with a branded two-panel Four Star Industries / QCMS authentication workspace.
- Added a navy-blue quality-control hero, workflow highlights, secure-access indicators, plant/version identity and a higher-contrast sign-in panel.
- Existing Supabase sign-in, password recovery and controlled preview behavior remains unchanged.

No database schema migration is required for this release.
