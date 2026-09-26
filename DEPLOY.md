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
