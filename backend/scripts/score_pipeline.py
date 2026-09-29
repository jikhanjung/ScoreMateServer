"""ScoreMate score pipeline — the one host-side orchestrator (replaces layout_lane · omr_lane · model_layout_lane). devlog 072

Every current PDF version goes through, in this order:
  ① PDF analysis     manage.py score_layout (in the container, seconds)
  ② model layout     scripts/model_layout.py  — the model reads systems · staves · barlines per page
                     (vector: a cross-check of ① · scanned: the layout devices get)
  ③ recognition      scripts/astra_musicxml.py — PDF → MusicXML, checked against the trusted layout (①, or ② for scans)
The unit of work is **one page**: each model call is one page (--budget-pages 1, exit 4 = more to do), and after every page
the queue is looked at again — a newly uploaded score's early stages cut in between the pages of a long recognition.
Priority: all of ① → one page of ② (shortest score first) → one page of ③ → again, until nothing is left.

Run by cron through deploy/host/score_pipeline.sh (flock — one pipeline at a time):
  */5 * * * * /srv/scoremate/scripts/score_pipeline.sh >> /srv/scoremate/omr/pipeline.log 2>&1
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get('SCOREMATE_ROOT', '/srv/scoremate'))
OMR = ROOT / 'omr'
PYTHON = os.environ.get('OMR_PYTHON', str(OMR / 'venv' / 'bin' / 'python'))
MAX_TRIES = 3
MAX_RUNTIME = float(os.environ.get('PIPELINE_MAX_SECONDS', 3 * 3600))   # cron 이 다시 부르니 한 번에 너무 오래 쥐지 않는다
LOGIN_HINTS = ('401', 'unauthorized', 'unauthorised', 'log in', 'login', 'refresh token')


def log(message):
    print(time.strftime('%Y-%m-%d %H:%M:%S ') + message, flush=True)


def manage(*args, stdin=None):
    uid = str(os.stat(ROOT / 'db').st_uid)
    result = subprocess.run(['docker', 'compose', 'exec', '-T', '-u', uid, 'api', 'python', 'manage.py', *args],
                            cwd=ROOT, input=stdin, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def jobs():
    code, out, err = manage('pipeline_status')
    if code:
        raise RuntimeError(f'pipeline_status failed: {err.strip()[-300:]}')
    return [json.loads(line[len('PIPELINE_JOB '):]) for line in out.splitlines() if line.startswith('PIPELINE_JOB ')]


def pdf_path(job):
    return ROOT / 'files' / job['key']


def sha_ok(job):
    try:
        return hashlib.sha256(pdf_path(job).read_bytes()).hexdigest() == job['sha256']
    except OSError:
        return False


def pages_done(stage, workdir):
    if stage == 'model':
        return len(list((workdir / 'pages').glob('p*.json')))
    done = set()
    for chunk in (workdir / 'chunks').glob('*/chunk.musicxml'):
        name = chunk.parent.name.lstrip('0123456789_').lstrip('p')
        first, _, last = name.partition('-')
        if first.isdigit() and last.isdigit():
            done.update(range(int(first), int(last) + 1))
    return len(done)


def run_step(stage, job):
    """한 쪽 — (결과 코드, 작업 폴더)"""
    if stage == 'model':
        workdir = OMR / 'model_layout' / f"v{job['version_id']}"
        command = [PYTHON, str(ROOT / 'scripts' / 'model_layout.py'), str(pdf_path(job)), str(workdir), '--budget-pages', '1']
    else:
        workdir = OMR / 'work' / f"v{job['version_id']}"
        command = [PYTHON, str(ROOT / 'scripts' / 'astra_musicxml.py'), str(pdf_path(job)), str(workdir), '--budget-pages', '1']
        if job.get('staves'):
            command += ['--staves', str(job['staves'])]
        if job.get('page_systems'):
            command += ['--page-systems', job['page_systems']]
    workdir.mkdir(parents=True, exist_ok=True)
    with (workdir / 'run.log').open('a') as out:
        code = subprocess.call(command, stdout=out, stderr=subprocess.STDOUT)
    return code, workdir


def ingest(stage, job, workdir, status):
    result_file = workdir / 'result.json'
    result = json.loads(result_file.read_text()) if result_file.exists() else {}
    if stage == 'model':
        bundle = {'version_id': job['version_id'], 'sha256': job['sha256'], 'status': status,
                  'pages': result.get('pages'), 'run': result.get('run'), 'problems': result.get('problems')}
        command = 'model_layout_ingest'
    else:
        bundle = {'version_id': job['version_id'], 'sha256': job['sha256'], 'status': status,
                  'run': result.get('run', {}), 'problems': result.get('problems', []), 'metadata': result.get('metadata', {})}
        if not bundle['metadata'] and (workdir / 'metadata.json').exists():
            bundle['metadata'] = json.loads((workdir / 'metadata.json').read_text())
        if status == 'ok':
            bundle['musicxml'] = (workdir / 'score.musicxml').read_text(encoding='utf-8')
        elif not bundle['problems']:
            bundle['problems'] = (workdir / 'run.log').read_text(errors='replace').splitlines()[-5:]
        command = 'omr_ingest'
    code, out, err = manage(command, stdin=json.dumps(bundle, ensure_ascii=False))
    if code:
        raise RuntimeError(f'{command} failed: {err.strip()[-300:]}')
    return out.strip().splitlines()[-1] if out.strip() else ''


def login_problem(workdir):
    tail = (workdir / 'run.log').read_text(errors='replace').lower().splitlines()[-50:]
    return any(hint in line for line in tail for hint in LOGIN_HINTS)


def step(stage, job, skip):
    """한 쪽을 하고 결과를 처리한다. False = 파이프라인을 멈춰야 한다(로그인)"""
    label = f"v{job['version_id']} {job['title']}"
    if not sha_ok(job):
        log(f'ERROR {label}: 파일 sha256 불일치 또는 없음 — 건너뜀')
        skip.add((stage, job['version_id']))
        return True
    code, workdir = run_step(stage, job)
    total = job.get('pages') or 0
    manage('pipeline_progress', str(job['version_id']), stage, str(pages_done(stage, workdir)), str(total))
    name = '위치' if stage == 'model' else '인식'
    if code == 4:
        log(f'{name} {label}: {pages_done(stage, workdir)}/{total}쪽')
        return True
    if code in (0, 3):
        status = 'ok' if code == 0 else 'failed'
        result = ingest(stage, job, workdir, status)
        manage('pipeline_progress', str(job['version_id']), 'done')
        log(f'DONE {name} {label}: {status} — {result}')
        return True
    if login_problem(workdir):
        log('ERROR codex 로그인 필요(토큰 만료?) — codex logout && codex login --device-auth. 파이프라인 멈춤, 악보는 그대로 대기')
        return False
    tries_file = workdir / 'tries'
    tries = int(tries_file.read_text() or 0) + 1 if tries_file.exists() else 1
    tries_file.write_text(str(tries))
    if tries >= MAX_TRIES:
        (workdir / 'result.json').write_text(json.dumps({'status': 'failed', 'problems': [f'could not run (rc={code})']}))
        log(f'DONE {name} {label}: failed — 실행 실패 {tries}번(rc={code}) — {ingest(stage, job, workdir, "failed")}')
    else:
        log(f'RETRY {name} {label}: 실행 실패 rc={code} ({tries}/{MAX_TRIES}) — 다음 실행에서 다시')
        skip.add((stage, job['version_id']))
    return True


def main():
    started = time.monotonic()
    skip = set()           # 이번 실행에서 건너뛸 (단계, 판) — 실행이 실패한 것
    while time.monotonic() - started < MAX_RUNTIME:
        pending = jobs()
        if any(j['pdf'] == 'none' for j in pending):
            code, out, err = manage('score_layout')
            for line in out.splitlines():
                if line.startswith('LAYOUT'):
                    log(f'PDF 분석 {line}')
            if code:
                log(f'ERROR score_layout: {err.strip()[-300:]}')
                return 1
            continue
        model = [j for j in pending if j['model'] == 'none' and ('model', j['version_id']) not in skip]
        if model:
            if not step('model', model[0], skip):
                return 1
            continue
        omr = [j for j in pending if j['model'] != 'none' and j['omr'] == 'none' and ('omr', j['version_id']) not in skip]
        if omr:
            if not step('omr', omr[0], skip):
                return 1
            continue
        return 0
    log('시간 한도 — 다음 cron 에서 이어 한다')
    return 0


if __name__ == '__main__':
    sys.exit(main())
