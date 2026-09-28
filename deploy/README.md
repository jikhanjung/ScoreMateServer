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
    prune.sh               오래된 이 서비스 이미지만 정리 (KEEP=3, DRY_RUN=1)
    docker-compose.yml     운영 compose (pull 전용, 127.0.0.1:8016, 읽기 전용 루트, cap_drop)
    scoremate.nginx.conf   호스트 nginx 사이트 원본 (TLS · 점검 페이지 · X-Accel internal location)
    maintenance.html       컨테이너 교체 중 nginx 가 503 으로 보여 줄 페이지
    .env.example           /srv/scoremate/.env 서식
    omr_lane.sh            악보 인식(OMR) 레인 — 호스트 cron, 한 번에 판 하나 (§악보 인식)
backend/scripts/backup_db.py   운영 hourly 백업 (이미지에 실려 /srv/scoremate/scripts 로 추출)
backend/scripts/astra_musicxml.py  PDF → MusicXML (Codex CLI gpt-6-astra, 호스트에서 실행)
```

## 운영 레이아웃 (`/srv/scoremate`)

| 경로 | 무엇 | 컨테이너 |
|---|---|---|
| `.env` (600) | IMAGE_TAG · HOST_PORT · SECRET_KEY · 관리자 | env_file |
| `db/` | `db.sqlite3` (+ `-wal` `-shm`), 손상 센티넬 `INTEGRITY_FAIL` | `/app/hostdb` |
| `files/` | 악보 PDF · 썸네일 · 인식 결과 MusicXML (`{user_id}/uploads/…`, `{user_id}/scores/…`, `…/scores/{id}/omr/v{N}.musicxml`) | `/app/hostfiles` |
| `omr/` | 인식 레인: `venv/`(music21 · pymupdf) · `work/v{판 id}/`(조각 · 로그, 이어 하기용) · `lane.log` · `lane.lock` | — |
| `backup/` | hourly `scoremate_YYYYMMDD_HH.sqlite3`(24) · `pre_deploy/`(20) · nginx tar · `backup.log` | — |
| `maintenance/`, `acme/` | 점검 페이지 · Let's Encrypt webroot | — |
| `scripts/backup_db.py`, `scripts/astra_musicxml.py`, `scripts/omr_lane.sh`, `*.sh`, `docker-compose.yml`, `scoremate.nginx.conf` | 이미지에서 추출 | — |

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

**올린 PDF(와 썸네일 · MusicXML)는 `files/` 에 있고 daily 오프사이트가 챙긴다** — pre-deploy · hourly 는 DB 만.
m710q `~/backups/scoremate/current/files/`(미러) · `files_snapshots/monthly/YYYYMM_full` + `daily/YYYYMMDD`(하드링크, 한 번 쓰면 안 바뀌는 파일이라 싸다) ·
NAS `scoremate_backup/current/files` + `files_snapshots`(-H). 2026-09-28 확인: PDF 6 · 표지 5 모두 미러에 있다.
한계: 하루 한 번(05:25)이라 그날 올린 파일은 다음 새벽까지 운영 디스크에만 있다 — 필요하면 files 만 더 자주 rsync.

## 보표 · 마디 분석 (devlog 068)

TV 앱의 PDF 분석(`score/`, Kotlin)을 옮긴 `scores/score_layout.py` 가 판마다 보표 · 시스템 · 마디선 · 박자표 · 보표 이름을 JSON 파일로 남긴다.
기기는 동기화 응답의 `layout` 으로 받아 스스로 분석하지 않고 쓸 수 있다.
```
*/5 * * * * /srv/scoremate/scripts/layout_lane.sh >> /srv/scoremate/omr/layout.log 2>&1
```
`manage.py score_layout` = 분석 파일이 없는 판 전부, `--version-id N` = 그 판을 다시.

## 악보 인식 (OMR, devlog P01)

PDF → MusicXML 을 **운영 호스트의 cron** 이 만든다. 모델 호출(Codex CLI, `gpt-6-astra`, ChatGPT 로그인)은 호스트에서, 결과 저장은 컨테이너에서.

```
*/10 cron → scripts/omr_lane.sh
  1. docker compose exec api manage.py omr_pending    인식할 판(지금 쓰는 판 · 해시 있음 · 인식 기록 없음) 하나
  2. sha256 확인 후 omr/venv/bin/python scripts/astra_musicxml.py files/<key> omr/work/v<id>
       2쪽씩 호출 → 조각마다 파트 구성 · 마디별 박 길이 검산(실패 시 오류를 알려 한 번 더) → 이어 붙이기
  3. 결과 JSON | manage.py omr_ingest   → 판의 분석(analyzer=astra-musicxml) + files/…/omr/v<N>.musicxml
```
- 웹 악보 화면의 판 목록에 "악보 인식 · N파트 · M마디" + **MusicXML** 받기(PDF 와 같은 권한). 실패는 "악보 인식 실패"
- 검산을 통과하지 못한 판은 실패로 기록하고 다시 부르지 않는다 → 다시 하려면 admin 에서 그 분석(ScoreAnalysis)을 지운다
- 실행 자체가 안 된 경우(codex · 로그인 · 시간 초과)는 기록하지 않고 다음 cron 에서 다시, 같은 판이 3번 그러면 실패로 기록
- 쪽당 6~7분(2쪽 호출 13분 안팎). 겹치지 않게 flock. 구독 한도는 이 호스트 사용자의 ChatGPT 계정

설치(1회, 사람):
```bash
# codex 는 nvm node 에 있다 (cron 은 nvm 을 안 읽으므로 레인이 ~/.nvm/versions/node/*/bin 을 스스로 PATH 에 넣는다)
codex login --device-auth            # 만료되면 codex logout 후 다시
python3 -m venv /srv/scoremate/omr/venv && /srv/scoremate/omr/venv/bin/pip install music21 pymupdf
( crontab -l; echo '*/10 * * * * /srv/scoremate/scripts/omr_lane.sh >> /srv/scoremate/omr/lane.log 2>&1' ) | crontab -
```
멈추기: 그 cron 줄을 지운다(주석 처리). 진행 확인: `tail -f /srv/scoremate/omr/lane.log`, `omr/work/v<id>/run.log`.
