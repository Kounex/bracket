# AGENTS.md

Guidance for AI coding agents working on this repository. Assumes no prior knowledge of
the project.

Component-specific conventions live in nested files:

- `backend/AGENTS.md` — Python/FastAPI layering, routes, SQL, models, error handling
- `frontend/AGENTS.md` — React/TypeScript components, data fetching, state, i18n

## Project overview

**Bracket** is an open-source tournament system (GitHub: `evroon/bracket`, licensed AGPL-v3.0).
It supports single elimination, round-robin and Swiss tournament formats, with multiple clubs,
tournaments per club, stages per tournament, drag-and-drop match scheduling, and public dashboard
pages.

This working copy is a **fork**: `origin` is the fork (github.com/Kounex/bracket), `upstream` is
https://github.com/evroon/bracket.git. See "Git workflow and releases" below.

The repository is a monorepo with three main components:

- `backend/` — async Python API built with **FastAPI**, served by **gunicorn + uvicorn workers**.
- `frontend/` — **React 19 + Vite + TypeScript** SPA using the **Mantine 8** component library.
- `docs/` — documentation site built with **Next.js + Nextra** (published at docs.bracketapp.nl).

The database is **PostgreSQL**; there is no SQLite fallback. Everything (including local dev and
tests) needs a running Postgres instance.

## Repository layout

```
backend/          Python backend (FastAPI)
  bracket/        Main application package
    app.py        FastAPI app factory, middleware, router registration, static/frontend serving
    config.py     Environment-based configuration (pydantic-settings)
    database.py   `databases` (asyncpg) connection + sync SQLAlchemy engine
    schema.py     SQLAlchemy Core table definitions (single source of truth for the DB schema)
    routes/       FastAPI routers, one file per resource (auth, clubs, courts, matches, ...)
    models/       Pydantic models; `models/db/` mirrors the DB tables
    sql/          Database access layer (raw queries via `databases`), one file per resource
    logic/        Business logic: scheduling/, planning/, ranking/, scoring, subscriptions
    utils/        Helpers: db_init, dummy_records, security, pagination, errors, ...
    cronjobs/     Background jobs (e.g. automatic scheduling), started only in PRODUCTION
    uvicorn.py    RestartableUvicornWorker (gunicorn worker class used for dev auto-reload)
  alembic/        Database migrations (alembic.ini at backend root)
  tests/          pytest suite: `integration_tests/` (API, need Postgres) and `unit_tests/`
  cli.py          Click CLI: create-dev-db, register-user, generate-openapi, hash-password
  openapi/        Generated openapi.json + Pydantic schema customizations
  static/         User-uploaded files (e.g. tournament logos)
frontend/         React SPA
  src/pages/      Route-level components (login, clubs, tournaments/, ...)
  src/components/ Reusable UI (brackets, builder, tables, modals, scheduling, dashboard, ...)
  src/services/   API-facing service functions per resource
  src/openapi/    GENERATED API client (@hey-api/openapi-ts) — do not edit by hand
  public/locales/ i18n translation files (i18next; managed via Crowdin)
docs/             Nextra/Next.js documentation site
.agents/skills/   Agent skills (e.g. release-version)
.github/workflows/ CI: backend.yml, frontend.yml, docs-build.yml, docker-*.yml, ...
```

## Tech stack

- **Backend**: Python ≥ 3.12 (CI uses 3.12; Docker uses 3.14), FastAPI, SQLAlchemy 2 Core +
  `databases[asyncpg]` for async queries, Alembic for migrations, Pydantic v2 + pydantic-settings,
  JWT auth (pyjwt, passlib/bcrypt; HS256 tokens, 1-week expiry), fastapi-sso for SSO,
  heliclockter for tz-aware datetimes, Sentry SDK (optional), hCaptcha for registration,
  dependency management with **uv** (`uv.lock`, `pyproject.toml`, `package = false`).
- **Frontend**: React 19, Vite 8, TypeScript 5.9, Mantine 8 (+ @mantine/form 9), react-router 7,
  SWR (reads) + axios (writes) for data fetching, nuqs for URL query state,
  @hello-pangea/dnd for drag-and-drop, i18next for translations (12 languages, Crowdin sync),
  package manager **pnpm** (Node 22 in CI, corepack enabled).
- **Docs**: Next.js 16 + Nextra 4 + Tailwind, pnpm.

## Architecture

### System design

```
┌─────────────────────┐     REST/JSON      ┌────────────────────────┐
│   React 19 SPA      │ ─────────────────►  │   FastAPI Backend      │
│   Vite 8 + Mantine  │   Bearer JWT        │                        │
│   SWR + Axios       │ ◄───────────────── │   routes/ → logic/     │
└─────────────────────┘                     │        ↓       ↓       │
                                            │       sql/ ← schema.py │
                                            └──────────┬─────────────┘
                                                       │
                                            ┌──────────▼─────────────┐
                                            │     PostgreSQL         │
                                            │   (asyncpg + databases)│
                                            └────────────────────────┘
```

Three-tier SPA + REST monolith, deployable combined or split.

- Backend layers: `routes/ → logic/ → sql/ → schema.py` (details in `backend/AGENTS.md`)
- Frontend layers: `pages/ → components/ → services/ → openapi/` (details in
  `frontend/AGENTS.md`)
- OpenAPI-first contract: backend generates the spec, frontend generates TS types from it
  (see "API contract (OpenAPI)").

### Database schema

Core entity hierarchy:

```
clubs (multi-tenant root)
  └── tournaments (per-club)
        ├── stages (tournament phases)
        │     └── stage_items (brackets/groups within a stage)
        │           ├── stage_item_inputs (team slots + standings: points, W/D/L)
        │           └── rounds (collections of matches)
        │                 └── matches (actual games, scores, court assignment)
        ├── teams (tournament-scoped)
        │     └── players_x_teams (many-to-many)
        ├── players (tournament-scoped, stats: elo, swiss, W/D/L)
        ├── courts (physical play areas)
        └── rankings (point rules: win/draw/loss values)
```

Access control:

```
users
  └── users_x_clubs (OWNER / COLLABORATOR)
        └── clubs → tournaments (club membership = tournament access)
```

Key tables:

| Table | Key Columns | Notes |
|-------|-------------|-------|
| clubs | id, name | Multi-tenant root |
| tournaments | id, name, club_id, status, dashboard_public | OPEN/ARCHIVED status |
| stages | id, name, tournament_id, is_active | Sequential tournament phases |
| stage_items | id, name, stage_id, type, team_count, ranking_id | SINGLE_ELIMINATION / SWISS / ROUND_ROBIN |
| stage_item_inputs | id, slot, stage_item_id, team_id, points, W/D/L | Team assignments + standings |
| rounds | id, name, stage_item_id, is_draft | Draft rounds for Swiss scheduling |
| matches | id, round_id, input1_id, input2_id, scores, court_id | Game results |
| teams | id, name, tournament_id, elo_score, swiss_score | Tournament-scoped |
| players | id, name, tournament_id, elo_score, swiss_score | Individual participants |
| users | id, email, password_hash, account_type | REGULAR / DEMO |
| courts | id, name, tournament_id | Physical play areas |
| rankings | id, tournament_id, win/draw/loss_points | Scoring rules |

A tournament is built from nested components: **stages** are sequential phases (e.g. group stage
→ knockout), **stage items** are individual brackets/groups within a stage (type determines
format), **stage item inputs** are the team slots tracking standings, **rounds** group matches
(Swiss uses draft rounds for dynamic scheduling), and **matches** are individual games with two
inputs, scores, and an optional court. The scheduling engine in `logic/scheduling/` generates
match pairings based on the stage item type (elimination tree, Swiss pairing, round-robin matrix).

### Key data flows

CRUD operation (e.g. create team):

```
1. Frontend: form submit → createTeam() in services/team.tsx
2. Axios POST /tournaments/{id}/teams with TeamBody JSON
3. Backend route: auth check → validate body → sql_create_team()
4. SQL: INSERT INTO teams ... RETURNING id
5. Response: SuccessResponse → {"success": true}
6. Frontend: await swrTeamsResponse.mutate() → SWR refetches
```

Auth flow:

```
1. POST /token with email + password (OAuth2 form)
2. Backend: bcrypt verify → mint JWT (HS256, 1-week)
3. Response: {access_token, token_type, user_id}
4. Frontend: store in localStorage('login')
5. Subsequent requests: Authorization: bearer <token>
6. Backend: decode JWT → load user → check club membership
```

## Configuration

The backend is configured via environment variables or `.env` files, selected by the
`ENVIRONMENT` variable (`backend/bracket/config.py`):

- `CI` → `ci.env` (committed; used by pytest; expects Postgres at `localhost:5532`)
- `DEVELOPMENT` → `dev.env` (gitignored; defaults baked into `DevelopmentConfig`; Postgres at
  `localhost:5432`)
- `PRODUCTION` → `prod.env` (gitignored)
- `DEMO` → `demo.env` (gitignored)

Key settings: `PG_DSN` (required), `JWT_SECRET` (required), `ADMIN_EMAIL`/`ADMIN_PASSWORD`,
`CORS_ORIGINS`/`CORS_ORIGIN_REGEX`, `AUTO_RUN_MIGRATIONS` (default true), `SERVE_FRONTEND` +
`API_PREFIX` (serve the built frontend from the backend), `ALLOW_USER_REGISTRATION`,
`CAPTCHA_SECRET`, `SENTRY_DSN`.
Note: when running under pytest, the environment defaults to `CI` automatically.

The frontend is configured with Vite-style `.env` files (`frontend/.env.development` is
committed): `VITE_API_BASE_URL` (must include `/api` when the backend uses `API_PREFIX=/api`)
and `VITE_HCAPTCHA_SITE_KEY`.

## Build, run and test commands

All backend commands run from `backend/` (with uv); all frontend commands from `frontend/`
(with pnpm).

### Development

- `./dev.sh` (repo root) — full local dev setup: starts Postgres via
  `podman compose -f docker-compose.dev.yml up -d`, seeds the dev DB
  (`cli.py create-dev-db`, skips if populated), then runs backend (gunicorn with reload on
  port 8400) and frontend (Vite on port 3000). Dev login: `test@example.org` /
  `aeGhoe1ahng2Aezai0Dei6Aih6dieHoo`.
- `./run.sh` — same backend+frontend startup without Postgres handling (assumes DB exists).
- Alternative: `cp process-compose-example.yml process-compose.yml && process-compose up -d`
  runs frontend (:3000), backend (:8400) and docs (:3001).
- Backend only: `cd backend && ENVIRONMENT=DEVELOPMENT uv run gunicorn -k bracket.uvicorn.RestartableUvicornWorker bracket.app:app --bind localhost:8400 --reload`
- Frontend only: `cd frontend && pnpm dev`
- Install deps: `uv sync` (backend), `pnpm i` (frontend, docs).

### Backend tests and checks

- Tests: `cd backend && ENVIRONMENT=CI uv run pytest --cov --cov-report=xml . -vvv`
  - **A Postgres database must be reachable at the DSN in `backend/ci.env`**
    (`postgresql://bracket_ci:bracket_ci@localhost:5532/bracket_ci`). The test fixtures drop and
    recreate the schema from `bracket/schema.py`; they support parallel runs via pytest-xdist.
- Lint/format/typecheck pipeline (mirrors CI, see `backend/precommit.sh`):
  - `uv run ruff format .` / `uv run ruff check --fix .`
  - `uv run dmypy run -- --follow-imports=normal --junit-xml= .` (mypy)
  - `uv run pyrefly check`
  - `uv run pylint cli.py bracket tests`
  - `uv run vulture` — must report no unused functions/classes/methods
  - `uv run ./cli.py generate-openapi` — regenerates `backend/openapi/openapi.json`; run this
    whenever API routes or Pydantic models change, then regenerate the frontend client (below).

### Frontend checks

- `cd frontend && pnpm test` — the CI check; runs `tsc` (typecheck) and
  `prettier --write "**/*.{ts,tsx}"`. There is **no unit test framework** on the frontend despite
  the script name (no eslint in CI either, despite the config existing).
- `pnpm run prettier:check`, `pnpm run typecheck` — individual checks.
- `pnpm build` — production build into `dist/`.
- `pnpm run openapi-ts` — regenerate `src/openapi/` client from
  `backend/openapi/openapi.json` (requires the backend schema to be regenerated first). Never
  hand-edit files in `frontend/src/openapi/`.

### Docs

- `cd docs && pnpm dev` / `pnpm build` / `pnpm test` (prettier + markdownlint).

### Docker / production

- `docker compose up -d` (root `docker-compose.yml`) — quickstart (split): pulls
  `ghcr.io/kounex/bracket-frontend` + `ghcr.io/kounex/bracket-backend` plus Postgres; Caddy
  (`Caddyfile.split`, bind-mounted into the frontend container) serves the app on port 8400 and
  proxies `/api` to the backend.
- Root `Dockerfile` — multi-stage: builds the frontend with pnpm, then a Python image where the
  backend serves both the API and the built frontend from `/app/frontend-dist`.
- Migrations run automatically on app startup when `AUTO_RUN_MIGRATIONS=true`
  (see `backend/bracket/app.py` lifespan); manual migration tooling is Alembic
  (`backend/alembic/`, run from `backend/`). Add a migration whenever `schema.py` changes.

This machine uses **podman** (not Docker): run `podman machine start` first; the Docker API
socket is forwarded automatically, and `podman compose` is a drop-in for `docker compose`.

Deployment modes:

| Mode | Images | Ports | API_PREFIX |
|------|--------|-------|------------|
| Local dev | None | 8400 | "" (empty) |
| Docker combined | `ghcr.io/evroon/bracket` | 8400 | /api |
| Docker split | `-backend` + `-frontend` | 8400 (frontend→3000) | /api (proxied by Caddy) |

## API contract (OpenAPI)

OpenAPI-first: the backend generates a JSON spec, the frontend generates TypeScript types from
it. The generated SDK functions exist but are NOT used — only types are consumed.

When changing backend routes, request/response models, or Pydantic types:

1. Edit backend routes/models (set `response_model=`, define Body types, etc.)
2. `cd backend && uv run ./cli.py generate-openapi`
3. `cd frontend && pnpm openapi-ts`
4. Fix any frontend type errors: `pnpm test` (runs tsc + prettier)
5. Commit `backend/openapi/openapi.json` AND `frontend/src/openapi/**` together

`backend/cli.py` calls `app.openapi()` → writes `backend/openapi/openapi.json`. A monkey-patch
in `backend/openapi/openapi.py` forces all Pydantic fields as required in the spec (avoids
optional/null union types in generated TS). CI enforces freshness via `test_openapi_up_to_date`
in pytest.

Frontend type generation is configured in `frontend/openapi-ts.config.js` using
`@hey-api/openapi-ts`. Generated files (do NOT edit): `types.gen.ts` (all domain types),
`sdk.gen.ts` (typed API functions, not used in app code), `client.gen.ts` + `client/` (Axios
client infra, not used).

Frontend usage convention: import types via `import { Tournament } from '@openapi'`; make HTTP
calls with `createAxios()` from `@services/adapter` (reads) and `@services/{entity}` (writes).
Do NOT use generated SDK functions or create duplicate hand-written types.

API prefix: local dev uses `API_PREFIX=""` (paths like `/tournaments`); Docker deployments use
`API_PREFIX=/api` (paths like `/api/tournaments`) — in split mode the frontend's Caddy proxies
`/api/*` to the backend. The frontend `VITE_API_BASE_URL` must match.

## Code style guidelines

### Python

- Formatting: **ruff format**, line length **100**, target Python 3.13. Linting: ruff with rule
  sets E, EXE, F, FA, FIX, I, ISC, PGH, PIE, PLE, PLW, RUF100, T20, TCH, TD, TID, UP, W
  (see `[tool.ruff]` in `backend/pyproject.toml`). Run `ruff format` + `ruff check --fix` before
  committing.
- Typing: **strict mypy** (`disallow_untyped_defs`, `no_implicit_optional`, `warn_return_any`,
  pydantic plugin enabled) plus **pyrefly**. All new functions must be fully type-annotated.
- pylint also runs in CI with a specific disabled-checks list in `pyproject.toml`; vulture must
  not flag new dead code.
- Architecture layering: HTTP handling in `routes/` → business rules in `logic/` → queries in
  `sql/` → tables in `schema.py` → Pydantic models in `models/`. Keep new code in the right layer
  rather than mixing concerns. Never import `routes/` from `logic/` or `sql/`.
- Datetimes use `heliclockter` (timezone-aware); IDs are `BigInteger` in the DB.
- ID types are branded `NewType` aliases (`utils/id_types.py`, e.g. `TournamentId`, `TeamId`).
- Every router must set `prefix=config.api_prefix`; `app.py` asserts this at startup.
- Response wrappers (`routes/models.py`): `SuccessResponse` for mutations → `{"success": true}`,
  `XxxResponse(data=...)` (a `DataResponse[T]` subclass) for reads → `{"data": ...}`.
- Detailed backend conventions: see `backend/AGENTS.md`.

### TypeScript / frontend

- Prettier (default config: 100 width, single quotes, trailing commas,
  `prettier-plugin-organize-imports`) enforced on all `*.ts`/`*.tsx`; `pnpm test` auto-formats.
- ESLint config: `eslint-config-mantine` + airbnb presets (`.eslintrc.js`).
- API access goes through the generated client in `src/openapi/` wrapped by per-resource
  functions in `src/services/`; UI text goes through i18next (`react-i18next`), translations live
  in `public/locales/<lang>/` and are managed via Crowdin — edit English (`en`) only unless you
  are intentionally translating.
- Detailed frontend conventions: see `frontend/AGENTS.md`.

## Testing instructions

- Backend test files end in `_test.py` and live under `backend/tests/unit_tests/` (pure logic,
  e.g. scheduling/ranking algorithms) and `backend/tests/integration_tests/api/` (HTTP-level API
  tests using an authenticated client fixture from `tests/integration_tests/conftest.py`).
- pytest runs in `asyncio_mode = auto` with pytest-asyncio; warnings are errors except for an
  explicit ignore-list in `pyproject.toml`.
- Integration tests: marker `@pytest.mark.asyncio(loop_scope="session")`; fixtures
  `reinit_database` (session), `auth_context` (session), `startup_and_shutdown_uvicorn_server`
  (module); helpers `send_auth_request()`, `send_tournament_request()`, `send_request()`; use the
  `HTTPMethod` enum, not raw strings; assert full JSON payloads including the `data` wrapper;
  test data via `inserted_*` async context managers and `DUMMY_*` records.
- Unit tests: no HTTP server — construct Pydantic models directly with `DUMMY_*` fixtures and
  negative IDs for isolation. `test_openapi_up_to_date` enforces spec freshness.
- Integration tests require the CI Postgres (see above); the schema is dropped/recreated per
  session, so **never point `ENVIRONMENT=CI` at a database containing real data**.
- Add tests for new backend behavior: unit tests for pure logic, integration tests for new or
  changed endpoints.
- Frontend has no runtime/component tests — `pnpm test` is typecheck + prettier only.
- Coverage is uploaded to Codecov from CI (`codecov.yml`).

## Local CI verification

Before pushing to `dev`/`master` or tagging a release, run **all** CI checks locally and confirm
they pass. Never push if any check fails — fix issues locally, re-run all checks, then push once.

Backend (from `backend/`):

```bash
uv run ruff format --check .
uv run ruff check .
uv run pylint bracket tests cli.py
uv run mypy .
uv run pyrefly check
! uv run vulture | grep "unused function\|unused class\|unused method"
```

Tests require a Postgres instance matching `ci.env` (port 5532, user/pass/db `bracket_ci`):

```bash
podman run -d --name bracket_ci_postgres \
  -e POSTGRES_USER=bracket_ci -e POSTGRES_PASSWORD=bracket_ci \
  -e POSTGRES_DB=bracket_ci -p 5532:5432 postgres:latest
ENVIRONMENT=CI uv run pytest --cov .
podman stop bracket_ci_postgres && podman rm bracket_ci_postgres
```

Frontend (from `frontend/`): `pnpm i && pnpm test`

Docs (from `docs/`): `pnpm i --ignore-scripts && pnpm test-check && pnpm build`

The docker workflow (image build/publish) cannot be replicated locally but is unaffected by
code-only changes.

## Git workflow and releases

Branches:

- `dev` — active development branch, all code changes happen here
- `master` — production branch, always reflects the latest release; tracks `upstream`
  (https://github.com/evroon/bracket.git)

Remotes: `origin` is the fork (github.com/Kounex/bracket); never push to `upstream`.

Release process:

1. Commit all changes on `dev`
2. Tag the release: `git tag vX.Y.Z`
3. Push `dev` with tags: `git push origin dev --tags`
4. Merge `dev` into `master`: `git checkout master && git merge dev --no-edit`
5. Push master: `git push origin master`
6. Switch back to dev: `git checkout dev`

The tag push triggers GitHub Actions to build and push container images. There is an agent skill
for this flow in `.agents/skills/release-version/`.

## CI / CD and deployment

- GitHub Actions in `.github/workflows/`:
  - `backend.yml` — pytest + mypy + pyrefly + pylint + ruff + vulture on every PR/push to master.
  - `frontend.yml` — `pnpm i` + `pnpm test` (tsc + prettier).
  - `docs-build.yml` — docs build checks (paths: `docs/**`).
  - `docker-build.yml` — builds all 3 Dockerfiles on PRs (no push).
  - `docker-publish.yml` — tags matching `v*` trigger GHCR publish of the frontend and backend
    images (parallel matrix jobs, GHA build cache, linux/amd64 + linux/arm64). The combined image
    (root `Dockerfile`) is not published by this workflow.
- Releases are cut by pushing a `v*` tag (see "Git workflow and releases"); production runs from
  the published Docker image (see `docker-compose.yml` and the deployment docs in
  `docs/content/deployment`).

## Security considerations

- `JWT_SECRET` and `ADMIN_PASSWORD` must be set via environment in production; the committed
  defaults in `DevelopmentConfig` are for local development only. Never commit real secrets or
  `prod.env`/`dev.env`/`demo.env` (they are gitignored).
- Auth is JWT-based (access tokens), passwords hashed with bcrypt via passlib; SSO is supported
  through fastapi-sso (`ALLOW_INSECURE_HTTP_SSO` must stay false outside development).
- User registration and captcha are configurable (`ALLOW_USER_REGISTRATION`, `CAPTCHA_SECRET`
  with hCaptcha on the frontend).
- CORS is wide open (`*`) by default; set `CORS_ORIGINS` in production (the app logs a warning
  otherwise).
- Sentry is opt-in via `SENTRY_DSN`.
- Report vulnerabilities via GitHub's private vulnerability reporting (see `SECURITY.md`).
- License is **AGPL-v3.0** — all contributions fall under it (see `LICENSE`, README).
