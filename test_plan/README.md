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

## Teacher journey validator

Teacher-centric end-to-end lifecycle:

```bash
cd libre_libros_app
python3 scripts/teacher_playwright_journey.py
```

Generated evidence:

- `test_plan/<fecha>-teacher-journey/run-log.md`
- `test_plan/<fecha>-teacher-journey/teacher-report.md`
- Screenshots from registration to logout
- `server.log`

## UX refinement

Post-validator UX refinement should create a dedicated execution folder, for example:

- `test_plan/<fecha>-ux-refinement/run-log.md`
- Before/after screenshots for the refined surfaces
- Optional notes about the UX issues detected from the validator evidence
- Optional `server.log` when the refinement changed interactive behavior

This phase consumes the evidence already produced by validator runs, reviews the captured journeys as a UX expert, applies interface improvements, and stores a fresh screenshot set after the changes.
