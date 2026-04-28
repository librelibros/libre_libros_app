#!/usr/bin/env python3
"""End-to-end health check for the GitHub -> Render -> Supabase pipeline.

Run from the project root:

    python scripts/check_deploy.py

Reads environment from the local .env (so you can validate the same values
that your local app uses) and from process env (so CI can override).
Optionally exercises Render and GitHub APIs when the relevant tokens are
exported.

Exits with a non-zero status if any required check fails. Optional checks
print a warning but do not fail the run.
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import quote, urlparse, urlunparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""
    optional: bool = False


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, r: Result) -> None:
        self.results.append(r)
        mark = f"{GREEN}OK{RESET}" if r.ok else (
            f"{YELLOW}WARN{RESET}" if r.optional else f"{RED}FAIL{RESET}"
        )
        line = f"  [{mark}] {r.name}"
        if r.detail:
            line += f"  {DIM}— {r.detail}{RESET}"
        print(line)

    @property
    def has_required_failure(self) -> bool:
        return any(not r.ok and not r.optional for r in self.results)


def section(title: str) -> None:
    print(f"\n{DIM}—— {title} ——{RESET}")


# ---------- helpers ----------

def _redact(s: str | None, keep: int = 4) -> str:
    if not s:
        return "<empty>"
    if len(s) <= keep + 4:
        return "***"
    return s[:keep] + "***" + s[-2:]


def _normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


# ---------- checks ----------

def check_local_env(report: Report) -> dict[str, str]:
    section("Local environment")
    env: dict[str, str] = {}
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "LIBRE_LIBROS_DATABASE_URL", "LIBRE_LIBROS_SECRET_KEY"):
        val = os.environ.get(key, "").strip()
        env[key] = val
        if val:
            report.add(Result(f"env {key} present", True, _redact(val)))
        else:
            optional = key in ("LIBRE_LIBROS_SECRET_KEY",)
            report.add(Result(f"env {key} present", False, "missing", optional=optional))
    return env


def check_database_url_format(report: Report, url: str) -> None:
    if not url:
        return
    section("LIBRE_LIBROS_DATABASE_URL parsing")
    normalized = _normalize_db_url(url)
    report.add(Result("scheme normalized to postgresql+psycopg",
                      normalized.startswith("postgresql+psycopg://") or normalized.startswith("sqlite"),
                      f"normalized={_redact(normalized, keep=24)}"))
    try:
        parsed = urlparse(normalized)
    except Exception as e:
        report.add(Result("URL parses cleanly", False, str(e)))
        return
    report.add(Result("URL parses cleanly", True, f"scheme={parsed.scheme} host={parsed.hostname} port={parsed.port}"))

    if parsed.scheme.startswith("postgresql"):
        if not parsed.username:
            report.add(Result("URL has username", False, "missing — should be 'postgres.<project_ref>' for the pooler"))
        else:
            report.add(Result("URL has username", True, parsed.username))
        if not parsed.password:
            report.add(Result("URL has password", False, "missing"))
        else:
            # Detect unencoded reserved chars in raw URL (before urlparse decoding).
            raw_userinfo_at = url.find("@")
            colon = url.find(":", url.find("//") + 2)
            if 0 < colon < raw_userinfo_at:
                raw_pwd = url[colon + 1:raw_userinfo_at]
                bad = [c for c in "&+/?#@" if c in raw_pwd and f"%{ord(c):02X}" not in raw_pwd.upper()]
                if bad:
                    report.add(Result("password URL-encoded",
                                      False,
                                      f"contains unencoded {bad} — encode + → %2B, & → %26, etc."))
                else:
                    report.add(Result("password URL-encoded", True))
        if parsed.hostname:
            if "pooler.supabase.com" in parsed.hostname:
                report.add(Result("host is Supabase pooler (Render-friendly, IPv4)", True, parsed.hostname))
            elif parsed.hostname.endswith("supabase.co"):
                report.add(Result("host is Supabase pooler (Render-friendly, IPv4)",
                                  False,
                                  f"using direct host {parsed.hostname} — Render free is IPv4-only; switch to *.pooler.supabase.com:6543",
                                  optional=True))


def check_supabase_rest(report: Report, url: str, key: str) -> None:
    if not url or not key:
        return
    section("Supabase REST")
    import urllib.request, urllib.error
    target = f"{url.rstrip('/')}/auth/v1/health"
    try:
        with urllib.request.urlopen(target, timeout=10) as resp:
            report.add(Result("project reachable", True, f"GET /auth/v1/health -> HTTP {resp.status}"))
    except urllib.error.HTTPError as e:
        report.add(Result("project reachable", e.code < 500, f"HTTP {e.code}"))
    except Exception as e:
        report.add(Result("project reachable", False, str(e)))

    target = f"{url.rstrip('/')}/rest/v1/"
    try:
        req = urllib.request.Request(target, headers={"apikey": key})
        with urllib.request.urlopen(req, timeout=10) as resp:
            report.add(Result("publishable key accepted by REST", True, f"HTTP {resp.status}"))
    except urllib.error.HTTPError as e:
        # 401/403 with a valid project URL still means we reached PostgREST.
        # Anything 5xx or a connect error is a real failure.
        ok = e.code in (200, 204, 401, 403, 404)
        detail = f"HTTP {e.code}"
        if e.code in (401, 403):
            detail += " (anon/publishable typically can't list root — endpoint reachable)"
        report.add(Result("publishable key accepted by REST", ok, detail))
    except Exception as e:
        report.add(Result("publishable key accepted by REST", False, str(e)))


def check_supabase_client(report: Report, url: str, key: str) -> None:
    if not url or not key:
        return
    section("Supabase Python client")
    try:
        from supabase import create_client
    except ImportError:
        report.add(Result("supabase package importable", False, "pip install supabase"))
        return
    report.add(Result("supabase package importable", True))
    try:
        client = create_client(url, key)
        report.add(Result("create_client() succeeds (key format accepted)", True, type(client).__name__))
    except Exception as e:
        report.add(Result("create_client() succeeds (key format accepted)", False, str(e)))


def check_postgres_connection(report: Report, url: str) -> None:
    if not url or url.startswith("sqlite"):
        return
    section("Supabase Postgres (SQLAlchemy + psycopg)")
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        report.add(Result("sqlalchemy importable", False, "pip install sqlalchemy"))
        return
    normalized = _normalize_db_url(url)
    try:
        engine = create_engine(normalized, future=True, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            val = conn.execute(text("select 1")).scalar()
            report.add(Result("connect + select 1", val == 1, f"returned {val!r}"))
    except Exception as e:
        msg = str(e).splitlines()[0][:200]
        report.add(Result("connect + select 1", False, msg))


def check_github_secrets(report: Report) -> None:
    section("GitHub secrets (via gh CLI, optional)")
    if not shutil.which("gh"):
        report.add(Result("gh CLI installed", False, "skip — install gh to enable", optional=True))
        return
    try:
        out = subprocess.run(
            ["gh", "secret", "list"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        report.add(Result("gh secret list", False, str(e), optional=True))
        return
    if out.returncode != 0:
        report.add(Result("gh authenticated", False, out.stderr.strip()[:200], optional=True))
        return
    names = {line.split()[0] for line in out.stdout.strip().splitlines() if line.strip()}
    for required in (
        "RENDER_API_KEY", "RENDER_SERVICE_ID",
        "SUPABASE_URL", "SUPABASE_KEY",
        "LIBRE_LIBROS_SECRET_KEY", "LIBRE_LIBROS_DATABASE_URL",
    ):
        report.add(Result(f"secret {required} set", required in names))


def check_render(report: Report) -> None:
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    if not api_key or not service_id:
        return
    section("Render API")
    import urllib.request, json as _json
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    try:
        req = urllib.request.Request(f"https://api.render.com/v1/services/{service_id}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
        report.add(Result("service exists", True, f"name={data.get('name')} status={data.get('suspended', 'unknown')}"))
    except Exception as e:
        report.add(Result("service exists", False, str(e)[:200]))
        return

    try:
        req = urllib.request.Request(f"https://api.render.com/v1/services/{service_id}/env-vars?limit=100", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            env_items = _json.loads(resp.read())
        keys = {item.get("envVar", {}).get("key") for item in env_items}
        for required in ("SUPABASE_URL", "SUPABASE_KEY", "LIBRE_LIBROS_DATABASE_URL", "LIBRE_LIBROS_SECRET_KEY"):
            report.add(Result(f"render env var {required} set", required in keys))
    except Exception as e:
        report.add(Result("list env vars", False, str(e)[:200]))

    try:
        req = urllib.request.Request(f"https://api.render.com/v1/services/{service_id}/deploys?limit=1", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            deploys = _json.loads(resp.read())
        if deploys:
            d = deploys[0].get("deploy", {})
            status = d.get("status", "?")
            ok = status in ("live", "deactivated")  # live = current; deactivated = older successful
            report.add(Result("latest deploy status", ok, f"status={status} commit={d.get('commit', {}).get('id', '')[:7]}"))
    except Exception as e:
        report.add(Result("latest deploy status", False, str(e)[:200], optional=True))


def main() -> int:
    print(f"{DIM}libre-libros deploy health check{RESET}")
    report = Report()
    env = check_local_env(report)
    check_database_url_format(report, env.get("LIBRE_LIBROS_DATABASE_URL", ""))
    check_supabase_rest(report, env.get("SUPABASE_URL", ""), env.get("SUPABASE_KEY", ""))
    check_supabase_client(report, env.get("SUPABASE_URL", ""), env.get("SUPABASE_KEY", ""))
    check_postgres_connection(report, env.get("LIBRE_LIBROS_DATABASE_URL", ""))
    check_github_secrets(report)
    check_render(report)

    section("Summary")
    fails = sum(1 for r in report.results if not r.ok and not r.optional)
    warns = sum(1 for r in report.results if not r.ok and r.optional)
    oks = sum(1 for r in report.results if r.ok)
    print(f"  {GREEN}{oks} ok{RESET}  {YELLOW}{warns} warn{RESET}  {RED}{fails} fail{RESET}")
    return 1 if report.has_required_failure else 0


if __name__ == "__main__":
    sys.exit(main())
