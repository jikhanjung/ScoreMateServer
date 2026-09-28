#!/bin/bash
# =============================================================================
# ScoreMate 모델 위치 레인 — 운영 호스트 cron. 한 번에 판 하나. devlog 070 · 071
#
#   */10 * * * * /srv/scoremate/scripts/model_layout_lane.sh >> /srv/scoremate/omr/model_layout.log 2>&1
#
# 쪽마다 Codex CLI(gpt-6-astra)가 시스템 · 보표 · 마디선 · 보표 이름 · 박자표를 0..1000 좌표로 읽고(scripts/model_layout.py),
# 컨테이너가 pt · 앱 ScoreLayout 모양으로 바꿔 저장한다(manage.py model_layout_ingest). 벡터 PDF 는 PDF 분석의 검산,
# 스캔 PDF 는 이것이 기기에 내려가는 layout 이 된다. 악보 인식 레인(omr_lane.sh)과 따로 돈다(잠금 · 로그 · 작업 폴더가 다르다).
# =============================================================================
set -uo pipefail

ROOT="${SCOREMATE_ROOT:-/srv/scoremate}"
OMR="${ROOT}/omr"
VENV="${OMR_VENV:-${OMR}/venv}"
MAX_TRIES=3
mkdir -p "${OMR}/model_layout"

exec 9>"${OMR}/model_layout.lock"
flock -n 9 || exit 0

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

if ! command -v codex >/dev/null 2>&1; then
    NODE_BIN=$(ls -d "${HOME}"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1)
    [ -n "${NODE_BIN}" ] && export PATH="${NODE_BIN}:${PATH}"
fi
command -v codex >/dev/null 2>&1 || { log "ERROR codex CLI 없음"; exit 1; }
[ -x "${VENV}/bin/python" ] || { log "ERROR ${VENV} 없음"; exit 1; }

cd "${ROOT}" || exit 1
DB_UID=$(stat -c %u "${ROOT}/db")
manage() { docker compose exec -T -u "${DB_UID}" api python manage.py "$@"; }

JOB=$(manage model_layout_pending --limit 1 2>/dev/null | sed -n 's/^MLAYOUT_JOB //p' | head -1)
[ -z "${JOB}" ] && exit 0

field() { printf '%s' "${JOB}" | python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }
VID=$(field version_id); KEY=$(field key); SHA=$(field sha256); TITLE=$(field title)
PDF="${ROOT}/files/${KEY}"
WORK="${OMR}/model_layout/v${VID}"
mkdir -p "${WORK}"

if [ "$(sha256sum "${PDF}" 2>/dev/null | cut -d' ' -f1)" != "${SHA}" ]; then
    log "ERROR v${VID} ${TITLE}: 파일 sha256 불일치 또는 없음 — 건너뜀"
    exit 1
fi

log "START v${VID} ${TITLE}"
"${VENV}/bin/python" "${ROOT}/scripts/model_layout.py" "${PDF}" "${WORK}" >> "${WORK}/run.log" 2>&1
RC=$?

if [ "${RC}" -eq 0 ] || [ "${RC}" -eq 3 ]; then
    :
elif tail -n 50 "${WORK}/run.log" | grep -qiE '401|unauthori[sz]ed|log ?in|refresh token'; then
    log "ERROR codex 로그인 필요 — codex logout && codex login --device-auth. v${VID} 는 그대로 대기"
    exit 1
else
    TRIES=$(( $(cat "${WORK}/tries" 2>/dev/null || echo 0) + 1 ))
    echo "${TRIES}" > "${WORK}/tries"
    if [ "${TRIES}" -lt "${MAX_TRIES}" ]; then
        log "RETRY v${VID} ${TITLE}: 실행 실패 rc=${RC} (${TRIES}/${MAX_TRIES})"
        exit 1
    fi
    printf '{"status": "failed", "problems": ["could not run (rc=%s)"]}' "${RC}" > "${WORK}/result.json"
fi

python3 - "${VID}" "${SHA}" "${WORK}" <<'PY' | manage model_layout_ingest && log "DONE v${VID} ${TITLE}: rc=${RC}" || { log "ERROR v${VID}: model_layout_ingest 실패 — ${WORK} 보존"; exit 1; }
import json, sys
from pathlib import Path
vid, sha, work = int(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
result = json.loads((work / 'result.json').read_text())
print(json.dumps({'version_id': vid, 'sha256': sha, **result}, ensure_ascii=False))
PY
