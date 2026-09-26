# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
**ScoreMateServer** - Django REST API backend for ScoreMate sheet music management, being extended (2026-09) into **ensemble score sharing** for Google TV clients (MrgqPdfViewer)
- **Stack**: Python 3.12, Django 5.0, Django REST Framework, SQLite (default) / PostgreSQL (optional), Celery (optional), MinIO/S3 → local disk (planned)
- **Purpose**: User accounts, PDF sheet music storage, library metadata, setlists, page count / thumbnail processing, quota management — and next: ensembles, score versions, TV device linking, incremental sync API
- **Current plan**: `devlog/20260926_054_악보공유_및_TV클라이언트_계획.md` (stages S0–S6). Read it before starting new feature work.

### Direction change (2026-09)
- The 2025-08 MVP was a **private personal library** ("no server-side sharing").
- The new goal: a leader uploads scores / parts to an **ensemble**; they are delivered to members' TVs. Revisions are frequent → **versions**. TVs link via **code + QR** (RFC 8628 device flow).
- New rule: **personal scores are private; ensemble scores are readable by that ensemble's members only.** No public sharing (arrangements are copyrighted works).
- Real-time sync (beat / bar / page) during rehearsal stays **client-to-client on the LAN** — the server is never in the real-time path.

### Status (2026-09-26)
| Stage | Content | Status |
|---|---|---|
| S0 | Repo cleanup, SQLite by default, Celery optional (eager when no `REDIS_URL`) | ✅ |
| S1 | Ensemble · Membership · Invite, `Score.ensemble`, permissions | next |
| S2 | ScoreVersion + data migration, new-version upload | |
| S3 | Device · DeviceAuthorization · `/activate` (RFC 8628) | |
| S4 | Sync API (cursor, soft delete, download redirect) | |
| S5 | Deploy on dolfinid (single container, local file storage, static web) | |
| S6 | (2nd) Google login, setlist sync | |

## Development Commands

### Backend without Docker (default: SQLite, no Redis/worker)
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate            # creates backend/data/db.sqlite3 (DATA_DIR)
python manage.py createsuperuser
python manage.py runserver

# Tests
python -m pytest tests/ -v --tb=short
python -m pytest tests/ --cov=. --cov-report=term-missing
```
- No `DATABASE_URL` → SQLite at `$DATA_DIR/db.sqlite3` (`DATA_DIR` defaults to `backend/data`).
- No `REDIS_URL` → Celery tasks run **eagerly inside the request** (`CELERY_TASK_ALWAYS_EAGER`); task failures do not fail the upload.
- File storage still needs an S3-compatible endpoint (MinIO) until S5 adds `STORAGE_BACKEND=local`.

### Docker Compose (full legacy stack: Postgres, Redis, worker, MinIO, frontend)
```bash
cp .env.example .env
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python -m pytest tests/ -v --tb=short
docker-compose logs -f web worker
```
Note: `scores/migrations/0001_initial.py` was edited in place for the SQLite switch (`tags` ArrayField → JSONField). An existing local Postgres DB must be recreated.

## High-Level Architecture

### Current service layout
- **Django API** (`backend/`): REST endpoints, JWT auth, presigned URL generation
- **DB**: SQLite by default; PostgreSQL via `DATABASE_URL` (no Postgres-only features may be used)
- **Background tasks**: Celery task code (`tasks/`); eager in-process without `REDIS_URL`, broker + worker with it
- **Object storage**: MinIO/S3 via boto3 presigned URLs
- **Web client**: Next.js (`frontend/`)

### Target deployment (S5, dolfinid GCP VM shared with other projects)
- **One container** (Gunicorn) bound to `127.0.0.1:8016`; the VM's nginx proxies `scoremate.noematica.kr` (Let's Encrypt)
- SQLite file + score files on VM disk under `/srv/scoremate/` (bind mount), backed up before each deploy
- Downloads: Django checks permission, nginx sends the file via **`X-Accel-Redirect`**
- Web: `next build` static export served by nginx
- Image `honestjung/scoremateserver:vX.Y.Z` (linux/amd64); `deploy/` follows the hanyang3d convention (`deploy.toml`, `deploy.sh`)

### Key Design Decisions
1. **Access scope**: personal scores → owner only; ensemble scores → members read, owner/leader write. No public links.
2. **Server stays out of real-time sync**: page-turn / beat sync is LAN client-to-client (no WebSocket).
3. **Portable DB**: code must run on SQLite (no `ArrayField`, `ArrayAgg`, Postgres full-text search). `backend/tests/test_sqlite_portability.py` guards this.
4. **Lightweight processing**: page count / thumbnails are fast (PyMuPDF) and may run in-request.
5. **Quota**: counted against the uploader (no ensemble quota for now); always update `used_quota_mb` on file operations.
6. **Files never stream through Django**: presigned URLs now, `X-Accel-Redirect` with local storage later.

### Data Flow Patterns
```
Upload:   Client → Django (presigned URL) → direct to storage → process (eager or Celery)
Download: Client → Django (permission check) → presigned URL / X-Accel-Redirect
TV sync (S4):  TV → GET /api/v1/sync/scores?cursor=… → changed + deleted → download each
```

## Development Process

### Phase-based Development
1. **Planning**: detailed plan in devlog
2. **Implementation**: regular commits
3. **Testing**: factory_boy + pytest
4. **Review**: code review and documentation update
5. **Completion**: report and next stage preparation

### Documentation Standards
All progress is documented in `devlog/` as `YYYYMMDD_###_<title_in_korean>.md` with a sequence number continuing from the highest existing one (check the directory first).

- **Planning Document**: implementation plan and architecture decisions
- **Progress Reports**: development updates and issue resolutions
- **Testing Report**: tests, coverage, bug fixes
- **Completion Report**: summary, achievements, next steps

### Quality Gates
Before moving to the next stage:
1. ✅ All implemented features fully tested
2. ✅ Coverage >90% on business logic
3. ✅ All tests passing
4. ✅ Documentation updated (CLAUDE.md, ARCHITECTURE.md, devlog/)
5. ✅ Completion report written

## Directory Structure
```
backend/
  scoremateserver/   # settings (env vars), urls, celery
  core/              # auth, users, quota, referrals
  scores/            # Score model, metadata, tags, CRUD
  setlists/          # Setlist and SetlistItem
  files/             # presigned URL generation
  tasks/             # task definitions (pdf_info, thumbnail)
  scoremate_admin/   # admin API
  tests/             # pytest suite (centralized)
frontend/            # Next.js app, Playwright E2E
nginx/               # legacy proxy config (compose)
devlog/              # development logs and plans
```

## API Endpoint Structure
RESTful, DRF ViewSets where appropriate.

### Authentication
- JWT via `djangorestframework-simplejwt`; all endpoints except auth require `Bearer` token
- Token lifetime: 60 min access, 1 day refresh (device tokens in S3 will get a long refresh + `device_id` claim)

### Main Endpoints
All under `/api/v1/`:
- `auth/register/`, `auth/login/`, `auth/token/refresh/`, `auth/token/verify/`, `user/profile/`, `dashboard/`
- `scores/` - score CRUD, search, tagging, bulk operations
- `setlists/` - setlist management
- `files/` - `upload-url/`, `upload-confirm/`, `upload-cancel/`, `download-url/`, `thumbnail/…`
- `admin/` - admin API (`scoremate_admin`)
- Planned: `ensembles/` (S1), score versions (S2), `device/` + web `/activate` (S3), `sync/` (S4)

## Environment Configuration
See `.env.example`:
- `DATA_DIR`: directory for the SQLite file (default `backend/data`)
- `DATABASE_URL`: optional; e.g. Postgres for the compose stack
- `REDIS_URL`: optional; when set, tasks go through the broker to a worker
- `STORAGE_*`: MinIO/S3 configuration
- `JWT_SIGNING_KEY`, `MAX_UPLOAD_MB`, `ALLOWED_MIME` (default `application/pdf`)

## Testing Strategy
- **pytest + pytest-django**, centralized in `backend/tests/`, **factory_boy** factories in `tests/factories.py`
- Tests run on SQLite by default (same as production)
- Mock S3 operations; tasks run eagerly without `REDIS_URL`
- Use `@pytest.mark.django_db` for database access

```python
user = UserFactory(email="test@example.com", plan="pro")
score = ScoreFactory(user=user, title="Test Score")
setlist = SetlistFactory(user=user)
item = SetlistItemFactory(setlist=setlist, score=score)
```

## Important Constraints
1. **No WebSocket/Realtime**: synchronization happens client-to-client
2. **No public sharing**: scores are visible to their owner, or to members of their ensemble — nobody else
3. **SQLite-compatible code only**: no Postgres-specific fields, aggregates or search
4. **Idempotent tasks**: background jobs must be safely retryable, and must work eagerly in-request
5. **Quota enforcement**: always update `used_quota_mb` on file operations
6. **Files are not streamed through Django**

## Code Conventions
- PEP 8; type hints where beneficial
- DRF serializers for validation, ViewSets for CRUD
- Business logic in models or service modules
- Docstrings for public methods and complex logic
- Always create and review migrations; `db_index=True` on frequently queried fields

## Background Task Patterns
```python
# Tasks should be idempotent and atomic
@shared_task(bind=True, max_retries=3)
def process_pdf(self, score_id):
    try:
        ...
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

## Security Considerations
- Every score query must be scoped: own scores, or scores of ensembles the user belongs to
- Presigned URLs with short TTL (5-15 minutes)
- Validate MIME types and file sizes before upload
- Never expose storage credentials to clients
- Rate limit login and device-code lookups; store device codes hashed (S3)
- Sanitize user input in metadata fields
