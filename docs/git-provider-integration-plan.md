# Git Provider Integration Plan

## Goal

Move commit and push operations away from the Libre Libros backend and make repository writes provider-agnostic.

## Recommended direction

Use a provider bridge with two layers:

1. Platform identity in Libre Libros
2. Linked Git identity per user and per organization

The editorial UI should keep showing `colegio`, `curso` and `mi version docente`. The Git branch mapping stays internal.

## Write model

- The web client edits Markdown and assets locally in the browser.
- The browser sends a provider-specific write request using a short-lived capability granted by the backend.
- The backend should not rewrite full book contents when the provider can accept direct client-originated commits.

## Provider abstraction

Define a provider-neutral account model:

- `GitAccount`
  - provider: `github`, `gitlab`, future `gitea`
  - provider_user_id
  - username
  - access token or installation binding
  - refresh metadata

- `RepositoryBinding`
  - organization or personal scope
  - provider
  - repo identifier
  - default branch
  - permission profile

## Authentication

### GitHub

Preferred path:

- GitHub App for organization and school repositories
- OAuth user login for personal repositories and account linking

Why:

- GitHub App gives better org-level control, narrower permissions, and installation-scoped access
- OAuth is still needed to link a Libre Libros user to a GitHub identity and, if required, let the user work against personal repositories

### GitLab

Preferred path:

- OAuth app plus per-project/group token model

## Token handling

- Store provider secrets encrypted at rest
- Prefer installation tokens or short-lived tokens over long-lived personal access tokens
- Never expose stored provider secrets to templates or persistent browser storage
- Issue short-lived backend-generated session capabilities to the browser when direct provider writes are enabled

## Backend role after refactor

The backend should remain responsible for:

- user session and role model
- organization membership and approval rules
- provider account linking
- repository discovery and permission checks
- issuing short-lived write capabilities
- syncing review metadata not representable directly in provider APIs

## Browser responsibilities after refactor

- editing Markdown and assets
- preparing commit payloads
- creating commits on the selected provider/repository/branch
- opening pull requests or merge requests for cross-school proposals

## Incremental rollout

1. Keep current backend writes as fallback
2. Add linked provider accounts to users and organizations
3. Introduce provider-neutral repository bindings
4. Move personal-branch commits to browser-assisted provider writes
5. Move organization approval flows to provider-backed PR/MR merge actions
6. Remove backend direct-write path once provider-backed flow is stable

## Risks

- browser-to-provider writes need careful CORS and token scope handling
- GitHub App and GitLab OAuth flows differ materially, so the abstraction should stop at the capability boundary, not at raw API shape
- large binary assets should stay constrained; direct browser uploads increase failure modes on unstable networks
