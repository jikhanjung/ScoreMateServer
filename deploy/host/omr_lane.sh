#!/bin/bash
# =============================================================================
# ScoreMate 악보 인식(OMR) 레인 — 운영 호스트 cron. 한 번에 판 하나. devlog P01 · deploy/README.md §악보 인식
#
#   */10 * * * * /srv/scoremate/scripts/omr_lane.sh >> /srv/scoremate/omr/lane.log 2>&1
#
# 1. 컨테이너에 묻는다: manage.py omr_pending  → 인식할 판(키 · sha256)
# 2. 호스트에서 PDF 를 읽어 scripts/astra_musicxml.py 가 Codex CLI(gpt-6-astra, ChatGPT 로그인)로 MusicXML 을 만든다
#    — codex 로그인과 구독 한도는 이 호스트 사용자의 것. 컨테이너에는 codex 를 넣지 않는다(fsis2026 · ocrserver 와 같은 방식)
# 3. 결과를 컨테이너에 넘긴다: manage.py omr_ingest (표준 입력 JSON) → 판의 분석 + files/…/omr/v<N>.musicxml
#
# 긴 작업(쪽당 수 분)이라 flock 으로 겹치지 않게 한다. 조각 결과는 omr/work/v<ID>/ 에 남아 다음 실행이 이어서 한다.
# 인식 결과가 검산을 통과하지 못하면(종료 3) 실패로 기록하고 다시 부르지 않는다 — 다시 하려면 웹 admin 에서 그 분석을 지운다.
# 돌리지 못한 경우(codex 없음 · 로그인 · 시간 초과)는 기록하지 않고 다음 실행에서 다시 — 같은 판이 MAX_TRIES 번 넘게 그러면 실패로 기록.
# =============================================================================
set -uo pipefail

ROOT="${SCOREMATE_ROOT:-/srv/scoremate}"
OMR="${ROOT}/omr"
VENV="${OMR_VENV:-${OMR}/venv}"
MAX_TRIES=3
mkdir -p "${OMR}/work"

exec 9>"${OMR}/lane.lock"
flock -n 9 || exit 0

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

# cron 은 비대화형 셸 — nvm 의 node/codex 가 PATH 에 없다(fsis2026 P37 의 첫 cron 실패 원인)
if ! command -v codex >/dev/null 2>&1; then
    NODE_BIN=$(ls -d "${HOME}"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1)
    [ -n "${NODE_BIN}" ] && export PATH="${NODE_BIN}:${PATH}"
fi
command -v codex >/dev/null 2>&1 || { log "ERROR codex CLI 없음 — npm i -g @openai/codex 후 codex login"; exit 1; }
[ -x "${VENV}/bin/python" ] || { log "ERROR ${VENV} 없음 — python3 -m venv ${VENV} && ${VENV}/bin/pip install music21 pymupdf"; exit 1; }

cd "${ROOT}" || exit 1
DB_UID=$(stat -c %u "${ROOT}/db")
manage() { docker compose exec -T -u "${DB_UID}" api python manage.py "$@"; }

JOB=$(manage omr_pending --limit 1 2>/dev/null | sed -n 's/^OMR_JOB //p' | head -1)
[ -z "${JOB}" ] && exit 0

field() { printf '%s' "${JOB}" | python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }
VID=$(field version_id); KEY=$(field key); SHA=$(field sha256); TITLE=$(field title)
PDF="${ROOT}/files/${KEY}"
WORK="${OMR}/work/v${VID}"
mkdir -p "${WORK}"

# 호스트가 읽는 파일이 그 판의 파일인지 — 아니면 넘기지 않는다(ingest 도 한 번 더 확인한다)
ACTUAL=$(sha256sum "${PDF}" 2>/dev/null | cut -d' ' -f1)
if [ "${ACTUAL}" != "${SHA}" ]; then
    log "ERROR v${VID} ${TITLE}: 파일 sha256 불일치 또는 없음 (${PDF}) — 건너뜀"
    exit 1
fi

log "START v${VID} ${TITLE} (${KEY})"
"${VENV}/bin/python" "${ROOT}/scripts/astra_musicxml.py" "${PDF}" "${WORK}" >> "${WORK}/run.log" 2>&1
RC=$?

bundle() {   # status → 표준 출력 JSON (omr_ingest 입력)
    "${VENV}/bin/python" - "$1" "${VID}" "${SHA}" "${WORK}" <<'PY'
import json, sys
from pathlib import Path
status, vid, sha, work = sys.argv[1], int(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
result = json.loads((work / 'result.json').read_text()) if (work / 'result.json').exists() else {}
bundle = {'version_id': vid, 'sha256': sha, 'status': status, 'run': result.get('run', {}),
          'problems': result.get('problems', []), 'metadata': result.get('metadata', {})}
if not bundle['metadata'] and (work / 'metadata.json').exists():
    bundle['metadata'] = json.loads((work / 'metadata.json').read_text())
if status == 'ok':
    bundle['musicxml'] = (work / 'score.musicxml').read_text(encoding='utf-8')
else:
    tail = (work / 'run.log').read_text(errors='replace').splitlines()[-5:] if (work / 'run.log').exists() else []
    bundle['problems'] = bundle['problems'] or tail
print(json.dumps(bundle, ensure_ascii=False))
PY
}

if [ "${RC}" -eq 0 ]; then
    STATUS=ok
elif [ "${RC}" -eq 3 ]; then
    STATUS=failed
elif tail -n 50 "${WORK}/run.log" | grep -qiE '401|unauthori[sz]ed|log ?in|refresh token'; then
    # 로그인 문제는 악보 탓이 아니다 — 시도 횟수에 넣지 않는다(넣으면 로그인이 풀린 사이 멀쩡한 악보가 '실패'로 기록된다)
    log "ERROR codex 로그인 필요(토큰 만료?) — codex logout && codex login --device-auth. v${VID} 는 그대로 대기"
    exit 1
else
    TRIES=$(( $(cat "${WORK}/tries" 2>/dev/null || echo 0) + 1 ))
    echo "${TRIES}" > "${WORK}/tries"
    if [ "${TRIES}" -lt "${MAX_TRIES}" ]; then
        log "RETRY v${VID} ${TITLE}: 실행 실패 rc=${RC} (${TRIES}/${MAX_TRIES}) — ${WORK}/run.log"
        exit 1
    fi
    STATUS=failed
fi

if bundle "${STATUS}" | manage omr_ingest; then
    log "DONE v${VID} ${TITLE}: ${STATUS} (rc=${RC})"
else
    log "ERROR v${VID} ${TITLE}: omr_ingest 실패 — ${WORK} 에 결과 보존"
    exit 1
fi
