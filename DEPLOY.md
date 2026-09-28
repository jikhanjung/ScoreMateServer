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

### 0.7.1 (2026-09-27) — TV · 세트리스트 고르기 화면 정리
- 체크박스 · 라디오가 텍스트 칸용 스타일(늘어남)을 받아 흩어지던 것을 고침(`.choice` · `.option` · `.checklist`)
- TV 화면을 기기마다 카드 하나(정보 · 이름 바꾸기 · 받는 것 · 해제)로, 해제한 기기는 아래에 작게. "모든 악보"면 세트리스트 목록을 흐리게
- 세트리스트 "곡 넣기"를 여러 줄 선택 상자(Ctrl 필요) 대신 체크 목록으로
- 마이그레이션 없음

### 0.7.2 (2026-09-27) — 상단 버전 표시
- 웹 상단 "ScoreMate" 옆에 `v{VERSION}`(version.py — 배포마다 따라간다)
- 마이그레이션 없음

### 0.8.0 (2026-09-28) — 악보 인식(OMR) 레인
- 새 관리 명령 `omr_pending` · `omr_ingest`, 웹 판 목록에 인식 결과 · **MusicXML** 받기. 결과는 `files/…/scores/{id}/omr/v{N}.musicxml` + 분석 `astra-musicxml`
- 배포가 `scripts/astra_musicxml.py` · `scripts/omr_lane.sh` 를 이미지에서 꺼낸다(`_extract_and_deploy.sh` — **새 추출 규칙은 다음 배포부터**, 이번엔 한 번 `docker cp`)
- 호스트 1회: `omr/venv`(music21 · pymupdf, 설치함) · `codex login --device-auth`(사람) · cron `*/10 … omr_lane.sh` — deploy/README.md §악보 인식
- 마이그레이션 없음

### 0.8.1 (2026-09-28) — 기기 화면: 세트리스트만 · "연결 기기"
- 웹 메뉴 · 화면 "TV" → **"연결 기기"**(태블릿도 쓸 것이라 기기 중립 문구로)
- 기기마다 **세트리스트만** 고른다 — "모든 악보" 선택지 삭제(연결 확인 화면 포함). 저장하면 늘 `setlists`
  - 서버 모델의 `all` 값은 남아 있다(웹 · API 로 들어갈 길은 없음). 2026-09-28 운영 기기 `Z18TV_Test` 는 이미 `setlists`
- 세트리스트 화면의 "보낼 TV" 삭제 — 기기 설정은 "연결 기기" 화면 한 곳에서만
- OMR 레인: 로그인 만료(401)는 시도 횟수에 넣지 않는다(호스트에는 0.8.0 뒤 직접 반영했고, 이번 추출로 정식 반영)
- 마이그레이션 없음

### 0.8.2 (2026-09-28) — 기기 `sync_mode` 삭제
- 🔴 **마이그레이션 있음** `devices.0004_remove_device_sync_mode` — `devices.sync_mode` 열 삭제. 기기는 늘 고른 세트리스트의 곡만 받는다
  (운영 기기 `Z18TV_Test` 는 이미 `setlists` · 곡목 1개 — 받는 것이 바뀌지 않는다)
- API `devices/`, `devices/me/` 응답에서 `sync_mode` 가 빠졌다(`sync_setlists` 는 그대로). TV 앱은 이 필드를 읽지 않는다(2026-09-28 확인)
- 되돌리기: 0.8.1 이하 이미지는 이 열을 찾는다 → `rollback.sh 0.8.1 --db=restore`(배포 전 스냅샷), 또는 0.8.2 컨테이너에서 `migrate devices 0003` 뒤에 이미지만 되돌린다

### 0.9.0 (2026-09-28) — 곡 정보: 편곡 칸 · PDF 에서 찾기
- 🔴 **마이그레이션 있음** `scores.0006_score_arranger` — 열 추가(빈 값). API · 동기화 응답에 `arranger` 가 늘었다(추가만 — TV 는 모르는 필드를 무시)
- 올리기: 제목을 비우면 **PDF 문서 제목**(없으면 파일 이름). "곡 - Full Score" 꼴이면 곡 · 파트로 나눈다
- 고치기: "찾은 정보" — PDF 문서 속성 + 악보 인식이 첫 쪽에서 읽은 곡 정보, "채우기" 후 저장
- OMR 레인: 첫 쪽 곡 정보 호출(effort medium)이 먼저 돈다 → 분석 data.metadata(인식이 실패해도 남는다)

### 0.9.1 (2026-09-28) — 악보 인식: 짧은 악보부터 · 한 쪽씩 다시
- 인식 대기 순서: **쪽수가 적은 것부터**(쪽수 모름은 맨 뒤, 같으면 오래된 것부터)
- `astra_musicxml.py`: 두 쪽 조각이 검산 실패 두 번이거나 시간 초과면 **한 쪽씩** 다시. 호출 제한 40 → 60분. 예전 조각 이름(`NNN_pA-B`)도 이어 하기
  (호스트에는 0.9.0 뒤 직접 반영했고, 이번 추출로 정식 반영)
- 마이그레이션 없음

### 0.9.2 (2026-09-28) — 악보 인식: 한 쪽씩
- `astra_musicxml.py` 기본 **한 쪽에 한 번 호출**(전엔 두 쪽). 두 쪽 호출이 10~40분+ 걸리고, 형식 깨짐 · 시간 초과가 모두 두 쪽 조각에서 났다
- 이미 끝난 여러 쪽 조각(예전 두 쪽)은 그대로 쓰고 그만큼 건너뛴다 — 진행 중이던 K488(두 쪽으로 시작)도 다음 실행부터 한 쪽씩 이어 간다
- 마이그레이션 없음

### 0.9.3 (2026-09-28) — 악보 상세에서 쪽마다 보기
- 상세 화면에 "쪽 (N)" 격자(작은 이미지) → 누르면 큰 이미지 보기(← → · 이미지 왼쪽/오른쪽 누르기, 다음 쪽 미리 받기)
- `/scores/<id>/pages/<n>/?size=thumb|view` — 처음 볼 때 그 쪽만 그려 `files/{user}/scores/{id}/pages/{판 해시}/…jpg` 에 캐시, 서명 URL 로 302
  (Moldau 한 쪽: 작은 것 0.02초 · 19KB, 큰 것 0.2초 · 266KB). 판 · 악보를 지우면 캐시도 지운다. 쿼터에는 넣지 않는다
- 마이그레이션 없음

### 0.9.4 (2026-09-28) — 쪽 보기: 너비 맞춤 · 높이 맞춤
- 쪽 보기 막대에 **너비 맞춤**(가로를 채우고 세로 스크롤) · **높이 맞춤**(한 쪽이 한 화면에) 버튼, 키 W · H
- 고른 맞춤은 브라우저에 기억(localStorage). 처음엔 가로 화면이면 높이, 세로 화면이면 너비. 보기 창은 화면 전체 너비
- 마이그레이션 없음

### 0.9.5 (2026-09-28) — 쪽 보기: 1쪽 · 2쪽
- 쪽 보기 막대에 **1쪽 / 2쪽** — 2쪽은 1–2, 3–4 … 나란히, 넘기기도 두 쪽씩(마지막 홀수 쪽은 혼자). 키 1 · 2
- 너비 맞춤(2쪽이면 반씩) · 높이 맞춤(두 쪽이 화면보다 넓으면 가로 스크롤)과 함께. 고른 것은 브라우저에 기억
- 마이그레이션 없음

### 0.9.6 (2026-09-28) — 기기 동기화에 MusicXML
- `sync/scores` 의 각 악보에 **`musicxml`**: 인식 결과가 있으면 `{url, sha256, size_bytes, filename, parts, measures, updated_at}`, 없으면 `null`(추가만)
- 새 API `GET /api/v1/scores/{id}/musicxml/`(`?version=n`) — 서명 URL 로 302, 기기마다 'sync' 제한. 파일 이름은 PDF 이름 + `.musicxml`
- 인식이 끝나면 악보 `updated_at` 이 바뀌어 다음 동기화에 그 악보가 다시 온다(기존 동작). TV 앱이 받게 하려면 앱 쪽 작업 — P06 §11
- 마이그레이션 없음

### 0.9.7 (2026-09-28) — 악보 인식: 짧은 형식 (약 5배 빠름)
- 모델은 MusicXML 대신 **짧은 텍스트**(`C#5/8. r/4 C4+E4/2 (3:2 … ) [mf] {st,s(}`)로 쓰고, `scripts/omr_compact.py` 가 MusicXML 을 만든다
  (K488 1쪽: 1,310 → 273초, 출력 43,600 → 8,800 토큰, high MusicXML 과 34마디 중 33마디 같음 — 나머지 1마디도 같은 음을 두 성부로 적은 것)
- 첫 쪽 곡 정보 호출이 조표 · 박자도 읽고, 옮긴 결과의 첫 조표와 다르면 다시 세게 한다
- `--format musicxml` 로 예전 방식. 기본 effort high
- 배포가 `scripts/omr_compact.py` 도 꺼낸다(새 추출 규칙은 다음 배포부터 → 이번엔 호스트에 직접 복사)
- 마이그레이션 없음

