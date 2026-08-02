#!/usr/bin/env bash
set -euo pipefail

TARGET="/Users/dhokaleraj/QSMS"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_ROOT="/Users/dhokaleraj/QSMS_Backups"
DEPLOY_LOG="$TARGET/logs/github_streamlit_deploy_${STAMP}.log"

mkdir -p "$TARGET/logs" "$BACKUP_ROOT"
exec > >(tee -a "$DEPLOY_LOG") 2>&1

banner() {
  printf '\n============================================================\n'
  printf ' QSMS — GITHUB + STREAMLIT PRODUCTION DEPLOYMENT\n'
  printf '============================================================\n'
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

banner
[[ -d "$TARGET" ]] || fail "QSMS folder was not found at $TARGET"
[[ -f "$TARGET/streamlit_app.py" ]] || fail "streamlit_app.py is missing in $TARGET"
[[ -f "$TARGET/requirements.txt" ]] || fail "requirements.txt is missing in $TARGET"

cd "$TARGET"
VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || echo unknown)"
echo "QSMS version: $VERSION"
echo "Deployment log: $DEPLOY_LOG"

BACKUP_FILE="$BACKUP_ROOT/QSMS_before_GitHub_deploy_${STAMP}.tar.gz"
echo "Creating source backup: $BACKUP_FILE"
tar -czf "$BACKUP_FILE" \
  --exclude='.venv' --exclude='.git' --exclude='logs' \
  --exclude='uploads' --exclude='exports' --exclude='updates' \
  -C "$TARGET" .

cat > .gitignore <<'EOF'
# Secrets and local environment
.streamlit/secrets.toml
.env
.env.*
!.env.example
.deploy_private/
.venv/

# Python and test cache
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/

# Runtime data and generated files
uploads/
exports/
logs/
updates/
*.log
*.db
*.sqlite
*.sqlite3
.DS_Store

# Supabase CLI local state
supabase/.temp/
supabase/.branches/

# Editors
.vscode/*.local.json
.idea/
EOF

mkdir -p .github/workflows docs deploy scripts .deploy_private
cat > .github/workflows/quality-checks.yml <<'YAML'
name: QSMS production checks

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Compile
        run: python -m compileall -q .

      - name: Online readiness
        run: python scripts/check_online_readiness.py

      - name: Test
        run: pytest -q
YAML

cat > docs/PRODUCTION_DEPLOYMENT.md <<'MD'
# QSMS Production Deployment

## Production architecture

- **Source and release history:** Private GitHub repository
- **Application hosting:** Streamlit Community Cloud
- **Live transactional database and authentication:** Supabase
- **Application entrypoint:** `streamlit_app.py`
- **Production Python:** 3.12

## Security controls

- `.streamlit/secrets.toml`, `.env`, uploads, exports, logs and local environments are excluded from Git.
- Only the Supabase publishable/anon key is used by Streamlit.
- Never put the Supabase service-role key in Streamlit or GitHub.
- Supabase Row Level Security remains the database authorization boundary.

## Streamlit Community Cloud configuration

- Repository: the private QSMS GitHub repository
- Branch: `main`
- Main file path: `streamlit_app.py`
- Python version: `3.12`
- Secrets: paste the local `.streamlit/secrets.toml` into Streamlit Advanced settings.

Set production values in Streamlit secrets:

```toml
QSMS_ENVIRONMENT = "Production"
QSMS_ALLOW_PREVIEW = false
QSMS_APP_URL = "https://YOUR-QSMS-APP.streamlit.app"
```

## Future releases

Run:

```bash
cd /Users/dhokaleraj/QSMS && ./scripts/push_github.sh
```

A successful push triggers GitHub Actions. Streamlit Community Cloud then deploys the new `main` branch automatically.
MD

cat > scripts/push_github.sh <<'PUSH'
#!/usr/bin/env bash
set -euo pipefail
TARGET="/Users/dhokaleraj/QSMS"
cd "$TARGET"
[[ -d .git ]] || { echo "Git repository is not initialized. Run QSMS_GITHUB_STREAMLIT_LIVE_DEPLOY.command first."; exit 1; }
[[ -x .venv/bin/python ]] || { echo "QSMS virtual environment is missing."; exit 1; }
source .venv/bin/activate
python -m compileall -q .
python scripts/check_online_readiness.py
pytest -q
git add .
if git diff --cached --quiet; then
  echo "No source changes to push."
  exit 0
fi
VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || echo update)"
git commit -m "QSMS ${VERSION} production update $(date +%Y-%m-%d_%H-%M)"
git push origin main
echo "GitHub push completed. Streamlit Cloud will redeploy from main."
PUSH
chmod +x scripts/push_github.sh

if [[ ! -f .streamlit/secrets.toml ]]; then
  fail ".streamlit/secrets.toml is missing. Configure Supabase locally before production deployment."
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null

echo "Running production checks..."
python -m compileall -q .
python scripts/check_online_readiness.py
pytest -q

command -v git >/dev/null 2>&1 || fail "Git is not installed. Install Xcode Command Line Tools and rerun."
if [[ ! -d .git ]]; then
  git init
  git branch -M main
fi

git config user.name >/dev/null 2>&1 || {
  read -r -p "Git commit name [Rajesh Dhokale]: " GIT_NAME
  git config user.name "${GIT_NAME:-Rajesh Dhokale}"
}
git config user.email >/dev/null 2>&1 || {
  read -r -p "Git commit email [Rajesh.Dhokale@fourstarindustries.com]: " GIT_EMAIL
  git config user.email "${GIT_EMAIL:-Rajesh.Dhokale@fourstarindustries.com}"
}

# Remove sensitive/local files from a previous Git index without deleting local copies.
git rm -r --cached --ignore-unmatch \
  .streamlit/secrets.toml .env .deploy_private .venv uploads exports logs updates \
  >/dev/null 2>&1 || true

git add .

# Validate that no local secret value is present in staged files and reject service-role credentials.
python - <<'PY'
from __future__ import annotations
import base64
import json
import subprocess
import tomllib
from pathlib import Path

root = Path.cwd()
secret_path = root / ".streamlit" / "secrets.toml"
secrets = tomllib.loads(secret_path.read_text(encoding="utf-8"))

flat: dict[str, str] = {}
def walk(prefix: str, value):
    if isinstance(value, dict):
        for k, v in value.items():
            walk(f"{prefix}.{k}" if prefix else str(k), v)
    elif isinstance(value, (str, int, float, bool)):
        flat[prefix] = str(value)
walk("", secrets)

for name, value in flat.items():
    upper = name.upper()
    if "SERVICE_ROLE" in upper:
        raise SystemExit("Service-role credentials are not allowed in the Streamlit secrets file.")
    parts = value.split(".")
    if len(parts) == 3:
        try:
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
            if decoded.get("role") == "service_role":
                raise SystemExit("A Supabase service-role JWT was detected. Use the publishable/anon key only.")
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            pass

staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], text=True
).splitlines()
for path_text in staged:
    path = root / path_text
    if not path.is_file() or path.stat().st_size > 5_000_000:
        continue
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for name, value in flat.items():
        if len(value) >= 12 and value in content:
            raise SystemExit(f"Secret value from {name} was found in staged file: {path_text}")
print("Secret scan passed: no local credential values are staged.")
PY

VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || echo production)"
if git diff --cached --quiet; then
  echo "No new source changes to commit."
else
  git commit -m "QSMS ${VERSION} production baseline $(date +%Y-%m-%d_%H-%M)"
fi

ORIGIN="$(git remote get-url origin 2>/dev/null || true)"
if [[ -z "$ORIGIN" ]]; then
  if ! command -v gh >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      read -r -p "GitHub CLI is not installed. Install it with Homebrew now? [Y/n]: " INSTALL_GH
      if [[ ! "${INSTALL_GH:-Y}" =~ ^[Nn]$ ]]; then
        brew install gh
      fi
    fi
  fi

  if command -v gh >/dev/null 2>&1; then
    if ! gh auth status >/dev/null 2>&1; then
      echo "Authenticate to GitHub in the browser..."
      gh auth login --web --git-protocol https
    fi
    DEFAULT_OWNER="$(gh api user -q .login 2>/dev/null || true)"
    read -r -p "GitHub owner or organization [$DEFAULT_OWNER]: " REPO_OWNER
    REPO_OWNER="${REPO_OWNER:-$DEFAULT_OWNER}"
    read -r -p "Private repository name [FSI-QSMS]: " REPO_NAME
    REPO_NAME="${REPO_NAME:-FSI-QSMS}"
    [[ -n "$REPO_OWNER" ]] || fail "GitHub owner is required."
    if gh repo view "$REPO_OWNER/$REPO_NAME" >/dev/null 2>&1; then
      git remote add origin "https://github.com/$REPO_OWNER/$REPO_NAME.git"
      git push -u origin main
    else
      gh repo create "$REPO_OWNER/$REPO_NAME" --private --source=. --remote=origin --push
    fi
  else
    echo "Create an EMPTY PRIVATE GitHub repository first."
    read -r -p "Paste the private repository HTTPS or SSH URL: " REPO_URL
    [[ -n "$REPO_URL" ]] || fail "Repository URL is required."
    git remote add origin "$REPO_URL"
    git push -u origin main
  fi
else
  echo "Using existing GitHub remote: $ORIGIN"
  git push -u origin main
fi

ORIGIN="$(git remote get-url origin)"
cat > deploy/LIVE_DEPLOYMENT_INFO.txt <<EOF
QSMS production deployment
Repository: $ORIGIN
Branch: main
Entrypoint: streamlit_app.py
Python: 3.12
Supabase: live project configured through Streamlit secrets
Prepared: $(date)
EOF

echo ""
echo "GitHub push completed successfully."
echo "Repository: $ORIGIN"
echo ""
echo "Streamlit Community Cloud settings:"
echo "  Branch: main"
echo "  Main file: streamlit_app.py"
echo "  Python: 3.12"
echo ""

if command -v pbcopy >/dev/null 2>&1; then
  read -r -p "Copy local Streamlit secrets to clipboard for Cloud settings? [Y/n]: " COPY_SECRETS
  if [[ ! "${COPY_SECRETS:-Y}" =~ ^[Nn]$ ]]; then
    pbcopy < .streamlit/secrets.toml
    echo "Secrets copied to clipboard. Paste them only into Streamlit Advanced settings."
  fi
fi

if command -v open >/dev/null 2>&1; then
  open "https://share.streamlit.io/" >/dev/null 2>&1 || true
fi

echo ""
echo "In Streamlit: Create app → repository → main → streamlit_app.py."
echo "Open Advanced settings, choose Python 3.12, and paste the secrets."
echo "After deployment, update QSMS_APP_URL in Streamlit secrets to the final app URL."
echo ""
echo "Future source updates use one command:"
echo "cd /Users/dhokaleraj/QSMS && ./scripts/push_github.sh"
