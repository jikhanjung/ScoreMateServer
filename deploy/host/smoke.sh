#!/bin/bash
# /srv/scoremate/smoke.sh — 배포 계약 `smoke` 동사
# Usage: /srv/scoremate/smoke.sh X.Y.Z
#
# /healthz 200 + 버전 일치 + DB 연결 + 핵심 행 수(user>0 — entrypoint 가 관리자 계정을 보증) 를 결정론적으로 검증.
# 가볍게 유지 — 스테이크 낮으니 무거운 모니터링은 만들지 않는다.
#
# status=="ok" 만 통과시킨다. 그래서 이 스크립트는 **무인 검사가 사람에게 닿는 유일한 채널**이기도
# 하다: hourly backup_db.py 가 DB 손상을 보면 센티넬 → /healthz degraded(200) → 여기서 실패.
# dolfinid crontab 에 MAILTO 가 없어 cron 로그는 아무도 안 읽으므로, 사람이 이미 보는 경로에 물렸다.
#
# HTTPS 리다이렉트는 nginx 담당(Django SECURE_SSL_REDIRECT 미사용)이지만, 관례대로 X-Forwarded-Proto: https 를 실어
# 추후 설정 변경에도 안전하게 로컬(127.0.0.1) 평문 검증한다.
set -euo pipefail

EXPECT_VERSION=${1:-}
if [ -z "$EXPECT_VERSION" ]; then
    echo "Usage: $0 X.Y.Z"
    exit 1
fi

# deploy.sh 와 동일하게 .env HOST_PORT(기본 8016) 사용.
HOST_PORT=$(sed -n 's/^HOST_PORT=//p' /srv/scoremate/.env 2>/dev/null || true)
HOST_PORT=${HOST_PORT:-8016}
URL="${SMOKE_URL:-http://127.0.0.1:${HOST_PORT}/healthz}"

echo "=== smoke: GET $URL (expect $EXPECT_VERSION) ==="

BODY=$(curl -fsS -m 5 \
    -H "X-Forwarded-Proto: https" \
    "$URL") || { echo "FAIL: /healthz 요청 실패 (연결/타임아웃/HTTP 오류)"; exit 1; }

echo "  response: $BODY"

# stdlib python3 로 JSON 검증 (호스트에 jq 의존 안 함)
EXPECT_VERSION="$EXPECT_VERSION" python3 - "$BODY" <<'PY'
import json, os, sys
body = sys.argv[1]
expect = os.environ["EXPECT_VERSION"]
try:
    d = json.loads(body)
except Exception as e:
    print(f"FAIL: JSON 파싱 불가 — {e}")
    sys.exit(1)

errs = []
if d.get("status") == "degraded":
    # hourly backup_db.py 의 PRAGMA integrity_check 실패 → DB 옆 센티넬. 배포 문제가 아니다.
    print("FAIL: status=degraded — **운영 DB 손상 감지**(배포 자체 문제 아님, 롤백은 답이 아닐 수 있음)")
    print(f"  {d.get('integrity')}")
    print("  · 백업 로테이션 prune 은 이미 중단됨 — /srv/scoremate/backup/ 의 과거 스냅샷이 복구 후보")
    print("  · 증거 사본: /srv/scoremate/backup/scoremate_INTEGRITY_FAIL.corrupt")
    print("  · 확인: sqlite3 /srv/scoremate/db/db.sqlite3 'PRAGMA integrity_check'")
    print("  · 복구 후 다음 정시 검사가 통과하면 센티넬은 자동 해제(급하면 rm /srv/scoremate/db/INTEGRITY_FAIL)")
    sys.exit(1)
if d.get("status") != "ok":
    errs.append(f"status={d.get('status')!r} (기대 'ok', error={d.get('error')!r})")
if d.get("db") is not True:
    errs.append(f"db={d.get('db')!r} (기대 True)")
if d.get("version") != expect:
    errs.append(f"version={d.get('version')!r} (기대 {expect!r})")
# 도메인 불변식 1개: 사용자 행 수>0 (entrypoint 가 관리자 계정을 보증 — 0 이면 빈 DB 에 붙은 것)
user = (d.get("counts") or {}).get("user")
if not isinstance(user, int) or user <= 0:
    errs.append(f"counts.user={user!r} (기대 정수>0)")

if errs:
    print("FAIL:")
    for e in errs:
        print(f"  - {e}")
    sys.exit(1)
c = d.get('counts') or {}
print(f"PASS: version={expect}, db=ok, user={user}, score={c.get('score')}, ensemble={c.get('ensemble')}")
PY

echo "=== smoke OK ==="
