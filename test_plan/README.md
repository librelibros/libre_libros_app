# Test Plan Evidence

This folder stores end-to-end usage test evidence generated during validation.

Expected contents for each run:

- One dated subfolder per execution, for example `2026-03-27-smoke`
- `run-log.md` with the tested user histories, steps, and observed results
- Screenshots for each important interaction step
- Optional `server.log` or exported container logs when runtime issues are investigated

## Playwright smoke validator

Reusable validator flow for local browser checks:

```bash
cd libre_libros_app
python3 -m pip install -r requirements-validator.txt
python3 -m playwright install chromium
python3 scripts/validator_playwright_smoke.py
```

Generated evidence:

- `test_plan/<fecha>-validator-playwright/run-log.md`
- `test_plan/<fecha>-validator-playwright/validation-report.md`
- Login, dashboard, listing, filter, detail, and comment screenshots
- Editor, admin, and logout screenshots
- `book-export.pdf`
- `server.log`

The script launches the app with an isolated SQLite database, imports the example repository from `../data/repo`, signs in with an auto-created admin account, and records the smoke flow.
