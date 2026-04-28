---
name: check-deploy
description: Verifies the GitHub → Render → Supabase pipeline end-to-end. Checks local .env, Supabase REST + publishable key, Postgres connectivity via SQLAlchemy/psycopg, GitHub repository secrets, and the Render service (env vars + last deploy). Use when a deploy fails, when secrets change, or before pushing risky changes.
---

# /check-deploy

Runs `scripts/check_deploy.py` from the project root and reports OK / WARN / FAIL for every step of the deploy pipeline.

## When to use

- A Render deploy just failed and you want to know whether the cause is local, in GitHub secrets, in the workflow, or in Supabase.
- You rotated the Supabase password or any secret and want to confirm it propagated.
- You're about to push a change that might affect the deploy and want a green baseline first.

## How to run

From the project root (`libre_libros_app/`):

```bash
python scripts/check_deploy.py
```

To exercise the Render-side checks, export the same tokens the workflow uses:

```bash
RENDER_API_KEY=... RENDER_SERVICE_ID=... python scripts/check_deploy.py
```

To exercise the GitHub-secrets check, ensure `gh` is authenticated (`gh auth status`).

## What it checks

1. **Local env** — `SUPABASE_URL`, `SUPABASE_KEY`, `LIBRE_LIBROS_DATABASE_URL`, `LIBRE_LIBROS_SECRET_KEY` are present (loaded from `.env`).
2. **`LIBRE_LIBROS_DATABASE_URL` shape** — scheme is `postgresql+psycopg` (or normalisable to it), URL parses, has username + password, password is URL-encoded, host is the Supabase pooler (Render free is IPv4-only — the direct `db.*.supabase.co` host won't resolve there).
3. **Supabase REST** — `/auth/v1/health` reachable; publishable key accepted by `/rest/v1/`.
4. **Supabase Python client** — `supabase.create_client(...)` accepts the key format.
5. **Postgres connection** — `SQLAlchemy + psycopg` connect and `SELECT 1`.
6. **GitHub secrets** (optional, needs `gh` auth) — six required secrets are set: `RENDER_API_KEY`, `RENDER_SERVICE_ID`, `SUPABASE_URL`, `SUPABASE_KEY`, `LIBRE_LIBROS_SECRET_KEY`, `LIBRE_LIBROS_DATABASE_URL`.
7. **Render** (optional, needs `RENDER_API_KEY` + `RENDER_SERVICE_ID` exported) — service exists, env vars are set on the service, latest deploy status.

Exits non-zero when any **required** check fails. Optional checks print WARN and don't fail the run.

## Common failures and what they mean

- `failed to resolve host '...&@db.*.supabase.co'` → password contains `+`, `&`, `@`, `/`, `#` or `?` and isn't URL-encoded. Encode every reserved char (`+` → `%2B`, `&` → `%26`, `@` → `%40`, ...).
- `Network is unreachable` on `db.*.supabase.co` → using the direct host on Render free, which is IPv4-only. Switch to `aws-0-<region>.pooler.supabase.com:6543`.
- `password authentication failed` → wrong DB password, or stale (Supabase requires reset after every password change).
- `ModuleNotFoundError: psycopg2` → URL uses bare `postgresql://` and SQLAlchemy defaults to psycopg2. The app already normalises this in `app/database.py`, but if you see it in another context, force `postgresql+psycopg://`.
- `gh: not authenticated` → run `gh auth login` (SSH, your existing key) or set `GH_TOKEN`.
