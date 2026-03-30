# Test Plan Evidence

This folder stores end-to-end usage test evidence generated during validation.

Expected contents for each run:

- One dated subfolder per execution, for example `2026-03-27-smoke`
- A project-level `user_stories.md` defining the end-to-end flows to execute
- `run-log.md` with the tested user histories, steps, and observed results
- Screenshots for each important interaction step
- One browser video in `mp4` format per executed full-flow user story, named after the story with a stable slug such as `user-story-login-y-acceso.mp4`
- Videos paced for human review, with short delays between key actions and a visible click marker
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
- `test_plan/<fecha>-validator-playwright/story-video-report.md`
- `test_plan/<fecha>-validator-playwright/user-story-*.mp4`
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
- `test_plan/<fecha>-teacher-journey/user-story-*.mp4`
- Screenshots from registration to logout
- `server.log`

## UX refinement

Post-validator UX refinement should create a dedicated execution folder, for example:

- `test_plan/<fecha>-ux-refinement/run-log.md`
- Before/after screenshots for the refined surfaces
- One updated `mp4` video per validated user story
- Optional notes about the UX issues detected from the validator evidence
- Optional `server.log` when the refinement changed interactive behavior

This phase consumes the evidence already produced by validator runs, reviews the captured journeys as a UX expert, applies interface improvements, and stores a fresh screenshot set after the changes.

## Auth migration regression

Legacy-password regression coverage for persistent Docker data:

```bash
cd libre_libros_app
./.venv-validator/bin/python -m pytest -q
docker compose up --build -d
curl -i -c /tmp/libre_libros_admin.cookies -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'email=admin@example.com&password=admin12345'
curl -i -b /tmp/libre_libros_admin.cookies http://127.0.0.1:8000/
```

Generated evidence:

- `test_plan/2026-03-29-admin-login-fix/run-log.md`
- Optional container logs proving `POST /login` returns `303`
- Optional SQLite inspection showing the admin hash migrated to `pbkdf2`

## GitLab debug stack

End-to-end validation of the debug compose running Libre Libros against the embedded GitLab server:

```bash
cd libre_libros_app
docker compose up --build -d
./.venv-validator/bin/python scripts/gitlab_debug_playwright_smoke.py
```

Generated evidence:

- `test_plan/<fecha>-gitlab-debug/run-log.md`
- `test_plan/<fecha>-gitlab-debug/validation-report.md`
- `01-login.png`, `02-gitlab-login.png`, `03-dashboard.png`, `04-books.png`, `05-logout.png`

This flow validates that local auth is disabled, the GitLab OAuth login completes, the bootstrapped catalog is visible without duplicated sources, and logout returns to the external-login screen.
