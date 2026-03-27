# Docker Smoke Test

## Date

- 2026-03-27

## Environment

- Project path: `/Users/id02987/git/personal/libre_libros/libre_libros_app`
- Runtime: Docker Compose
- Data mount: `../data -> /app/data`
- Seeded admin user: `admin@example.com`

## Iteration Goal

- Verify that the Docker image starts correctly
- Verify that the mounted repository under `data/repo` is imported into the catalogue
- Verify that public book detail pages render
- Verify that markdown assets are served correctly
- Verify that authenticated catalogue and filters work

## Actions And Results

1. Rebuilt and started the service with `docker compose up --build -d`
   - Result: container started successfully
2. Checked container logs with `docker compose logs --no-color --tail=120`
   - Result: application startup completed without the previous `FileNotFoundError: git`
3. Requested `GET /login`
   - Result: `200 OK`
4. Requested `POST /login` with seeded admin credentials
   - Result: `303 See Other`, session cookie issued
5. Requested authenticated `GET /books`
   - Result: `200 OK`, 9 example books visible
6. Requested authenticated `GET /books?course=Primaria&subject=Lengua`
   - Result: `200 OK`, only `Lengua Primaria` shown
7. Requested public `GET /books/1`
   - Result: `200 OK`, rendered markdown contains rewritten asset URLs under `/books/1/assets/...`
8. Requested public `GET /books/1/assets/cover.svg?branch=main`
   - Result: `200 OK`, `content-type: image/svg+xml`

## Issues Found During Iteration

1. Docker image did not include `git`
   - Fix applied: install `git` in `Dockerfile`
2. Book list did not support course/subject filtering
   - Fix applied: added `course` and `subject` query filters and UI controls
3. Markdown image URLs were resolving to `/books/assets/...` and returning `404`
   - Fix applied: rewrite markdown asset URLs to `/books/{book_id}/assets/...` and added an asset-serving route

## Current Residual Warning

- `passlib` still logs a non-blocking warning when reading the installed `bcrypt` package version:
  - `AttributeError: module 'bcrypt' has no attribute '__about__'`
  - The app still authenticates correctly and all tested flows above pass

## Second Iteration

### Goal

- Add index and topic navigation to books
- Add page-based reading controlled by Markdown page breaks
- Make the editor preview respect the same structure
- Fix image rendering inside the editor preview

### Actions And Results

1. Added Markdown page-break support with `<!-- pagebreak -->`
   - Result: page groups are generated server-side from Markdown
2. Added index generation from headings
   - Result: book detail and editor preview now render a topic list
3. Added page navigation UI
   - Result: document markup includes previous/next controls and page indicators
4. Rebuilt Docker image and restarted the service
   - Result: startup successful
5. Requested public `GET /books/1`
   - Result: `200 OK`, response contains `Indice`, `Temas del libro`, heading anchors, and page navigation markup
6. Requested public `GET /books/1/assets/cover.svg?branch=main`
   - Result: `200 OK`, image asset served correctly
7. Requested authenticated `GET /books/1/edit?branch=main`
   - Result: `200 OK`, editor preview contains index, page controls, and image URLs rewritten to `/books/1/assets/...`

## Automated Test Result

- Local test suite: `6 passed`
