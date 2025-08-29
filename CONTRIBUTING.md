# Contributing to ScoreMateServer

Thank you for helping improve ScoreMateServer! This guide outlines how to set up, code, test, and submit changes.

## Quick Start
- Prereqs: Docker (and Docker Compose), Node 18+, npm.
- Env: copy `.env.example` to `.env` and fill values (DB/Redis/MinIO/JWT). Never commit secrets.
- Run stack: `npm run dev` (or detached: `npm run dev:detached`).
- Verify: API `http://localhost:8000`, Frontend `http://localhost:3000`, MinIO `http://localhost:9001`.

## Branching & Commits
- Branch names: `feature/<short-scope>` or `fix/<issue|scope>` (e.g., `feature/bulk-tag-ops`).
- Commits: imperative and scoped (e.g., `feat: add setlist statistics`, `fix: thumbnail URL generation`). Keep changes focused and descriptive.

## Coding Standards
- Follow Repository Guidelines in `AGENTS.md` (project layout, commands, style, tests).
- Backend: Python (Django, DRF, Celery), ruff for lint. 4-space indent, `snake_case` functions, `PascalCase` classes.
- Frontend: Next.js (TypeScript). `next lint`, `PascalCase` components, hooks start with `use`.

## Tests & Lint
- Backend tests: `npm run test:backend` (coverage: `npm run test:backend:coverage`).
- Frontend E2E: `npm run test:frontend` (headed: `npm --workspace frontend run test:headed`).
- Lint: `npm run lint:backend` and `npm run lint:frontend`.
- PRs must pass lint and tests. Add/adjust tests with your changes.

## Pull Requests
- Include: problem statement, solution overview, linked issues (`Closes #123`), screenshots/GIFs for UI, and verification steps.
- Note any env/config changes and data migrations. Keep PRs small and reviewable.

## Useful Docker Commands
- Logs: `npm run logs` (or `npm run logs:backend`, `npm run logs:frontend`).
- Migrations: `docker-compose exec web python manage.py migrate`.
- Superuser: `docker-compose exec web python manage.py createsuperuser`.

For architecture details, see `ARCHITECTURE.md`. Thanks for contributing!
