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
