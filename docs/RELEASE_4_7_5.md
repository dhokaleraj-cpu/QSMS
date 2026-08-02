# QSMS 4.7.5

## Manual RMTC release guard correction

The final authorized part disposition is now the release authority. Automated validation remains visible as a recommendation, but it no longer blocks a reasoned manual acceptance.

- `ACCEPTED` and `ACCEPTED_UNDER_RESERVE` count as released part decisions.
- A failed automated recommendation accepted manually requires a reason.
- Reserve and rejected decisions also require a reason.
- Every covered part requires a final decision before release.
- Existing audit history and Supabase records are preserved.
