# ScoreMateServer — ARCHITECTURE.md

_Last updated: 2026-09-26 (Asia/Seoul). Plan of record: `devlog/20260926_054_악보공유_및_TV클라이언트_계획.md`._

## 0) Purpose & Scope
ScoreMateServer is the **server-side** for ScoreMate. Since 2026-09 its purpose is **sharing scores inside an ensemble**:
a leader uploads scores and parts, and they are delivered automatically to members' Google TVs (MrgqPdfViewer client).

The server covers:
- **Accounts & Auth** (email/password JWT; Google login later)
- **File storage** for sheet-music PDFs (S3/MinIO today → VM disk on deploy)
- **Library & Setlists** (CRUD, tags, metadata)
- **Ensembles** (members, roles, invites) — _planned S1_
- **Score versions** (frequent revisions) — _planned S2_
- **TV device linking** (RFC 8628 code + QR) — _planned S3_
- **Incremental sync API** for TVs — _planned S4_
- **Processing** (page count, thumbnails)
- **Plans/Quota/Referral**, **Admin**

> Real-time rehearsal sync (beat / bar / page turns) is **not a server feature** — TVs sync with each other on the LAN.

History: the 2025-08 MVP was a private personal library with "no server-side sharing". That principle is replaced below.

---

## 1) System Principles
- **Scoped access**: personal scores are visible only to their owner; ensemble scores only to that ensemble's members. **No public links or public libraries** (arrangements are copyrighted works).
- **Server out of the real-time path**: no WebSocket rooms, no page-turn fan-out.
- **Small footprint**: one container, SQLite, local disk — sized for small ensembles on a shared VM.
- **Portable code**: must run on SQLite; Postgres remains possible via `DATABASE_URL`, but no Postgres-only features.
- **Files never pass through Django**: presigned URLs, or nginx `X-Accel-Redirect` after a Django permission check.
- **Idempotent processing**: tasks are safe to retry and can run in-request.

---

## 2) High-Level Architecture

### Target (S5, dolfinid)
```
 Google TV (MrgqPdfViewer)      Phone / PC browser
   device JWT                     user JWT, /activate
          \                         /
           v                       v
 +-----------------------------------------------+
 | VM nginx (TLS, scoremate.noematica.kr)        |
 |  - static Next.js export                      |
 |  - /api → 127.0.0.1:8016                      |
 |  - X-Accel-Redirect → /srv/scoremate/files    |
 +----------------------+------------------------+
                        v
 +-----------------------------------------------+
 | scoremateserver container (Gunicorn, Django)  |
 |  auth · ensembles · scores/versions · devices |
 |  sync API · in-request PDF processing         |
 +----------+-----------------------+------------+
            v                       v
   /srv/scoremate/data/db.sqlite3   /srv/scoremate/files/
```

### Today (development)
- Django API with SQLite by default (`DATA_DIR/db.sqlite3`), Postgres if `DATABASE_URL` is set.
- Celery task code: runs eagerly in the request when `REDIS_URL` is unset; broker + worker when set.
- MinIO/S3 through boto3 presigned URLs.
- `docker-compose.yml` still offers the full legacy stack (Postgres, Redis, worker, MinIO, frontend, nginx).

---

## 3) Data Model

### Existing
- **User**(email, plan, total_quota_mb, used_quota_mb, referral_code, …)
- **Score**(user, title, original_filename, composer, instrumentation, pages, s3_key, size_bytes, mime, thumbnail_key, tags (JSON list), note, content_hash, created_at, updated_at)
- **Setlist**(user, title, description) / **SetlistItem**(setlist, score, order_index, notes)
- **Task**(user, score, kind, status, try_count, celery_task_id, log, result_json, error_message, …)
- **ReferralLog**, **BillingLog**, **AccessLog**

### Planned additions
```
Ensemble            name, created_by, created_at                                         (S1)
Membership          ensemble, user, role(owner|leader|member), part, joined_at; unique(ensemble,user)
Invite              ensemble, code, created_by, expires_at, max_uses, uses
Score (+)           ensemble (null = personal), part_name                                  (S1)
                    current_version, deleted_at (soft delete for sync)                     (S2/S4)
ScoreVersion        score, number, s3_key, size_bytes, pages, content_hash, uploaded_by, note  (S2)
Setlist (+)         ensemble (null = personal)
Device              uuid, user, name, model, app_version, last_seen_at, revoked_at          (S3)
DeviceAuthorization device_code (hashed), user_code ("BCDF-GHJK"), status, user, expires_at, interval
```

### Permissions
| | Read | Write (upload, new version, delete) |
|---|---|---|
| Personal score | owner | owner |
| Ensemble score | ensemble members | ensemble owner / leader |

Quota is charged to the uploader (no ensemble quota for now).

---

## 4) API Surface (`/api/v1/`)

### Existing
- Auth: `auth/register/`, `auth/login/`, `auth/token/refresh/`, `auth/token/verify/`, `user/profile/`, `dashboard/`
- Scores: `scores/` (list/search/filter, CRUD, bulk operations, tag stats)
- Files: `files/upload-url/`, `files/upload-confirm/`, `files/upload-cancel/`, `files/download-url/`, `files/thumbnail/<key>`
- Setlists: `setlists/` (CRUD, items, ordering)
- Admin: `admin/…`

### Planned
- `ensembles/` — create, members/roles, invite links, join by code (S1)
- Score versions — upload new version with a note, list versions (S2)
- `device/code`, `device/token` (RFC 8628) + web page `/activate`; "my devices" with revoke (S3)
- `sync/scores?cursor=` → `{cursor, scores:[…current version…], deleted:[ids]}`; `scores/{id}/download` → redirect; device heartbeat (S4)

---

## 5) TV Device Linking (S3, RFC 8628)
```
TV  POST device/code {name, model} → device_code, user_code, verification_uri(_complete), interval
TV  shows code + QR
Phone  /activate (login) → confirm code → Device created
TV  POST device/token {device_code} every interval
      → authorization_pending | slow_down | {access, refresh, device_id}
```
- Device refresh tokens are long-lived (~180 days) with a `device_id` claim; revoking a device rejects its refresh.
- `device_code` stored hashed; `user_code` lookups rate-limited; codes expire after 10 minutes.

---

## 6) Sync (S4)
- Scope: my personal scores + scores of ensembles I belong to.
- Cursor = last seen (`updated_at`, id), monotonic; a new version or metadata change bumps `updated_at`.
- First sync without cursor returns everything. Leaving an ensemble reports its scores in `deleted`.
- TVs download files directly (presigned / X-Accel), never through Django.

---

## 7) Storage Layout
```
{user_id}/scores/{score_id}/original.pdf
{user_id}/scores/{score_id}/thumbs/cover.jpg
```
Versions (S2) will get their own keys per version. On deploy the same layout lives under `/srv/scoremate/files/` (`STORAGE_BACKEND=local`, S5).

---

## 8) Processing
- **PDF_INFO**: page count and basic metadata → Score (version).
- **THUMBNAIL**: `cover.jpg`.
- PyMuPDF makes both fast (hundreds of ms), so they run in-request by default. Failures do not fail the upload (`CELERY_TASK_EAGER_PROPAGATES=False`); results are recorded in `Task`.
- Set `REDIS_URL` and run a worker if processing becomes heavy.

---

## 9) Security & Privacy
- Every score query is scoped to owner or ensemble membership; non-members get 404.
- No public links; short-TTL download URLs.
- MIME allowlist, size caps, upload / login / device-code rate limiting.
- Device tokens revocable per device.
- `AccessLog` for significant actions; minimal PII.

---

## 10) Deployment

### Target: dolfinid (GCP VM shared by several projects)
- Image `honestjung/scoremateserver:vX.Y.Z` (linux/amd64) built on the build host; VM runs `/srv/scoremate/` compose bound to `127.0.0.1:8016`.
- VM nginx site `scoremate.noematica.kr` with Let's Encrypt (webroot `/srv/scoremate/acme`).
- SQLite + files bind-mounted; verified backup before deploy; migrate inside the container; roll back `.env` on failure (`deploy.sh`).
- Read-only container, `cap_drop: ALL`, log size limits; Gunicorn ~2 workers × 4 threads.
- `deploy/` follows the hanyang3d convention (`deploy.toml`).

### Legacy / development
`docker-compose.yml` (and `docker-compose.prod.yml`, to be replaced in S5): web, worker, Postgres, Redis, MinIO, frontend, nginx.

---

## 11) Local Development
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate        # SQLite in backend/data/
python manage.py runserver
python -m pytest tests/
```
Or the full stack: `cp .env.example .env && docker-compose up -d` (API :8000, frontend :3000, MinIO console :9001).

### Key Env Vars
```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=*
DATA_DIR=                 # SQLite location (default backend/data)
DATABASE_URL=             # optional (Postgres)
REDIS_URL=                # optional (Celery broker + worker)
STORAGE_ENDPOINT=http://minio:9000
STORAGE_BUCKET=scores
STORAGE_ACCESS_KEY=
STORAGE_SECRET_KEY=
STORAGE_USE_SSL=false
JWT_SIGNING_KEY=
MAX_UPLOAD_MB=200
ALLOWED_MIME=application/pdf
REFERRAL_BONUS_MB=50
```

---

## 12) Directory Layout
```
backend/
  scoremateserver/  # settings, urls, celery
  core/             # auth, users, quota, referral
  scores/           # Score (+ versions, S2)
  setlists/
  files/            # upload/download URL issuance
  tasks/            # pdf_info, thumbnail
  scoremate_admin/  # admin API
  tests/
frontend/           # Next.js (App Router), Playwright E2E
devlog/             # plans and reports
```

---

## 13) Roadmap
| Stage | Content |
|---|---|
| S0 ✅ | Repo cleanup, SQLite default, Celery optional |
| S1 | Ensembles, membership, invites, permissions |
| S2 | Score versions + data migration |
| S3 | TV device linking |
| S4 | Sync API, soft delete, download redirect |
| S5 | dolfinid deployment (single container, local storage, static web) |
| S6 | Google login, setlist sync, shared score analysis |

---

## 14) Non-Goals
- No WebSocket rooms or server-side page-turn broadcasting.
- No public libraries or public share links.
- No AI models embedded in the API container.
