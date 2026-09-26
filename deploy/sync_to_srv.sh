#!/bin/bash
# deploy/sync_to_srv.sh — 최초 부트스트랩 1회용 (git-free 전환 전). 상시 배포에는 필요 없다.
#
# 운영 서버에는 저장소가 없다. 대신 **이미지에서 직접** 부트스트랩한다(운영 호스트에서):
#   sudo install -d -o "$(id -un)" -g "$(id -gn)" /srv/scoremate
#   cd /srv/scoremate && CID=$(docker create honestjung/scoremateserver:X.Y.Z)
#   for f in _extract_and_deploy.sh deploy-prod.sh .env.example; do docker cp "$CID:/app/deploy/host/$f" ./; done
#   docker rm "$CID" && chmod +x _extract_and_deploy.sh deploy-prod.sh
#
# 저장소가 있는 머신이 곧 대상 호스트라면(예: 테스트 타깃) 이 스크립트로 같은 일을 한다.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOST_DEST="${HOST_DEST:-/srv/scoremate}"
HOST_SRC="$PROJECT_DIR/deploy/host"

if [ ! -d "$HOST_DEST" ]; then
    echo "ERROR: $HOST_DEST 없음 — 대상 호스트에서 디렉터리를 만든 뒤 실행." >&2
    exit 1
fi

cp -p "$HOST_SRC"/deploy-prod.sh "$HOST_SRC"/_extract_and_deploy.sh "$HOST_SRC"/.env.example "$HOST_DEST/"
chmod +x "$HOST_DEST"/deploy-prod.sh "$HOST_DEST"/_extract_and_deploy.sh
echo "bootstrap synced → $HOST_DEST (deploy-prod.sh · _extract_and_deploy.sh · .env.example)"
echo "다음: .env 준비 후 $HOST_DEST/deploy-prod.sh X.Y.Z"
