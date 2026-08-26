# QCMS v4.14.8

Build: `4148-AUTO-SAFETY-SNAPSHOT-DIRTY-WORKTREE-DEPLOY`

## Deployment hardening
- Automatically snapshots tracked local changes before deployment instead of stopping on a dirty Git worktree.
- Saves full source backup, binary worktree patch, staged-index patch, Git status, and a local Git stash reference.
- Does not require manual commit or revert before a controlled update.
- Preserves `.git`, `.venv`, `.env`, `.streamlit/secrets.toml`, uploads, logs and exports.
- Retains all QCMS v4.14.7 functional and notification features; no database reset or schema change is required.
- Verifies local/remote Git SHA after push and keeps live runtime build proof.
