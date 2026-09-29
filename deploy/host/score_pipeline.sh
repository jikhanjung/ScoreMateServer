#!/bin/bash
# =============================================================================
# ScoreMate 악보 처리 파이프라인 — 운영 호스트 cron 에서 이것 하나(devlog 072)
#
#   */5 * * * * /srv/scoremate/scripts/score_pipeline.sh >> /srv/scoremate/omr/pipeline.log 2>&1
#
# 새 판마다 ① PDF 분석 → ③ 모델 위치 → ② 악보 인식 을 쪽 단위로 번갈아 처리한다(scripts/score_pipeline.py).
# 예전의 layout_lane.sh · omr_lane.sh · model_layout_lane.sh 셋을 대신한다. 잠금 하나 — 이미 돌고 있으면 그냥 끝난다.
# =============================================================================
set -uo pipefail
ROOT="${SCOREMATE_ROOT:-/srv/scoremate}"
mkdir -p "${ROOT}/omr"
exec 9>"${ROOT}/omr/pipeline.lock"
flock -n 9 || exit 0

# cron 은 비대화형 셸 — nvm 의 codex 가 PATH 에 없다
if ! command -v codex >/dev/null 2>&1; then
    NODE_BIN=$(ls -d "${HOME}"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1)
    [ -n "${NODE_BIN}" ] && export PATH="${NODE_BIN}:${PATH}"
fi
command -v codex >/dev/null 2>&1 || { echo "$(date '+%F %T') ERROR codex CLI 없음"; exit 1; }
VENV="${OMR_VENV:-${ROOT}/omr/venv}"
[ -x "${VENV}/bin/python" ] || { echo "$(date '+%F %T') ERROR ${VENV} 없음"; exit 1; }
cd "${ROOT}" || exit 1
exec "${VENV}/bin/python" "${ROOT}/scripts/score_pipeline.py"
