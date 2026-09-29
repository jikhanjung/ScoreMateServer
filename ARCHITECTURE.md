# ScoreMateServer — ARCHITECTURE.md

_Last updated: 2026-09-28 (Asia/Seoul). In production: https://scoremate.noematica.kr (web + API, 0.10.2). Plan of record: `devlog/20260926_054_악보공유_및_TV클라이언트_계획.md`; score recognition: `devlog/20260928_P01_…`. Handoff: `HANDOFF.md`._

## 0) Purpose & Scope
ScoreMateServer is the **server-side** for ScoreMate. Since 2026-09 its purpose is **sharing scores inside an ensemble**:
a leader uploads scores and parts, and they are delivered automatically to members' Google TVs (MrgqPdfViewer client).

The server covers:
- **Accounts & Auth** (email/password JWT; Google login later)
- **File storage** for sheet-music PDFs (S3/MinIO today → VM disk on deploy)
- **Library & Setlists** (CRUD, tags, metadata)
- **Ensembles** (members, roles, invites) — S1 ✅ (server)
- **Score versions** (frequent revisions) — S2 ✅
- **TV device linking** (RFC 8628 code + QR) — S3 ✅
- **Incremental sync API** for TVs — S4 ✅
- **Processing** (page count, thumbnails, per-page images on demand)
- **Score recognition (OMR)**: PDF → MusicXML on a host cron lane (Codex CLI `gpt-6-astra`) — devlog 064 · 069
- **Score layout**: staves · systems · measures · time signatures from the PDF, the TV app's Kotlin analysis ported — devlog 068
- **Web viewing**: page view (fit width/height, 1/2 pages), listening from MusicXML with page follow — devlog 067
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

### Production (S5, dolfinid — live since 0.1.0)
```
 Google TV (MrgqPdfViewer)      Phone / PC browser
   device JWT                     user JWT, /activate
          \                         /
           v                       v
 +-----------------------------------------------+
 | VM nginx (TLS, scoremate.noematica.kr)        |
 |  - web: Django templates (same container)     |
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
   /srv/scoremate/db/db.sqlite3     /srv/scoremate/files/
                                     ^
 host cron (outside the container)   |  results written back via manage.py
  */5  score_pipeline.sh  per version: ① manage.py score_layout (PDF analysis) → ② model_layout.py (model reads layout)
                          → ③ astra_musicxml.py (PDF → MusicXML); one page at a time, shortest score first (devlog 072)
  hourly backup_db.py · daily offsite pull (m710q) incl. files/
```

### Development
- Django API with SQLite by default (`DATA_DIR/db.sqlite3`), Postgres if `DATABASE_URL` is set.
- Celery task code: runs eagerly in the request when `REDIS_URL` is unset; broker + worker when set.
- Storage: MinIO/S3 presigned URLs (`STORAGE_BACKEND=s3`), or `local` like production.
- Web: Django templates in `backend/web/` (session auth). `frontend/` (Next.js) is legacy and not deployed.
- `docker-compose.yml` still offers the full legacy stack (Postgres, Redis, worker, MinIO, frontend, nginx).

---

## 3) Data Model

### Existing
- **User**(email (login), username, plan = grade (solo|pro|enterprise), total_quota_mb, used_quota_mb (float MB), is_superuser (= is_staff), is_active, referral_code, …)
- **Score**(user, title, original_filename, composer, arranger (0.9.0), instrumentation, pages, s3_key, size_bytes, mime, thumbnail_key, tags (JSON list), note, content_hash, created_at, updated_at)
- **Setlist**(user, title, description) / **SetlistItem**(setlist, score, order_index, notes)
- **Task**(user, score, kind, status, try_count, celery_task_id, log, result_json, error_message, …)
- **ReferralLog**, **BillingLog**, **AccessLog**

### Added in S1 (`ensembles` app)
```
Ensemble            name, description, created_by, created_at, updated_at
Membership          ensemble, user, role(owner|leader|member), part, joined_at; unique(ensemble,user)
Invite              ensemble, code, created_by, expires_at, max_uses, uses, revoked_at
Score (+)           ensemble (null = personal, SET_NULL on ensemble delete), part_name
```

### Added in S6
```
Setlist (+)         ensemble (null = personal; CASCADE with the ensemble)
ScoreAnalysis       version, analyzer, analyzer_version, data (JSON), uploaded_by, device; unique(version, analyzer)
                      analyzers: astra-musicxml (OMR, file omr/v{N}.musicxml) · score-layout (file layout/v{N}.json) · TV uploads
SocialAccount       user, provider (google), subject (OIDC sub), email
```

### Added in S3 (`devices` app)
```
Device              uuid, user, name, model, app_version, last_seen_at, last_synced_at, revoked_at
DeviceSetlist       device, setlist, added_at — a device receives only the scores of its chosen setlists (sync_mode removed in 0.8.2)
DeviceAuthorization device_code_hash, user_code ("BCDF-GHJK"), status, device, user, interval, expires_at
```

### Added in S2
```
ScoreVersion        score, number, s3_key, original_filename, size_bytes, mime, pages, content_hash, uploaded_by, note
Score (+)           current_version (file fields mirror it), last_version_number (numbers never reused)
```

### Permissions
| | Read | Write (upload, new version, delete) |
|---|---|---|
| Personal score | owner | owner |
| Ensemble score | ensemble members | ensemble owner / leader |

Quota is charged to the uploader (no ensemble quota for now).

Implemented as `Score.objects.readable_by(user)` / `writable_by(user)`; every score lookup (viewset, bulk actions, downloads) goes through one of them. Non-members get 404, members attempting writes get 403. Role changes: owner only; at least one owner must remain.

### Service-wide roles and grades (devlog 075)
- **Administrator** = `is_superuser` (kept equal to `is_staff`, so `/admin/` works too). Only administrators manage users: web `/manage/users/` and `/api/v1/admin/users/`.
- Actions: add a user (works while `REGISTRATION_OPEN=false`), change grade / quota limit, grant/remove admin, set a password, deactivate.
- **Grade** = `User.plan`; `settings.USER_GRADES` maps it to a label and a default quota (200 / 1000 / 5000 MB, env `GRADE_*_MB`). Changing the grade applies its default quota unless a limit is given. Grades only set quota for now.
- Guards: no removing your own admin role, no deactivating yourself, at least one active administrator remains.
- Deactivated users: web session ends, login fails, user and device JWTs (access and refresh) are rejected; their data stays.
- Rules live in `core/services.py` (`update_user`, `create_user`, `set_password`), used by both the web and the admin API.

---

## 4) API Surface (`/api/v1/`)

### Existing
- Auth: `auth/register/`, `auth/login/`, `auth/token/refresh/`, `auth/token/verify/`, `user/profile/`, `dashboard/`
- Scores: `scores/` (list/search/filter, CRUD, bulk operations, tag stats)
- Files: `files/upload-url/`, `files/upload-confirm/`, `files/upload-cancel/`, `files/download-url/`, `files/thumbnail/<key>`
- Setlists: `setlists/` (CRUD, items, ordering)
- Admin (superuser only): `admin/users/` (list, `POST` add, `PATCH` grade/quota/admin/active, `POST {id}/reset_password/`), `admin/scores/`, `admin/setlists/`, `admin/tasks/`
- Ensembles (S1): `ensembles/`, `ensembles/{id}/members/{user_id}/`, `ensembles/{id}/invites/[{invite_id}/]`, `ensembles/invite/{code}/` (preview), `ensembles/join/`
- Scores accept/return `ensemble`, `part_name`, `version`, `version_count`; filter `?ensemble=<id>|personal`
- S6 ✅: `sync/setlists/`; `scores/{id}/analysis/` (PUT requires the version's sha256; members replace only with a newer analyzer); web `/setlists/`, Google login `/auth/google/`
- Sync (S4 ✅): `sync/scores/?cursor=` → `{cursor, has_more, scores, ids}` (TV drops local scores not in `ids`); `scores/{id}/download/` → 302; `devices/me/heartbeat/`
- TV linking (S3 ✅): `device/code`, `device/token` (RFC 8628 errors), `devices/` (list · rename · revoke), `devices/me/`; web `/activate/`, `/devices/` ("연결 기기")
- Score versions (S2 ✅): `scores/{id}/versions/` (list · new version), `versions/{n}/` (delete), `versions/{n}/make_current/`
- Recognition results: `scores/{id}/musicxml/` and `scores/{id}/layout/` (`?version=n`) → 302 to a signed URL; sync entries carry
  `musicxml {url, sha256, size_bytes, filename, parts, measures, updated_at}` and
  `layout {url, sha256, size_bytes, filename, analyzer_version, pdf_sha256, measures, systems, updated_at}` (null when absent)
- Web: `/scores/{id}/pages/{n}/?size=thumb|view` (page image, rendered once, cached per version), `/scores/{id}/versions/{n}/musicxml/[parts/]`

---

## 5) TV Device Linking (S3 ✅, RFC 8628) — details and client contract: devlog 059
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

## 6) Sync (S4 ✅ — client contract: devlog 060)
- Scope: user tokens — my personal scores + scores of ensembles I belong to. **Device tokens — only the scores of the setlists chosen for that device** on the web.
- Cursor = last seen (`updated_at`, id), monotonic; a new version or metadata change bumps `updated_at`.
- First sync without cursor returns everything. Instead of a `deleted` list (and soft delete), every response carries `ids` — all scores readable now; the TV deletes anything else. This covers delete, leave, kick, ensemble delete and moves alike.
- Effective time = max(updated_at, my join time for that ensemble), so joining brings old scores; recent changes wait `SYNC_LAG_SECONDS` so late commits are not skipped.
- TVs download files directly (presigned / X-Accel), never through Django.

---

## 7) Storage Layout
```
{user_id}/uploads/{uuid}/original.pdf                 # each version's PDF
{user_id}/scores/{score_id}/thumbs/cover.jpg
{user_id}/scores/{score_id}/pages/{sha16}/{thumb|view}-{n:04d}.jpg   # page images, on first view
{user_id}/scores/{score_id}/omr/v{N}.musicxml           # recognition result
{user_id}/scores/{score_id}/layout/v{N}.json            # staves/measures analysis (TV app ScoreLayout shape)
```
Production: `/srv/scoremate/files/` (`STORAGE_BACKEND=local`), served by nginx X-Accel after a Django permission check.
All of it is inside `files/`, so the daily offsite backup (m710q rsync + hardlink snapshots + NAS) covers PDFs and results.

---

## 8) Processing
- **PDF_INFO**: page count and basic metadata → Score (version).
- **THUMBNAIL**: `cover.jpg`.
- PyMuPDF makes both fast (hundreds of ms), so they run in-request by default. Failures do not fail the upload (`CELERY_TASK_EAGER_PROPAGATES=False`); results are recorded in `Task`.
- Set `REDIS_URL` and run a worker if processing becomes heavy.
- **Page images**: rendered on first view (PyMuPDF, 0.02 s thumb / 0.2 s view), cached per version.
- **Score layout** (host cron → `manage.py score_layout`): `scores/score_layout.py` is the TV app's Kotlin `score/` ported line by line
  (golden test + 64 app unit tests); `analyzer_version = SERVER_REVISION + app.<commit>` — bumping it re-analyzes every version.
- **Recognition (OMR)** (host cron → `scripts/astra_musicxml.py`): one page per Codex CLI call, the model writes a compact text form
  (`scripts/omr_compact.py` builds MusicXML), checks per page (well-formed, beat sums, part list, key signature vs a separate read,
  staves = layout's staves per system); failures are retried once, two-page chunks split. Needs the layout analysis first.

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
- `deploy/` follows the fcmanager convention (`deploy.toml`); host scripts are extracted from the image on deploy.
- Host cron: `scripts/score_pipeline.sh` (5 min, flock; needs `codex login --device-auth` on the host and `omr/venv`).
  See `deploy/README.md` §악보 처리 파이프라인.

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
  ensembles/        # ensembles, memberships, invites
  devices/          # TV/tablet linking (RFC 8628), per-device setlists
  web/              # Django templates (session auth), static player.js
  scores/           # Score + versions; omr.py (recognition), layouts.py + score_layout.py (staves/measures), pages.py
  scripts/          # host-side: backup_db.py, astra_musicxml.py, omr_compact.py (shipped in the image)
  setlists/
  files/            # upload/download URL issuance
  tasks/            # pdf_info, thumbnail
  scoremate_admin/  # admin API
  tests/
deploy/             # image build, host scripts (deploy.sh, omr_lane.sh, layout_lane.sh, …)
frontend/           # Next.js — legacy, not deployed
devlog/             # plans and reports
```

---

## 13) Roadmap
| Stage | Content |
|---|---|
| S0 ✅ | Repo cleanup, SQLite default, Celery optional |
| S1 ✅ | Ensembles, membership, invites, permissions (web screens pending) |
| S2 ✅ | Score versions + data migration (devlog 058) |
| S3 ✅ | TV device linking (devlog 059) |
| S4 ✅ | Sync API (ids set, no soft delete), download redirect (devlog 060) |
| S5 ✅ | dolfinid deployment — API only (done before S2), devlog 056 |
| Web ✅ | Django templates — login, scores, upload, ensembles/invites, join links (devlog 057) |
| S6 ✅ | Ensemble setlists + sync, shared score analysis, Google login (devlog 061) |
| — ✅ | Per-device setlists, "연결 기기" (devlog 062, 065) |
| — ✅ | Metadata: arranger, PDF title, suggestions (devlog 066) |
| — ✅ | Page view, fit width/height, 1/2 pages, listening with page follow (devlog 067) |
| — ✅ | Score layout files — TV app analysis ported (devlog 068) |
| — ✅ | Recognition lane PDF → MusicXML, all current scores done (devlog 064, 069) |
| next | Work-level ensemble play & parts (P01 §3), scanned scores, pitch review |

---

## 14) Non-Goals
- No WebSocket rooms or server-side page-turn broadcasting.
- No public libraries or public share links.
- No AI models embedded in the API container — recognition runs on the host through the Codex CLI and only its result files come back.
