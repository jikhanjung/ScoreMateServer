# DEPLOY.md — 릴리스별 운영 델타 (append-only)

배포 절차는 [`deploy/README.md`](deploy/README.md), 매니페스트는 [`deploy/deploy.toml`](deploy/deploy.toml).
이 파일에는 **릴리스마다 운영자가 알아야 할 변화**만 아래로 덧붙인다(지우지 않는다).

## 데이터 레인 경계

- 시스템 시드 없음(`has_seed = false`). 사용자 · 앙상블 · 악보 · 세트리스트는 전부 운영 데이터 — 앱 안에서만 들어오고, 안전망은 백업이다.
- 운영 DB 에 호스트에서 쓰지 않는다. 일괄 작업은 컨테이너 안에서, **DB 소유 uid 로**:
  `cd /srv/scoremate && docker compose exec -u "$(stat -c %u db)" api python manage.py …`
  (컨테이너 root 는 cap_drop 으로 DB 를 읽기 전용으로 연다 — `attempt to write a readonly database`)
- `.env` 는 배포가 `IMAGE_TAG` 한 줄만 바꾼다.

## 릴리스별 운영 델타

### 0.1.0 (2026-09-27) — 최초 운영 배포
- dolfinid `/srv/scoremate`, `127.0.0.1:8016`, `https://scoremate.noematica.kr` (API 만. 웹은 Django 템플릿으로 새로 만든다)
- 신규 설치: `deploy/README.md §최초 설치` 전부 (디렉터리 · .env · nginx · certbot · cron)
- 저장소 `STORAGE_BACKEND=local` — `/srv/scoremate/files`, 받기는 nginx X-Accel-Redirect
- 마이그레이션: 처음부터(빈 DB). 관리자 계정은 entrypoint 가 `.env` 의 `DJANGO_SUPERUSER_*` 로 만든다
- 오프사이트: m710q `backup-scoremate.sh` cron 등록
- 운영 확인(2026-09-27): 외부에서 가입 → 앙상블 → PDF 올리기(PUT, 재사용 409) → 페이지 수 35 · SHA-256 일치 → 썸네일 ·
  원본 받기(nginx X-Accel, 해시 일치) → 비멤버 404 → 정리. 임시 계정 2개는 컨테이너 안에서 지웠다

### 0.1.1 (2026-09-27)
- deploy.sh · rollback.sh 의 migration 수 조회를 DB 소유 uid 로 — 0.1.0 은 컨테이너 root 로 조회해 조용히 실패했다
  (rollback keep 가드가 "미상"으로 진행하는 상태). 운영 데이터 영향 없음
- local 저장소에서 파일을 지우면 비게 된 디렉터리도 지운다
- `prune.sh` 추가 (이 서비스 이미지만, 기본 3개 보존)
- 마이그레이션 없음

### 0.2.0 (2026-09-27) — 웹 화면 (Django 템플릿)
- `/` 가 웹이 됐다(로그인 · 악보 · 올리기 · 앙상블 · 초대 링크 `/join/<code>/` · 계정). API 안내 JSON 은 `/api/v1/` 에만 남는다
- 세션 로그인 — `.env` 변경 없음(CSRF_TRUSTED_ORIGINS · 보안 쿠키는 compose 에 이미 있다)
- 가입을 닫으려면 `.env` 에 `REGISTRATION_OPEN=false` (웹 · API 가입이 함께 닫힌다) 후 `docker compose up -d --force-recreate`
- 웹 업로드 임시 파일: `/srv/scoremate/files/.incoming` (compose `FILE_UPLOAD_TEMP_DIR`) — 요청이 끝나면 지워진다
- 마이그레이션 없음

### 0.3.0 (2026-09-27) — 악보 판(버전)
- 🔴 **마이그레이션 있음** `scores.0004_score_versions` — 스키마 + 데이터(기존 악보마다 판 1). 되돌리기가 있지만,
  이 배포 뒤 판을 올렸다면 0.2.0 으로의 `rollback --db=keep` 은 가드가 막는다 → `--db=restore`(pre-deploy 스냅샷) 판단
- 새 API: `/api/v1/scores/{id}/versions/…`. 웹 상세에 판 칸
- `.env` 변경 없음

### 0.4.0 (2026-09-27) — TV 기기 연결 (RFC 8628)
- 🔴 **마이그레이션 있음** `devices.0001_initial` (새 테이블만 — 가산, 되돌리기 안전)
- 새 API: `/api/v1/device/code`, `/api/v1/device/token`, `/api/v1/devices/`. 웹: `/activate/`, `/devices/`(TV 메뉴)
- 인증 클래스가 `devices.auth.DeviceAwareJWTAuthentication` 으로 바뀌었다(기존 사용자 토큰은 그대로 동작)
- 선택 `.env`: `DEVICE_REFRESH_TOKEN_DAYS`(기본 180)

### 0.5.0 (2026-09-27) — TV 동기화 API
- 🔴 **마이그레이션 있음** `devices.0002_device_last_synced_at` (열 추가 — 가산, 되돌리기 안전)
- 새 API: `/api/v1/sync/scores/`, `/api/v1/scores/{id}/download/`, `/api/v1/devices/me/heartbeat/`
- 선택 `.env`: `SYNC_PAGE_SIZE`(200), `SYNC_LAG_SECONDS`(5)

### 0.5.1 (2026-09-27) — 초대 전용 가입
- `/srv/scoremate/.env` 에 `REGISTRATION_OPEN=false` 추가(운영 결정). 초대 링크(`/join/<code>/`)로 온 사람만 가입하고, 가입하면 그 앙상블에 들어간다.
  API 가입은 `invite_code` 가 있어야 한다. 기존 계정 로그인은 그대로
- 마이그레이션 없음

### 0.6.0 (2026-09-27) — S6: 앙상블 세트리스트 · 분석 공유 · Google 로그인
- 🔴 **마이그레이션 있음** `setlists.0003_setlist_ensemble`(열 추가), `scores.0005_score_analysis`, `core.0002_social_account`(새 테이블) — 모두 가산
- 새 API: `/api/v1/sync/setlists/`, `/api/v1/scores/{id}/analysis/`. 웹: `/setlists/`, `/auth/google/`
- Google 로그인은 `.env` 에 `GOOGLE_CLIENT_ID` · `GOOGLE_CLIENT_SECRET` 을 넣어야 켜진다(devlog 061 §4). 지금은 꺼져 있다

### 0.6.1 (2026-09-27) — 동기화 요청 제한을 기기마다
- 동기화 · 받기 · 분석 · heartbeat 는 `sync` 제한(3000/시간)을 **기기마다**(기기 토큰이 아니면 사용자마다) 센다.
  전에는 사용자당 1000/시간 한 통을 같은 계정의 TV 여러 대와 웹이 나눠 써서, 처음 연결하는 TV 두 대가 함께 막힐 수 있었다
- 마이그레이션 없음

### 0.6.2 (2026-09-27) — TV P06 요청 반영
- 앙상블 이름을 바꾸면(API · 웹) 그 앙상블 악보의 `updated_at` 을 올린다 — TV 폴더 이름이 새 이름을 따라간다. 설명만 바꾸면 올리지 않는다
- 웹 업로드: 같은 곳에 제목 · 파트가 같은 악보가 있으면 묻는다(새 판으로 · 따로)
- 마이그레이션 없음

### 0.6.3 (2026-09-27) — 워커 공유 캐시 (버그 수정)
- 🔴 운영 버그: 캐시가 기본 메모리(워커마다 따로)였다 — gunicorn 워커 2개 사이에서 **API 업로드 예약(upload-url → upload-confirm)이
  절반쯤 "없음"으로 실패**하고, 요청 제한 · 로그인 실패 제한 · 코드 조회 제한이 워커 수만큼 느슨했다. 웹 업로드 · TV 동기화는 예약을 쓰지 않아 영향 없음
- compose `CACHE_DIR=/tmp/scoremate-cache`(파일 캐시, 워커 공유, 재시작하면 비워짐). 배포 게이트 [6/7] 가 캐시 공유를 확인한다
- 마이그레이션 없음

### 0.6.4 (2026-09-27) — 웹에서 앙상블 숨김
- `WEB_ENSEMBLES`(기본 false): 웹의 앙상블 메뉴 · 올릴 곳/곡목 선택 · 목록 필터 · 배지 · 문구를 숨긴다. 웹 업로드 · 세트리스트는 개인 것으로만
- 그대로: API(TV 동기화 · 앙상블 API), 초대 링크(`/join/<code>/` — 초대 전용 가입이 이것에 기댄다), 앙상블 페이지 직접 주소
- 다시 보이려면 `.env` 에 `WEB_ENSEMBLES=true` → `docker compose up -d --force-recreate`
- 마이그레이션 없음

### 0.7.0 (2026-09-27) — TV 마다 받을 것(세트리스트)
- 🔴 **마이그레이션 있음** `devices.0003_device_sync_setlists` — 열 · 표 추가 + 데이터: **기존 기기는 `all`(모든 악보)** 로 둔다. 새 기기 기본은 `setlists`
- 웹 TV 화면 · 세트리스트 "보낼 TV" · TV 연결 화면에서 고른다. TV 앱 변경 없음
