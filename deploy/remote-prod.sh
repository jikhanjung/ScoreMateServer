#!/bin/bash
# deploy/remote-prod.sh — (빌드 호스트 m710q 전용) 운영 서버에 원격 배포하는 얇은 래퍼.
# 운영 서버의 /srv/scoremate/deploy-prod.sh 를 SSH 로 실행할 뿐. 실제 배포 로직은 전부 운영 쪽(이미지에서 self-heal).
# 대상은 이 파일에 고정한다 — 기억이나 ~/.ssh/config 별칭에 기대지 않는다(deployment.md §4).
#
# Usage: ./deploy/remote-prod.sh X.Y.Z
# Env:
#   PROD_HOST   원격 SSH 대상 (기본 honestjung@cdgts.paleobytes.info = dolfinid)
#   PROD_DEPLOY 원격 배포 스크립트 경로 (기본 /srv/scoremate/deploy-prod.sh)
set -euo pipefail

VERSION=${1:-}
if [ -z "$VERSION" ]; then
    echo "Usage: $0 X.Y.Z" >&2
    exit 1
fi

PROD_HOST=${PROD_HOST:-honestjung@cdgts.paleobytes.info}
PROD_DEPLOY=${PROD_DEPLOY:-/srv/scoremate/deploy-prod.sh}

echo "=== remote deploy → ${PROD_HOST}:${PROD_DEPLOY} $* ==="
# PRUNE_KEEP: 배포 뒤 남길 이미지 수(기본 3, 0 = 정리 안 함) — 원격 deploy.sh 로 넘긴다
exec ssh "$PROD_HOST" "PRUNE_KEEP=${PRUNE_KEEP:-3}" "$PROD_DEPLOY" "$@"
