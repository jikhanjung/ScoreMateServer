
# ScoreMateServer — ARCHITECTURE.md (MVP)

_Last updated: 2025-08-19 (Asia/Seoul)_

## 0) Purpose & Scope
ScoreMateServer is the **server-side** for ScoreMate. It **excludes page‑turn sync** (handled client‑to‑client). The server focuses on:
- **Accounts & Auth** (email/password; OAuth later)
- **File storage** for sheet‑music PDFs (S3/MinIO)
- **Library & Setlists** (CRUD, tags, metadata)
- **Background processing** (page count, thumbnails; optional layout/bars hook)
- **Plans/Quota/Referral** (storage limits & bonus capacity)
- **Admin/Observability** (logs, quotas, task monitoring)

> Synchronization of “viewing/turning pages” is **not a server feature**.

---

## 1) System Principles
- **Private by default**: Only the uploader can read their files.
- **Thin and composable**: AI tasks are via async workers; model servers are pluggable.
- **Cost-aware**: S3-compatible object storage + Dockerized stack.
- **Legally cautious**: No server-side sharing; optional opt‑in for model training.
- **Predictable latency**: Background jobs are idempotent; no WS fan-out required.

---

## 2) High-Level Architecture

```
+--------------------------+
|        Clients           |
|  (Android/iOS/TV/Web)    |
+------------+-------------+
             | REST (JWT)
             v
+--------------------------+       +------------------+
|        Django API        |<----->|   Redis (cache)  |
|  DRF, Auth, Quota, CRUD  |       +------------------+
|  Presigned URL issuance  |                 ^
+-------------+------------+                 |
              |                              |
              | Celery/RQ tasks              |
              v                              |
+--------------------------+       +------------------+
|    Worker(s) (Celery)    |------>|  PostgreSQL DB   |
|  PDF_INFO / THUMBNAIL    |       +------------------+
|  LAYOUT_HOOK (optional)  |
+-------------+------------+
              |
              v
+--------------------------+
|    S3/MinIO Object Store |
+--------------------------+

[Reverse proxy: Nginx in front of Django for HTTP TLS/limits]
```

**Out of scope**: WebSocket rooms, ensemble sync, page-turn broadcasting.

---

## 3) Data Model (initial)

### Core
- **User**(id, email, password_hash, plan, total_quota_mb, used_quota_mb, referral_code, created_at)
- **Score**(id, user_id, title, composer, instrumentation, pages, s3_key, size_bytes, mime, thumbnail_key, tags[], note, content_hash, created_at, updated_at)
- **Setlist**(id, user_id, title, description, created_at)
- **SetlistItem**(id, setlist_id, score_id, order_index)

### Operations / Jobs / Billing
- **Task**(id, user_id, score_id, kind[`pdf_info|thumbnail|layout_hook`], status[`PENDING|RUNNING|SUCCEEDED|FAILED`], try_count, log, created_at, updated_at)
- **ReferralLog**(id, user_id, referred_user_id, bonus_mb, created_at)
- **BillingLog**(id, user_id, kind[`plan_change|payment|refund|referral_bonus`], amount, meta_json, created_at)
- **AccessLog**(id, user_id, action, target_type, target_id, meta_json, created_at)

DB: **PostgreSQL**. Tags can be a simple text array or a normalized table if needed later.

---

## 4) API Surface (MVP)

### Auth
- `POST /auth/register` → create user
- `POST /auth/login` → JWT access/refresh
- `POST /auth/logout` → (optional) blacklist refresh

### Scores (Library)
- `GET /scores?query=&tag=&page=` → list/search
- `POST /scores` → create metadata or start upload (see Files below)
- `GET /scores/{id}` → metadata (title, composer, pages, thumbnail URLs)
- `PATCH /scores/{id}` → update metadata/tags/note
- `DELETE /scores/{id}` → delete (DB + object)

### Files (Presigned)
- `POST /files/upload-url` → presigned PUT; validate size/MIME; returns `url`, `headers`, `content_hash_token`  
- `GET /files/download-url?score_id=&page=` → presigned GET (short TTL)

### Setlists
- `GET /setlists`
- `POST /setlists`
- `PATCH /setlists/{id}`
- `POST /setlists/{id}/items` (add/update order)
- `DELETE /setlists/{id}`

### Tasks
- `POST /tasks/refresh-thumbnails?score_id=`
- `POST /tasks/run-layout?score_id=` (optional; async hook)
- `GET /tasks/{task_id}` → status / log

### Billing / Quota / Referral
- `GET /billing/plan`
- `GET /billing/usage`
- `POST /billing/redeem-referral`
- `GET /billing/history`

> **No sync/session APIs** in server (handled entirely on clients).

---

## 5) Object Storage Layout

```
/{user_id}/scores/{score_id}/original.pdf
/{user_id}/scores/{score_id}/thumbs/page-0001.jpg
/{user_id}/scores/{score_id}/thumbs/cover.jpg
```
- Access via short‑lived presigned URLs only.
- `content_hash` detects duplicate uploads (optional hard‑linking at object layer).

---

## 6) Background Jobs

- **PDF_INFO**: Read page count, page sizes, basic metadata; persist to Score.
- **THUMBNAIL**: Generate `cover.jpg` (and optional per‑page thumbs later).
- **LAYOUT_HOOK (optional)**: Call external service for layout/bars detection; store JSON result (non‑blocking).

**Idempotency**: Jobs keyed by `(score_id, kind)`; safe to retry.  
**Failure policy**: exponential backoff; `try_count` cap; `log` retained for admin.

---

## 7) Security & Privacy

- **Private by default**: no public links, short‑TTL presigned URLs only.
- **No server sharing**: no session/room sharing endpoints.
- **Input validation**: MIME allowlist; file size caps; upload rate limiting.
- **PII minimization**: store only necessary profile fields.
- **Auditability**: `AccessLog` for significant actions (download, delete, quota change).
- **Data subject requests**: deletion/export flows (admin).

Optional:
- Virus scanning on upload (ClamAV sidecar) when moving to wider beta.

---

## 8) Plans / Quota / Referral (baseline)

- Plans: **Solo** (free/low quota), **Pro** (paid/higher quota).
- Quota counters updated on upload/delete; warning thresholds (80%, 95%).
- Referral bonus: per successful signup → extra MB recorded in `ReferralLog` and added to `total_quota_mb`.

Payments/IAP:
- Keep **server interface** for receipts, but full integration can wait until M1.

---

## 9) Deployment (Docker Compose)

Services:
- **web**: Django + DRF (ASGI not required because no WS)
- **worker**: Celery (or RQ) for jobs
- **db**: Postgres
- **cache**: Redis (celery broker, cache)
- **storage**: MinIO (dev) / AWS S3 (prod)
- **proxy**: Nginx (TLS, upload size, gzip)

Observability:
- Sentry (errors), Prometheus/Grafana (metrics), structured JSON logs.

---

## 10) Local Development

- `docker compose up -d` → launches db/redis/minio + app
- Create a `.env` from `.env.example` (see below).
- Run migrations: `python manage.py migrate`
- Create superuser: `python manage.py createsuperuser`
- Use Django Admin for quick inspection.

### Key Env Vars
```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=*
DATABASE_URL=postgres://scoremate:pass@db:5432/scoremate
REDIS_URL=redis://cache:6379/0
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

## 11) Sequences (ASCII)

### A) Upload Flow
```
Client --(JWT)--> Django: POST /files/upload-url (size,mime)
Django --verify--> Quota/MIME
Django --presign--> S3 (PUT)
Django --<-- return {url, headers}
Client --PUT--> S3 (binary)
Client --POST--> /scores {metadata, content_hash}
Worker(PDF_INFO/THUMBNAIL) -> updates Score(pages, thumbnail_key)
```

### B) Client-Only Sync (for clarity, server uninvolved)
```
ConductorClient <---- P2P/LAN ----> PlayerClients
(Clock sync, page turn schedule, announce, tempo)
```

---

## 12) Directory Layout (proposal)

```
/app
  /core        # settings, auth, quota, referral
  /scores      # models/serializers/views (metadata, tags)
  /setlists
  /files       # presigned URL issuance
  /tasks       # celery tasks (pdf_info, thumbnail, layout_hook)
  /admin       # admin customizations
/infra
  docker-compose.yml
  nginx/
/docs
  API.md
  SCHEMA.md
```

---

## 13) Roadmap

**MVP**
1) Auth/JWT & Quota counters  
2) Presigned upload; PDF_INFO + THUMBNAIL jobs  
3) Scores/Setlists CRUD & thumbnails in listing  
4) Admin: tasks, quotas, file index  
5) Usage warnings (email or webhook)

**M1**
- Referral redemption & automatic bonus application  
- Optional layout/bars hook with persisted JSON  
- Hardened download URLs (short TTL, scope)  
- Monthly activity/export report (admin)

---

## 14) Notes & Non‑Goals
- No WebSocket rooms; no fan‑out for page turns.
- No public libraries or cross‑user sharing in server.
- No AI models embedded in API container; use workers or external services.
