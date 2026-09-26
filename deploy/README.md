# 배포 (Docker) — 배포·데이터 계약 구현

ScoreMate API 를 dolfinid(GCP VM, 여러 프로젝트 공용)에 올리는 파일. 계약 선언층은 [`deploy.toml`](deploy.toml),
릴리스별 운영 델타는 루트 [`DEPLOY.md`](../DEPLOY.md), 표준 규약은 `../devdocs/guides/web/` (deployment · data-safety · operations).
구현은 같은 호스트의 **fcmanager**(Django + SQLite 단일 서비스)를 따랐다.

## 파일 구성

```
deploy/
  deploy.toml            배포 매니페스트(선언층)
  preflight.sh           [동사] 배포 전 위험 표면 diff + seed 냄새 lint (빌드 호스트)
  build.sh               [동사] test + 버전 bump + docker build + 이미지 스모크 + push (빌드 호스트 m710q)
  remote-prod.sh         빌드 호스트: ssh dolfinid '/srv/scoremate/deploy-prod.sh …' 얇은 래퍼(대상 고정)
  sync_to_srv.sh         최초 부트스트랩 안내(운영엔 저장소가 없으니 보통은 이미지에서 docker cp)
  Dockerfile             이미지 정의 — backend/ + deploy/host/* 를 싣는다(git-free 재료)
  Dockerfile.dockerignore  frontend/ · devlog/ · 테스트 제외
  docker-entrypoint.sh   root 로 시작 → 마운트 소유 uid 로 gosu 드롭 → migrate → 관리자 보증 → gunicorn
  host/                  운영 호스트 파일 — 배포 때 이미지에서 추출(self-heal)
    deploy-prod.sh         [동사 deploy 진입점] DEPLOY_SNAPSHOT=1
    _extract_and_deploy.sh 이미지에서 host 파일 추출(bash -n 통과 시에만 교체, 이전본 .previous) → deploy.sh
    deploy.sh              pull → .env IMAGE_TAG → down → 스냅샷(+.mig) → up → healthz 대기 → DB·파일 게이트 → smoke
    smoke.sh               [동사] /healthz 200 + 버전 일치 + user>0
    rollback.sh            [동사] --db=keep(기본, 이미지만) | --db=restore(스냅샷 무결성 검사 후 복원)
    docker-compose.yml     운영 compose (pull 전용, 127.0.0.1:8016, 읽기 전용 루트, cap_drop)
    scoremate.nginx.conf   호스트 nginx 사이트 원본 (TLS · 점검 페이지 · X-Accel internal location)
    maintenance.html       컨테이너 교체 중 nginx 가 503 으로 보여 줄 페이지
    .env.example           /srv/scoremate/.env 서식
backend/scripts/backup_db.py   운영 hourly 백업 (이미지에 실려 /srv/scoremate/scripts 로 추출)
```

## 운영 레이아웃 (`/srv/scoremate`)

| 경로 | 무엇 | 컨테이너 |
|---|---|---|
| `.env` (600) | IMAGE_TAG · HOST_PORT · SECRET_KEY · 관리자 | env_file |
| `db/` | `db.sqlite3` (+ `-wal` `-shm`), 손상 센티넬 `INTEGRITY_FAIL` | `/app/hostdb` |
| `files/` | 악보 PDF · 썸네일 (`{user_id}/uploads/…`, `{user_id}/scores/…`) | `/app/hostfiles` |
| `backup/` | hourly `scoremate_YYYYMMDD_HH.sqlite3`(24) · `pre_deploy/`(20) · nginx tar · `backup.log` | — |
| `maintenance/`, `acme/` | 점검 페이지 · Let's Encrypt webroot | — |
| `scripts/backup_db.py`, `*.sh`, `docker-compose.yml`, `scoremate.nginx.conf` | 이미지에서 추출 | — |

파일 받기: API 가 준 서명 URL(`/api/v1/files/blob/<token>/`) → Django 가 토큰만 확인하고 `X-Accel-Redirect: /_protected/<key>`
→ nginx 가 `/srv/scoremate/files/<key>` 를 직접 보낸다. 올리기는 같은 URL 에 PUT(Django 가 디스크에 쓴다, 한 번만).

## 배포 흐름

빌드 호스트(m710q):
```bash
./deploy/preflight.sh          # 위험 표면 + seed 냄새 + DEPLOY.md 델타
./deploy/build.sh X.Y.Z        # test + bump + build + 이미지 스모크 + push
./deploy/remote-prod.sh X.Y.Z  # = ssh dolfinid '/srv/scoremate/deploy-prod.sh X.Y.Z'
```
문제 시: `ssh dolfinid '/srv/scoremate/rollback.sh <이전 X.Y.Z> [--db=keep|restore]'`

빌드용 가상환경: `~/venv/scoremateserver` (`backend/requirements.txt`). 다른 경로면 `VENV=…/bin/activate`.

## 최초 설치 (dolfinid, 1회)

```bash
# 1. 디렉터리 — db/ 와 files/ 는 같은 소유자(컨테이너가 그 uid 로 돈다)
sudo install -d -o honestjung -g honestjung /srv/scoremate
cd /srv/scoremate && mkdir -p db files backup acme maintenance

# 2. 부트스트랩 파일을 이미지에서 꺼낸다 (저장소 불필요)
docker pull honestjung/scoremateserver:X.Y.Z
CID=$(docker create honestjung/scoremateserver:X.Y.Z)
for f in _extract_and_deploy.sh deploy-prod.sh .env.example scoremate.nginx.conf maintenance.html; do docker cp "$CID:/app/deploy/host/$f" ./; done
docker rm "$CID"; chmod +x _extract_and_deploy.sh deploy-prod.sh; mv maintenance.html maintenance/

# 3. .env — 비밀값은 출력하지 않는다
cp .env.example .env && chmod 600 .env   # DJANGO_SECRET_KEY · DJANGO_SUPERUSER_* 채우기

# 4. nginx + TLS: 80 블록만 먼저 → certbot webroot → 전체 설정
sudo certbot certonly --webroot -w /srv/scoremate/acme -d scoremate.noematica.kr \
  --non-interactive --agree-tos --deploy-hook 'nginx -t && systemctl reload nginx'
sudo cp scoremate.nginx.conf /etc/nginx/sites-available/scoremate
sudo ln -sf /etc/nginx/sites-available/scoremate /etc/nginx/sites-enabled/scoremate
sudo nginx -t && sudo systemctl reload nginx

# 5. 배포, 그리고 hourly 백업 cron
/srv/scoremate/deploy-prod.sh X.Y.Z
( crontab -l; echo '0 * * * * /usr/bin/python3 /srv/scoremate/scripts/backup_db.py >> /srv/scoremate/backup/backup.log 2>&1' ) | crontab -
```

nginx(www-data)가 `files/` 를 읽을 수 있어야 한다 — 컨테이너가 umask 002 로 쓰므로 디렉터리 775 · 파일 664.

## 백업 (data-safety.md)

| 트랙 | 어디서 | 보관 |
|---|---|---|
| pre-deploy | `deploy.sh` [4/7], 정지 후 cp | 20 |
| hourly | dolfinid cron `backup_db.py` — 무결성 검사 후 채택, 실패 시 prune 안 함 + 센티넬 → healthz degraded | 24 |
| daily 오프사이트 | m710q `~/scripts/backup-scoremate.sh` (정본 `system-operation/m710q/`) — 검증된 hourly 스냅샷 pull + `files/` rsync 하드링크 스냅샷 + NAS | 로컬 30일 · NAS 90일 |
