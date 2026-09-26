#!/bin/bash
# /srv/scoremate/deploy.sh — ScoreMate 버전 스왑 배포 (공통 엔진, fcmanager deploy.sh 동형).
# 직접 부르지 말고 git-free 래퍼로 호출(이미지에서 host 파일 추출 후 이 엔진에 위임):
#   /srv/scoremate/deploy-prod.sh X.Y.Z    (DEPLOY_SNAPSHOT=1 — 배포 전 DB 스냅샷)
#
# 흐름: pull → .env IMAGE_TAG → down → pre-deploy DB 스냅샷 → up(전 서비스) → healthz 대기
#       → DB · 파일 저장소 바인딩 게이트 → smoke. down~up 사이 nginx 가 502 → maintenance.html.
# 근거: devdocs guides/web/deployment.md §5 · data-safety.md.
# Usage: DEPLOY_SNAPSHOT=0|1 /srv/scoremate/deploy.sh X.Y.Z
set -euo pipefail

VERSION=${1:-}
if [ -z "$VERSION" ]; then
    echo "Usage: $0 X.Y.Z"
    exit 1
fi

ROOT=/srv/scoremate
cd "$ROOT"

IMAGE="honestjung/scoremateserver:${VERSION}"

# 헬스체크 포트(.env HOST_PORT, 기본 8016)
HOST_PORT=$(sed -n 's/^HOST_PORT=//p' .env 2>/dev/null)
HOST_PORT=${HOST_PORT:-8016}

[ -f .env ] || { echo "✗ $ROOT/.env 없음 — .env.example 을 복사해 비밀값을 채운 뒤 다시 실행."; exit 1; }

echo "=== [1/7] Pull ${IMAGE} ==="
docker pull "${IMAGE}"

echo ""
echo "=== [2/7] .env IMAGE_TAG=${VERSION} (그 키만 in-place — 비밀값은 건드리지 않는다) ==="
if grep -q '^IMAGE_TAG=' .env 2>/dev/null; then
    sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${VERSION}/" .env
else
    echo "IMAGE_TAG=${VERSION}" >> .env
fi

echo ""
echo "=== [3/7] Stop old container ==="
# rollback keep 가드용: 배포 전(새 이미지의 migrate 실행 전) 적용된 migration 수를 기록.
# exec 는 DB 소유 uid 로 — 컨테이너 root 는 cap_drop 으로 DAC_OVERRIDE 가 없어 DB 를 읽기 전용으로 연다
# (그러면 WAL init_command 가 실패해 이 값이 조용히 비고 rollback keep 가드가 무력해진다 — 0.1.0 에서 발견).
DB_UID=$(stat -c %u "$ROOT/db" 2>/dev/null || echo 0)
PRE_MIG=""
if [ "${DEPLOY_SNAPSHOT:-1}" = "1" ] && docker compose ps -q api 2>/dev/null | grep -q .; then
    PRE_MIG=$(docker compose exec -T -u "$DB_UID" api python manage.py showmigrations --plan 2>/dev/null | grep -c '\[X\]' || true)
    [ "$PRE_MIG" = "0" ] && PRE_MIG=""    # 0 = 조회 실패(적용된 migration 이 0 인 운영은 없다)
fi
docker compose down
mkdir -p "$ROOT/db" "$ROOT/files"    # 신규 호스트도 마운트 대상 디렉터리는 있어야 한다

echo ""
echo "=== [4/7] (prod) Pre-deploy DB 스냅샷 (롤백 안전망) ==="
# compose down 직후 — writer 없어 cp 안전. WAL/SHM 도 함께 보존.
if [ "${DEPLOY_SNAPSHOT:-1}" = "1" ] && [ -f "$ROOT/db/db.sqlite3" ]; then
    SNAP_DIR="$ROOT/backup/pre_deploy"
    mkdir -p "$SNAP_DIR"
    TS=$(date -u +%Y%m%d_%H%M%S)
    SNAP="$SNAP_DIR/scoremate_pre_deploy_${VERSION}_${TS}.sqlite3"
    cp -p "$ROOT/db/db.sqlite3" "$SNAP"
    [ -f "$ROOT/db/db.sqlite3-wal" ] && cp -p "$ROOT/db/db.sqlite3-wal" "${SNAP}-wal" || true
    [ -f "$ROOT/db/db.sqlite3-shm" ] && cp -p "$ROOT/db/db.sqlite3-shm" "${SNAP}-shm" || true
    [ -n "$PRE_MIG" ] && printf '%s\n' "$PRE_MIG" > "${SNAP}.mig" || true
    echo "  snapshot: $SNAP ($(du -h "$SNAP" | cut -f1), pre-migration count: ${PRE_MIG:-미상})"
    # retention: 최근 20개 — 이 디렉터리를 prune 하는 곳은 여기 하나뿐(data-safety §10). 사이드카도 함께 지운다
    ls -1tr "$SNAP_DIR"/scoremate_pre_deploy_*.sqlite3 2>/dev/null \
        | head -n -20 \
        | while read -r f; do rm -f "$f" "$f-wal" "$f-shm" "$f.mig"; done
else
    echo "  (DEPLOY_SNAPSHOT=${DEPLOY_SNAPSHOT:-1} 또는 DB 없음 — 스냅샷 건너뜀)"
fi

echo ""
echo "=== [5/7] Start new container (전 서비스) + wait for backend (/healthz) ==="
# up -d (서비스명 미지정) = compose 전 서비스 — 사이드카가 생겨도 빠지지 않는다(계약 MUST).
docker compose up -d
UP=0
for i in $(seq 1 60); do
    if curl -fsS -o /dev/null -m 2 -H "X-Forwarded-Proto: https" "http://127.0.0.1:${HOST_PORT}/healthz" 2>/dev/null; then
        echo "  backend up after ${i}s"; UP=1
        break
    fi
    sleep 1
done
if [ "$UP" != 1 ]; then
    echo "  ✗ 60초 안에 /healthz 가 200 이 아니다 — 로그:"
    docker compose logs --tail 60
    echo "  조사 후 필요시 롤백: $ROOT/rollback.sh <이전 X.Y.Z> [--db=keep|restore]"
    exit 1
fi

echo ""
echo "=== [6/7] Verify DB · 파일 저장소 바인딩 (호스트 마운트, 이미지 내부 아님) ==="
# 경로가 어긋나면 컨테이너가 이미지 내부 빈 DB · 빈 파일 디렉터리로 폴백해 빈 사이트로 뜬다
# (실데이터는 $ROOT/db · $ROOT/files 에 안전). 경로 + 쓰기 프로브로 확인한다.
EXPECT_DB=/app/hostdb/db.sqlite3
EXPECT_FILES=/app/hostfiles
PROBE_UID=$(stat -c %u "$ROOT/db" 2>/dev/null || echo 0)
BINDING=$(docker compose exec -T -u "${PROBE_UID}" api python manage.py shell -c "
import os, tempfile
from django.conf import settings
from django.db import connection
c = connection.cursor()
c.execute('CREATE TABLE IF NOT EXISTS _deploy_write_probe(x INTEGER)')
c.execute('DROP TABLE _deploy_write_probe')
fd, p = tempfile.mkstemp(dir=str(settings.FILES_ROOT), prefix='.deploy-probe-'); os.close(fd); os.unlink(p)
print(settings.DATABASES['default']['NAME'], settings.FILES_ROOT, settings.STORAGE_BACKEND, 'ok')" 2>&1 | tr -d '\r' | tail -n1)
if [ "$BINDING" = "${EXPECT_DB} ${EXPECT_FILES} local ok" ]; then
    echo "  OK: DB=${EXPECT_DB}, files=${EXPECT_FILES} (local), 둘 다 쓰기 가능"
else
    echo "  ✗ FATAL: 바인딩 검사 실패 — 기대 '${EXPECT_DB} ${EXPECT_FILES} local ok', 실제 '${BINDING:-<empty>}'"
    echo "    · 경로가 다르면: compose 의 environment(DATA_DIR · FILES_ROOT · STORAGE_BACKEND) 확인"
    echo "    · 쓰기 실패면: ${ROOT}/db 와 ${ROOT}/files 소유자를 같게 (sudo chown -R \$(stat -c %u:%g ${ROOT}/db) ${ROOT}/files)"
    echo "    확인 후 (cd ${ROOT} && docker compose up -d --force-recreate)"
    exit 1
fi

echo ""
echo "=== [7/7] Smoke (healthz + 버전 일치 + 핵심 행 수) ==="
if [ -x "$ROOT/smoke.sh" ]; then
    if ! "$ROOT/smoke.sh" "$VERSION"; then
        echo ""
        echo "!!! smoke 실패 — 컨테이너는 떴으나 검증 불일치(버전/DB/행수)."
        echo "!!! 조사 후 필요시 롤백: $ROOT/rollback.sh <이전 X.Y.Z> [--db=keep|restore] (기본 keep=이미지만)"
        exit 1
    fi
else
    echo "  (smoke.sh 없음 — 이미지 추출 실패? 건너뜀.)"
fi

echo ""
echo "=== Done: scoremate -> ${VERSION} (port ${HOST_PORT}, smoke OK) ==="
docker compose ps
