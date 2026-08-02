# Deployment Notes

## GitHub

Create a private repository and commit the application excluding `.streamlit/secrets.toml` and `.env`.

```bash
git init
git add .
git commit -m "QSMS Phase 1 masters and traceability"
git branch -M main
git remote add origin YOUR_PRIVATE_REPOSITORY_URL
git push -u origin main
```

The included GitHub Actions workflow compiles the project, verifies Phase 1 structure and runs tests.

## Streamlit hosting

- Main file: `streamlit_app.py`
- Python dependencies: `requirements.txt`
- Configure all values from `.streamlit/secrets.toml.example` in the host's secrets manager.
- Set `QSMS_APP_URL` to the final online QSMS URL.
- Set `FSI_PORTAL_URL` to the final online company portal URL.

## Supabase

The live QSMS project already contains the foundational schema. The Phase 1 migration adds only a read-only, RLS-respecting unified traceability view and search function. It does not reset or delete data.
