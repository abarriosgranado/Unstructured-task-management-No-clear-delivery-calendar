# Finance RACI Timeline

Streamlit web app for managing finance department ownership and recurring delivery timing.

The app is designed around two core views:

- **RACI Matrix**: who owns each finance activity.
- **Timeline**: when each recurring activity happens by period.

Setup pages allow the owner to configure finance areas, roles, department areas, RACI ownership, timeline dates, and the change log.

## App File

Use this file as the Streamlit entry point:

```bash
streamlit_app.py
```

## Local Run

```bash
pip install -r requirements.txt
streamlit run accounting_raci_app.py
```

Local development URL:

```text
http://127.0.0.1:8502
```

That URL is only for your computer. It is not the public website.

## Public Deployment

GitHub stores the code, but GitHub Pages does not run Streamlit apps. To publish this as a real web app, deploy the GitHub repository with a Streamlit-compatible hosting service.

Recommended MVP route:

```text
GitHub repo -> Streamlit Community Cloud -> public .streamlit.app URL
```

Deployment settings:

```text
Repository: your public GitHub repository
Branch: main
Main file path: streamlit_app.py
```

The public URL will look like:

```text
https://your-app-name.streamlit.app
```

For a more branded version, connect a custom domain later.

## Required Secrets

Do not commit real secrets to GitHub.

Configure secrets in Streamlit Cloud under:

```text
App settings -> Secrets
```

Minimum:

```toml
edit_password = "your-private-password"
```

For stable public persistence:

```toml
edit_password = "your-private-password"
database_url = "postgresql://user:password@host:5432/database?sslmode=require"
```

Use a managed Postgres database such as Supabase, Neon, Render Postgres, or Railway Postgres.

Without `database_url`, the app uses local SQLite. That is fine for development, but not reliable for a public deployment because cloud servers can restart or redeploy.

## Local Secrets

For local development, create:

```text
.streamlit/secrets.toml
```

Use `.streamlit/secrets.example.toml` as a template.

The real `secrets.toml` file is intentionally ignored by Git.

## Change Log

Saved setup, RACI, and timeline changes are recorded in the app change log.

## Main Features

- Setup master for finance department areas, roles, and department areas.
- RACI Matrix setup with role dropdowns.
- RACI Matrix view for ownership visibility.
- Timeline setup for period dates and status.
- Timeline view with sticky activity column.
- Change log for saved changes.
- Public deployment-ready dependency file.


## GitHub Publication Checklist

1. Create a public GitHub repository, for example `finance-ownership-timing`.
2. Push these files to the repository. Do not include `.streamlit/secrets.toml`, `.streamlit/credentials.toml`, `.venv/`, `__pycache__/`, or `*.sqlite3` files.
3. In Streamlit Community Cloud, create a new app from the GitHub repository.
4. Use `streamlit_app.py` as the main file path.
5. Add `edit_password` in Streamlit Cloud secrets before allowing edits.
6. Add `database_url` in Streamlit Cloud secrets for persistent public data.

The repository can be public. The real password and database URL must stay only in Streamlit Cloud secrets.
