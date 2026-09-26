# DEPLOY.md — 릴리스별 운영 델타 (append-only)

배포 절차는 [`deploy/README.md`](deploy/README.md), 매니페스트는 [`deploy/deploy.toml`](deploy/deploy.toml).
이 파일에는 **릴리스마다 운영자가 알아야 할 변화**만 아래로 덧붙인다(지우지 않는다).

## 데이터 레인 경계

- 시스템 시드 없음(`has_seed = false`). 사용자 · 앙상블 · 악보 · 세트리스트는 전부 운영 데이터 — 앱 안에서만 들어오고, 안전망은 백업이다.
- 운영 DB 에 호스트에서 쓰지 않는다. 일괄 작업은 `docker compose exec api python manage.py …` 로 컨테이너 안에서.
- `.env` 는 배포가 `IMAGE_TAG` 한 줄만 바꾼다.

## 릴리스별 운영 델타

### 0.1.0 (2026-09-27) — 최초 운영 배포
- dolfinid `/srv/scoremate`, `127.0.0.1:8016`, `https://scoremate.noematica.kr` (API 만. 웹은 Django 템플릿으로 새로 만든다)
- 신규 설치: `deploy/README.md §최초 설치` 전부 (디렉터리 · .env · nginx · certbot · cron)
- 저장소 `STORAGE_BACKEND=local` — `/srv/scoremate/files`, 받기는 nginx X-Accel-Redirect
- 마이그레이션: 처음부터(빈 DB). 관리자 계정은 entrypoint 가 `.env` 의 `DJANGO_SUPERUSER_*` 로 만든다
- 오프사이트: m710q `backup-scoremate.sh` cron 등록
