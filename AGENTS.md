# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: Django 5 REST API and Celery worker. Apps live under `scores/`, `setlists/`, `tasks/`, with project config in `scoremateserver/`. Tests are in `backend/tests/` (pytest).
- `frontend/`: Next.js app (TypeScript, App Router). Key folders: `app/`, `components/`, `hooks/`, `tests/e2e/` (Playwright).
- Root: `docker-compose.yml` (local stack: Postgres, Redis, MinIO, web, worker, frontend), `.env*` for configuration, `ARCHITECTURE.md` for a deeper overview, `nginx/` for optional proxy.

## Build, Test, and Development Commands
- Start full dev stack: `npm run dev` (or detached: `npm run dev:detached`).
- Backend only: `npm run dev:backend` (web, worker, db, cache, storage).
- Frontend only: `npm run dev:frontend` (or local install: `npm run dev:frontend:local`).
- Build: `npm run build:frontend` (Next.js) and `npm run build:backend` (Docker images).
- Test: `npm test` (all), `npm run test:backend` (pytest), `npm run test:backend:coverage`, `npm run test:frontend` (Playwright).
- Lint: `npm run lint:backend` (ruff), `npm run lint:frontend` (eslint via `next lint`).
- Utilities: `npm run logs`, `npm run stop`, `npm run clean`.

## Coding Style & Naming Conventions
- Python (backend): 4‑space indent; ruff enforced (`npm run lint:backend`). Use `snake_case` for modules/functions, `PascalCase` for classes. Django apps keep serializers/views/urls in their app folders.
- TypeScript/React (frontend): ESLint via `next lint`. Components `PascalCase` (e.g., `MetadataEditForm.tsx`), hooks `camelCase` starting with `use` (e.g., `useScores.ts`). Prefer module‑scoped utilities in `lib/` and colocate small helpers.
- Filenames: backend tests `test_*.py`; Playwright specs `*.spec.ts` in `frontend/tests/e2e/`.

## Testing Guidelines
- Backend: `pytest` with config in `backend/pytest.ini`. Run via `npm run test:backend`; add coverage checks with `npm run test:backend:coverage`. Write focused unit tests per app and API tests under `backend/tests/`.
- Frontend: Playwright E2E in `frontend/tests/e2e/`. Run headless `npm run test:frontend` or `npm run test:headed`; open report with `npm --workspace frontend run test:report`.
- Aim to add/adjust tests for every feature/bugfix and keep deterministic seeds/fixtures.

## Commit & Pull Request Guidelines
- Commits: Use imperative mood and concise scope (e.g., `feat: bulk tag operations`, `fix: download URL for thumbnails`). Group related changes; avoid noisy formatting‑only commits.
- PRs: Include summary, linked issues (e.g., `Closes #123`), screenshots/GIFs for UI, reproduction/verification steps, and notes on env/config changes. Keep PRs focused and passing lint/tests.

## Security & Configuration Tips
- Copy `.env.example` to `.env` for local dev; never commit secrets. Key vars: DB/Redis URLs, MinIO creds, `JWT_SIGNING_KEY`, `NEXT_PUBLIC_API_URL`.
- Use `docker-compose logs -f` to verify services (web 8000, frontend 3000, MinIO 9000/9001) before test runs.

