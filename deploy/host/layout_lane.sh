#!/bin/bash
# =============================================================================
# ScoreMate 보표 · 마디 분석 레인 — 운영 호스트 cron. 분석 파일이 없는 판을 채운다(scores/layouts.py, 앱 분석을 옮긴 것)
#
#   */5 * * * * /srv/scoremate/scripts/layout_lane.sh >> /srv/scoremate/omr/layout.log 2>&1
#
# 올리기 요청 안에서 돌리지 않는 이유: 35쪽 악보에 수 초 — 올리기가 늦어진다. 분석은 컨테이너 코드가 한다(모델 호출 없음).
# =============================================================================
set -uo pipefail
ROOT="${SCOREMATE_ROOT:-/srv/scoremate}"
mkdir -p "${ROOT}/omr"
exec 9>"${ROOT}/omr/layout.lock"
flock -n 9 || exit 0
cd "${ROOT}" || exit 1
OUT=$(docker compose exec -T -u "$(stat -c %u db)" api python manage.py score_layout 2>/dev/null | grep -E '^LAYOUT')
[ -n "${OUT}" ] && echo "${OUT}" | sed "s/^/$(date '+%Y-%m-%d %H:%M:%S') /"
exit 0
