# QCMS / QSMS New-Chat Handover — v4.14.21

Current controlled release: **4.14.21**  
Build: **41421-DEPLOY-RESUME-DELETE-ROUTING**

This hotfix preserves all v4.14.20 functionality and corrects:
- stale macOS TMPDIR deployment failures;
- false Supabase verification failure after v4.14.20 schema was already live;
- OSP/MetLAB/Dimensional transaction deletion being routed to the master-delete RPC;
- unhandled delete exceptions that crashed Streamlit pages.

Deployment remains one self-contained macOS `.command` updater. Preserve all existing Supabase data, Git history, Streamlit Cloud configuration, secrets, uploads, logs, exports and existing workflows.
