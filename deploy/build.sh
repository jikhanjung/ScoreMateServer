#!/bin/bash
# build.sh — 테스트 + 버전 bump + 이미지 빌드 + 이미지 스모크 + push. (빌드 호스트 m710q 전용)
# Usage: ./deploy/build.sh X.Y.Z
#
# 책임 분리 (devdocs guides/web/deployment.md §0 · §2):
#   - 이 스크립트: 개발기에서 test → bump(backend/scoremateserver/version.py) → docker build → 스모크 → push
#     테스트가 실패하면 push 전에 멈춘다 — 깨진 이미지는 레지스트리에 가지 않는다.
#   - 운영(dolfinid)은 git-free: deploy-prod.sh 가 이미지를 pull 하고 host 파일을 이미지에서 꺼낸다.
set -euo pipefail

VERSION=${1:-}
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Usage: $0 X.Y.Z" >&2
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${VENV:-$HOME/venv/scoremateserver/bin/activate}"
IMAGE=honestjung/scoremateserver
cd "$PROJECT_DIR"

echo "=== [1/5] Tests (SQLite, S3 는 moto) ==="
# shellcheck disable=SC1090
source "$VENV"
(cd backend && env -u DATABASE_URL -u REDIS_URL -u STORAGE_BACKEND python -m pytest tests/ -q -p no:cacheprovider)
(cd backend && DATA_DIR="$(mktemp -d)" python manage.py makemigrations --check --dry-run >/dev/null) \
    || { echo "✗ 마이그레이션 누락 — makemigrations 후 커밋"; exit 1; }
echo "All tests passed."

echo ""
echo "=== [2/5] Bumping version to $VERSION ==="
echo "VERSION = '$VERSION'" > backend/scoremateserver/version.py
git add backend/scoremateserver/version.py
if git diff --cached --quiet; then
    echo "(version already at $VERSION, no commit)"
else
    git commit -m "Bump version to $VERSION"
fi
REVISION=$(git rev-parse --short HEAD)
[ -n "$(git status --porcelain)" ] && REVISION="${REVISION}-dirty"

echo ""
echo "=== [3/5] Building image $IMAGE:$VERSION (linux/amd64, rev $REVISION) ==="
docker build --platform linux/amd64 -f deploy/Dockerfile \
    --build-arg APP_VERSION="$VERSION" --build-arg VCS_REF="$REVISION" \
    -t "$IMAGE:$VERSION" -t "$IMAGE:latest" .

echo ""
echo "=== [4/5] Image smoke (운영과 같은 옵션으로 띄워 /healthz · 버전 · 관리자 확인) ==="
SMOKE_DIR=$(mktemp -d)
mkdir -p "$SMOKE_DIR/db" "$SMOKE_DIR/files"
CID=""
cleanup() { [ -n "$CID" ] && docker rm -f "$CID" >/dev/null 2>&1; rm -rf "$SMOKE_DIR"; }
trap cleanup EXIT
CID=$(docker run -d --read-only --tmpfs /tmp:rw,nosuid,size=64m \
    --cap-drop ALL --cap-add CHOWN --cap-add SETUID --cap-add SETGID --security-opt no-new-privileges:true \
    -v "$SMOKE_DIR/db:/app/hostdb" -v "$SMOKE_DIR/files:/app/hostfiles" \
    -e STORAGE_BACKEND=local -e FILES_X_ACCEL_PREFIX=/_protected/ -e REQUIRE_SECRET_KEY=true \
    -e DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
    -e DJANGO_SUPERUSER_EMAIL=smoke@example.com -e DJANGO_SUPERUSER_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(16))')" \
    -p 127.0.0.1::8000 "$IMAGE:$VERSION")
PORT=$(docker port "$CID" 8000/tcp | head -1 | awk -F: '{print $NF}')
BODY=""
for _ in $(seq 1 60); do
    BODY=$(curl -fsS -m 2 "http://127.0.0.1:$PORT/healthz" 2>/dev/null) && break
    sleep 1
done
echo "  $BODY"
EXPECT_VERSION="$VERSION" python - "$BODY" <<'PY' || { docker logs --tail 40 "$CID"; exit 1; }
import json, os, sys
d = json.loads(sys.argv[1] or '{}')
assert d.get('status') == 'ok', d
assert d.get('version') == os.environ['EXPECT_VERSION'], d
assert (d.get('counts') or {}).get('user', 0) > 0, d
print('  image smoke OK')
PY
cleanup; CID=""; trap - EXIT

echo ""
echo "=== [5/5] Pushing image ==="
docker push "$IMAGE:$VERSION"
docker push "$IMAGE:latest"

echo ""
echo "=== Done: $IMAGE:$VERSION ==="
echo "다음 단계 (git-free — dolfinid 에 repo/git pull 불요):"
echo "  ./deploy/remote-prod.sh $VERSION   # = ssh dolfinid '/srv/scoremate/deploy-prod.sh $VERSION'"
