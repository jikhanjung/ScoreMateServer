"""Score PDF -> MusicXML via Codex CLI (gpt-6-astra), a few pages per call, then merged into one score.

Same call shape as fsis2026 scripts/astra_cli_bbox.py: ChatGPT login (API keys removed), read-only sandbox,
--output-schema + --output-last-message. Experimental (devlog P01) — not used by the server.

    ~/venv/omr/bin/python tools/omr/astra_musicxml.py score.pdf out/score7 [--chunk 2] [--effort high]

Resumable: each chunk is kept under out/chunks/; rerunning skips finished chunks.
Each chunk must keep the part list of chunk 1 and every voice of every measure must fill its time signature;
a chunk that fails is retried once with the error, then the run stops (nothing is guessed).

Writes out/result.json — {"status": "ok"|"failed", "problems": [...], "run": {...}} — and exits
0 = ok (out/score.musicxml), 3 = transcription failed the checks (a verdict: do not retry),
4 = paused by --budget-pages (more pages to do — run again), anything else = could not run (codex missing, login, timeout).
"""
import argparse
import copy
import json
import os
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

import pymupdf

try:
    from . import omr_compact
except ImportError:
    import omr_compact

MODEL = 'gpt-6-astra'
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': ['musicxml', 'first_measure', 'last_measure', 'notes'],
          'properties': {'musicxml': {'type': 'string'}, 'first_measure': {'type': 'integer'},
                         'last_measure': {'type': 'integer'}, 'notes': {'type': 'string'}}}

PROMPT = """You are an optical music recognition engine. The attached images are consecutive pages {pages} (of {total})
of one printed score. Transcribe EVERYTHING on these pages into a single MusicXML 4.0 score-partwise document:
every part, every measure, clefs, key and time signatures, tempo and expression text, dynamics, every note and rest
with correct pitch (including accidentals and the key signature), duration, dots, ties, tuplets, chords,
articulations, slurs, and voices (use <backup> when a staff has more than one voice; use <staves>/<staff> for
multi-staff instruments such as piano).
Rules:
- Every voice of every measure must add up exactly to the time signature (pickup measures: implicit="yes").
- The FIRST measure of your document must carry full <attributes> for every part: divisions, key, time, clef(s),
  staves if more than one — even if they are not reprinted on this page.
- Do not invent content. If something is unreadable, transcribe your best reading and say so in notes.
- Inspect the attached images directly. Do not read other files, run commands, or use external tools.
{context}
Return JSON: musicxml (the whole document as a string), first_measure and last_measure (measure numbers you used),
notes (uncertainties, page by page)."""

COMPACT_PROMPT = """You are an optical music recognition engine. The attached images are consecutive pages {pages} (of {total})
of one printed score. Transcribe EVERYTHING on these pages: every part, every measure, clefs, key and time signatures,
tempo and expression text, dynamics, every note and rest with correct pitch and duration, dots, ties, tuplets, chords,
grace notes, articulations, slurs, and voices (a second voice on the same staff = another entry in "voices";
the second staff of a piano/harp part = "staff": 2).

Write it in this COMPACT form (not MusicXML — the program builds MusicXML from it):
{format_help}
Rules:
- Every voice of every measure must add up exactly to the time signature (a pickup measure: "implicit": true).
- The FIRST measure on these pages must give full attributes for every part (key, time, clef — and clef2 for a second
  staff) even if they are not reprinted on the page. After that, give attributes only where something changes.
- Each measure lists every part (use "R" for a whole-measure rest). Keep voice numbers stable from measure to measure.
- system_start: true on the first measure of every printed line (system) on the page, false otherwise.
- Do not invent content. If something is unreadable, transcribe your best reading and say so in notes.
- Inspect the attached images directly. Do not read other files, run commands, or use external tools.
{context}
Return JSON matching the schema: parts, measures, first_measure and last_measure (measure numbers you used),
notes (uncertainties, page by page)."""

META_SCHEMA = {'type': 'object', 'additionalProperties': False,
               'required': ['title', 'subtitle', 'composer', 'arranger', 'lyricist', 'instrumentation', 'part_name',
                            'parts', 'key_fifths', 'time', 'notes'],
               'properties': {k: {'type': 'string'} for k in ('title', 'subtitle', 'composer', 'arranger', 'lyricist',
                                                              'instrumentation', 'part_name', 'time', 'notes')} |
               {'parts': {'type': 'array', 'items': {'type': 'string'}}, 'key_fifths': {'type': 'integer'}}}

META_PROMPT = """The attached image is the first page of a printed music score. Read the header and the staff labels and
return JSON with exactly what is PRINTED (empty string when absent — never guess from general knowledge):
title, subtitle, composer, arranger (incl. "arr." / "편곡"), lyricist, instrumentation (e.g. "Guitar ensemble",
"Piano solo", "String quartet" — describe the parts you see), part_name ("Full Score" if all parts are shown together,
otherwise the single part printed, e.g. "Violin I"), parts (the staff names in order),
key_fifths (the key signature at the start of the FIRST staff: number of sharps, or minus the number of flats — count
each accidental in the signature carefully, 0 if none), time (the time signature there, e.g. "6/8"), notes.
Inspect the attached image directly. Do not read other files, run commands, or use external tools."""

FIRST_CONTEXT = """- These are the first pages. Part ids P1, P2, … in score order. Number measures as printed (a pickup measure is 0).
- Part names: ONLY the names printed at the start of the staves. If a staff has no printed name, call it "Staff 1",
  "Staff 2", … in order. NEVER infer instruments from the title, subtitle or composer (a piece titled for piano may be
  arranged for guitars). One part = one staff, unless one printed name (e.g. "Piano") spans two staves joined by a brace.{staves}"""
STAVES_CONTEXT = """
- Measured from the PDF drawing: every system here has exactly {count} staves. Your parts' staves must add up to {count}."""
PAGE_SYSTEMS_CONTEXT = """
- Measured from the PDF drawing: this page has {count} systems (printed lines) — mark system_start on the first measure of each."""

NEXT_CONTEXT = """- This continues a transcription already made from the previous pages. Use EXACTLY these parts, ids and order
  (a part may be printed with an abbreviated name or be absent on a page — still include it, filling absent measures
  with whole-measure rests):
{parts}
- The previous pages ended with measure {last}. Continue numbering from {next} unless the printed measure numbers
  say otherwise.
- State at the end of the previous pages (carry it into your first measure's attributes):
{state}"""


def page_systems(args, pages):
    """보표 분석이 잰 이 쪽의 시스템 수 — 한 쪽 호출이고 값이 있을 때만(0 = 악보가 아닌 쪽은 검사하지 않는다)"""
    if not args.page_systems or len(pages) != 1:
        return None
    counts = [int(c) for c in args.page_systems.split(',') if c.strip().isdigit()]
    if pages[0] > len(counts) or counts[pages[0] - 1] == 0:
        return None
    return counts[pages[0] - 1]


def key_disagreement(page, meta):
    """첫 쪽의 조표를 곡 정보 호출(따로 읽은 것)과 맞춘다 — 조표를 잘못 세면 그 음이 모두 틀린다(K488: 샵 2 를 3 으로)"""
    if not isinstance(meta.get('key_fifths'), int) or not page.get('measures'):
        return []
    first = page['measures'][0].get('parts') or []
    spec = next((p.get('attributes', '') for p in first if 'key=' in p.get('attributes', '')), '')
    match = re.search(r'key=(-?\d+)', spec)
    if match and int(match.group(1)) != meta['key_fifths']:
        return [f'key signature: you wrote key={match.group(1)}, an independent reading of the first staff found '
                f'key={meta["key_fifths"]} — count the sharps/flats of the key signature again and make every pitch '
                f'agree with the correct one']
    return []


def compact_state(state):
    """end_state 한 파트 → 'key=2 time=6/8 clef=G2-8' (짧은 형식의 attributes 와 같은 꼴)"""
    items = []
    if state.get('key') is not None:
        items.append(f"key={state['key']}")
    if state.get('time'):
        items.append(f"time={state['time']}")
    for number, clef in sorted(state.get('clefs', {}).items()):
        match = re.fullmatch(r'([GFC])(\d)(-?\d*)', clef)
        text = clef
        if match and match.group(3):
            change = int(match.group(3))
            text = f"{match.group(1)}{match.group(2)}{'-' if change < 0 else '+'}{8 if abs(change) == 1 else 15}"
        items.append(f"{'clef' if number == '1' else 'clef' + number}={text}")
    if state.get('staves'):
        items.append(f"staves={state['staves']}")
    return ' '.join(items)


def time_state(merged):
    """다음 쪽을 짧은 형식에서 바꿀 때 — 박자표가 다시 적히지 않은 마디의 길이"""
    result = {}
    for pid, s in end_state(merged).items():
        if s.get('time'):
            beats, beat_type = s['time'].split('/')
            result[pid] = {'time': Fraction(int(beats) * 4, int(beat_type))}
    return result


def run(command, prompt, timeout):
    env = {k: v for k, v in os.environ.items() if k not in ('OPENAI_API_KEY', 'CODEX_API_KEY')}
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, env=env, start_new_session=True)
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout)
        return process.returncode, stdout, stderr
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise


def call_astra(images, prompt, workdir, effort, timeout, schema=SCHEMA):
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / 'schema.json').write_text(json.dumps(schema))
    (workdir / 'prompt.txt').write_text(prompt, encoding='utf-8')
    response = workdir / 'response.json'
    response.unlink(missing_ok=True)
    command = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
               '--sandbox', 'read-only', '--model', MODEL, '-c', f'model_reasoning_effort="{effort}"']
    for image in images:
        command += ['--image', str(image)]
    command += ['--output-schema', str(workdir / 'schema.json'), '--output-last-message', str(response), '--json', '-']
    start = time.monotonic()
    code, stdout, stderr = run(command, prompt, timeout)
    (workdir / 'events.jsonl').write_text(stdout)
    (workdir / 'stderr.log').write_text(stderr)
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if code or not any(e.get('type') == 'turn.completed' for e in events):
        tail = ' | '.join((stderr or '').strip().splitlines()[-3:])   # 로그인 만료(401)를 레인이 알아보게 run.log 에 남긴다
        raise RuntimeError(f'codex failed (exit {code}): {tail} — see {workdir}/stderr.log')
    usage = [e.get('usage') for e in events if e.get('type') == 'turn.completed']
    return json.loads(response.read_text()), round(time.monotonic() - start, 1), usage


# ---- MusicXML helpers (plain ElementTree; music21 only for the duration check) ----

def parts_of(root):
    names = {sp.get('id'): (sp.findtext('part-name') or '').strip() for sp in root.iter('score-part')}
    return [(p.get('id'), names.get(p.get('id'), '')) for p in root.findall('part')]


def end_state(root):
    """Last divisions/key/time/clef(s) per part — handed to the next chunk and used to drop repeated attributes."""
    state = {}
    for part in root.findall('part'):
        s = {'clefs': {}}
        for attributes in part.iter('attributes'):
            for tag in ('divisions', 'staves'):
                if attributes.find(tag) is not None:
                    s[tag] = attributes.findtext(tag)
            if attributes.find('key') is not None:
                s['key'] = attributes.find('key').findtext('fifths')
            if attributes.find('time') is not None:
                s['time'] = f"{attributes.find('time').findtext('beats')}/{attributes.find('time').findtext('beat-type')}"
            for clef in attributes.findall('clef'):
                s['clefs'][clef.get('number', '1')] = f"{clef.findtext('sign')}{clef.findtext('line') or ''}" \
                    f"{clef.findtext('clef-octave-change') or ''}"
        state[part.get('id')] = s
    return state


def last_measure(root):
    numbers = [m.get('number') for m in root.find('part').findall('measure')]
    return numbers[-1] if numbers else '0'


def check(xml_text, expected_parts=None):
    """Problems as text; empty list = passed"""
    import music21
    problems = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return [f'not well-formed XML: {exc}']
    got = [pid for pid, _ in parts_of(root)]
    if expected_parts and got != expected_parts:
        problems.append(f'parts {got} != expected {expected_parts}')
    counts = {pid: len(root.find(f"part[@id='{pid}']").findall('measure')) for pid in got}
    if len(set(counts.values())) > 1:
        problems.append(f'measure count differs between parts: {counts}')
    try:
        score = music21.converter.parse(xml_text, format='musicxml')
    except Exception as exc:  # noqa: BLE001 — any parser failure is a transcription problem
        return problems + [f'music21 could not parse: {type(exc).__name__}: {exc}']
    for part in score.parts:
        ts = None
        for measure in part.getElementsByClass('Measure'):
            ts = measure.timeSignature or ts
            if ts is None:
                problems.append(f'{part.partName}: no time signature')
                break
            want = Fraction(ts.barDuration.quarterLength)
            for voice in (measure.voices or [measure]):
                got_len = sum(Fraction(e.quarterLength) for e in voice.notesAndRests)
                full_rest = len(voice.notesAndRests) == 1 and voice.notesAndRests[0].isRest
                if got_len != want and not full_rest and got_len > 0:
                    short_ok = got_len < want and measure is part.getElementsByClass('Measure')[0]
                    short_ok = short_ok or (got_len < want and measure is part.getElementsByClass('Measure')[-1])
                    if not short_ok:
                        problems.append(f'{part.partName} m{measure.number}: {got_len} quarters, time signature wants {want}')
    return problems[:30]


def merge(base, chunk):
    """Append chunk measures to base part by part, dropping attributes that only repeat the running state"""
    state = end_state(base)
    for part in chunk.findall('part'):
        target = base.find(f"part[@id='{part.get('id')}']")
        s = state[part.get('id')]
        measures = part.findall('measure')
        if measures:
            attributes = measures[0].find('attributes')
            if attributes is not None:
                for tag, current in (('divisions', s.get('divisions')), ('staves', s.get('staves'))):
                    el = attributes.find(tag)
                    if el is not None and el.text == current:
                        attributes.remove(el)
                key = attributes.find('key')
                if key is not None and key.findtext('fifths') == s.get('key'):
                    attributes.remove(key)
                t = attributes.find('time')
                if t is not None and f"{t.findtext('beats')}/{t.findtext('beat-type')}" == s.get('time'):
                    attributes.remove(t)
                for clef in attributes.findall('clef'):
                    sig = f"{clef.findtext('sign')}{clef.findtext('line') or ''}{clef.findtext('clef-octave-change') or ''}"
                    if s['clefs'].get(clef.get('number', '1')) == sig:
                        attributes.remove(clef)
                if len(attributes) == 0:
                    measures[0].remove(attributes)
        for measure in measures:
            target.append(copy.deepcopy(measure))


def render(pdf, pages, outdir, dpi):
    images = []
    for number in pages:
        image = outdir / 'pages' / f'page{number:03d}.png'
        if not image.exists():
            image.parent.mkdir(parents=True, exist_ok=True)
            pdf[number - 1].get_pixmap(dpi=dpi).save(image)
        images.append(image)
    return images


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('outdir', type=Path)
    parser.add_argument('--chunk', type=int, default=1, help='pages per call (1 — 2 쪽 호출은 느리고 깨지기 쉬웠다, devlog 064)')
    parser.add_argument('--effort', default='high', choices=('low', 'medium', 'high', 'xhigh', 'max'),
                        help='high — 짧은 형식 · medium 은 K488 1쪽 조표를 샵 3 으로 잘못 읽었다(devlog 064)')
    parser.add_argument('--dpi', type=int, default=200)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--pages', help='only these pages, e.g. 1-4 (for trials)')
    parser.add_argument('--budget-pages', type=int, default=0,
                        help='stop after this many newly transcribed calls (exit 4 = more to do); 0 = all')
    parser.add_argument('--staves', type=int, help='staves per system measured by the layout analysis (checks the part list)')
    parser.add_argument('--page-systems', help='systems per page from the layout analysis, e.g. 2,2,3 (checks system_start)')
    parser.add_argument('--format', default='compact', choices=('compact', 'musicxml'),
                        help='what the model writes: compact (short text → we build MusicXML, ~4x fewer tokens) or musicxml')
    args = parser.parse_args()

    pdf = pymupdf.open(args.pdf)
    total = len(pdf)
    first, last = (map(int, args.pages.split('-')) if args.pages else (1, total))
    chunks = [list(range(p, min(p + args.chunk, last + 1))) for p in range(first, last + 1, args.chunk)]
    log = args.outdir / 'log.jsonl'
    args.outdir.mkdir(parents=True, exist_ok=True)

    # 곡 정보(제목 · 작곡 · 편곡 …) — 첫 쪽만, 가볍게. 서버 고치기 화면의 제안이 된다
    meta_file = args.outdir / 'metadata.json'
    if not meta_file.exists():
        images = render(pdf, [1], args.outdir, args.dpi)
        meta, elapsed, _ = call_astra(images, META_PROMPT, args.outdir / 'chunks' / '000_metadata', 'medium',
                                      args.timeout, META_SCHEMA)
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'metadata: {elapsed}s {meta.get("title")!r} / {meta.get("composer")!r} / {meta.get("arranger")!r} '
              f'key={meta.get("key_fifths")} time={meta.get("time")}', flush=True)
    meta = json.loads(meta_file.read_text())

    merged = None
    ties = omr_compact.TieState()       # 쪽을 넘는 붙임줄 — 짧은 형식을 바꿀 때 이어 간다
    queue = list(chunks)
    new_chunks = 0
    while queue:
        pages = queue.pop(0)
        name = f'p{pages[0]:03d}-{pages[-1]:03d}'
        workdir = args.outdir / 'chunks' / name
        done, end = finished_from(args.outdir, pages[0])
        if done is not None:
            # 이미 끝난 조각 — 쪽 수가 지금 설정과 달라도(예전 두 쪽 조각) 그대로 쓰고 그만큼 건너뛴다
            compact = done.parent / 'chunk.json'
            if compact.exists():     # 짧은 형식으로 끝난 조각 — 다시 바꿔 붙임줄 상태를 이어 간다(결과 XML 은 같다)
                xml_text, _ = omr_compact.to_musicxml(json.loads(compact.read_text()), ties,
                                                      time_state(merged) if merged is not None else None,
                                                      new_page=pages[0] > 1)
                chunk = ET.fromstring(xml_text)
            else:
                chunk = ET.parse(done).getroot()
            queue = [group for group in ([p for p in g if p > end] for g in queue) if group]
        else:
            if merged is None:
                context = FIRST_CONTEXT.format(staves=STAVES_CONTEXT.format(count=args.staves) if args.staves else '')
                expected = None
            else:
                expected = [pid for pid, _ in parts_of(merged)]
                parts = '\n'.join(f'  {pid}: {name}' for pid, name in parts_of(merged))
                if args.format == 'compact':
                    state = '\n'.join(f'  {pid}: {compact_state(s)}' for pid, s in end_state(merged).items())
                else:
                    state = '\n'.join(f'  {pid}: {json.dumps(s, ensure_ascii=False)}' for pid, s in end_state(merged).items())
                previous = int(last_measure(merged)) if last_measure(merged).isdigit() else 0
                context = NEXT_CONTEXT.format(parts=parts, last=previous, next=previous + 1, state=state)
            if args.format == 'compact':
                expected_systems = page_systems(args, pages)
                if expected_systems is not None:
                    context += PAGE_SYSTEMS_CONTEXT.format(count=expected_systems)
                prompt = COMPACT_PROMPT.format(pages=pages, total=total, context=context,
                                               format_help=omr_compact.FORMAT_HELP)
                schema = omr_compact.SCHEMA
            else:
                prompt, schema = PROMPT.format(pages=pages, total=total, context=context), SCHEMA
            images = render(pdf, pages, args.outdir, args.dpi)
            result, problems = None, []
            for attempt in (1, 2):
                try:
                    result, elapsed, usage = call_astra(images, prompt, workdir / f'attempt{attempt}', args.effort,
                                                        args.timeout, schema)
                except subprocess.TimeoutExpired:
                    result, problems = None, [f'no answer within {int(args.timeout)}s']
                    log_entry(log, pages, attempt, args.timeout, [], None, problems, '')
                    print(f'pages {pages} attempt {attempt}: timeout', flush=True)
                    if len(pages) > 1:
                        break          # 여러 쪽이면 기다리지 말고 한 쪽씩으로
                    continue
                attempt_ties = omr_compact.TieState(ties)
                if args.format == 'compact':
                    xml_text, problems = omr_compact.to_musicxml(result, attempt_ties,
                                                                 time_state(merged) if merged is not None else None,
                                                                 new_page=pages[0] > 1)
                    result['musicxml'] = xml_text
                    problems = problems + ([] if problems else check(xml_text, expected))
                    if merged is None and attempt == 1:
                        problems += key_disagreement(result, meta)
                    expected_systems = page_systems(args, pages)
                    if expected_systems is not None and omr_compact.systems_on_page(result) != expected_systems:
                        problems.append(f'systems: you marked {omr_compact.systems_on_page(result)} systems (system_start) on '
                                        f'page {pages[0]}, the PDF drawing has {expected_systems} — mark system_start on the '
                                        f'first measure of every printed line')
                    if merged is None and args.staves:
                        total = sum(max(1, int(p.get('staves') or 1)) for p in result.get('parts') or [])
                        if total != args.staves:
                            problems.append(f'staves: your parts have {total} staves in total, but every system has '
                                            f'{args.staves} staves (measured from the PDF) — one part per staff unless a '
                                            f'printed name spans two braced staves')
                else:
                    problems = check(result['musicxml'], expected)
                log_entry(log, pages, attempt, elapsed, usage, result, problems, result['notes'])
                print(f'pages {pages} attempt {attempt}: {elapsed}s '
                      f"m{result['first_measure']}-{result['last_measure']} problems={len(problems)}", flush=True)
                if not problems:
                    break
                prompt = prompt + '\n\nYour previous answer failed these checks — fix them and answer again:\n- ' + \
                    '\n- '.join(problems)
            if problems:
                if len(pages) > 1:
                    # 두 쪽이 한 번에 안 되면 한 쪽씩 — 짧을수록 답이 온전하다(긴 XML 을 JSON 문자열로 쓰다 깨지는 일)
                    print(f'pages {pages}: split into single pages', flush=True)
                    queue[0:0] = [[p] for p in pages]
                    continue
                if result is None:
                    raise RuntimeError(f'page {pages[0]}: no answer within {int(args.timeout)}s twice')   # 실행 문제 — 레인이 다시
                workdir.mkdir(parents=True, exist_ok=True)
                (workdir / 'failed.musicxml').write_text(result['musicxml'])
                print(f'STOP: page {pages[0]} still fails: {problems}', file=sys.stderr)
                write_result(args, 'failed', [f'page {pages[0]}: {p}' for p in problems], log)
                return 3
            workdir.mkdir(parents=True, exist_ok=True)
            if args.format == 'compact':
                ties.clear()
                ties.update(attempt_ties)
                page_data = {k: v for k, v in result.items() if k != 'musicxml'}
                (workdir / 'chunk.json').write_text(json.dumps(page_data, ensure_ascii=False), encoding='utf-8')
            (workdir / 'chunk.musicxml').write_text(result['musicxml'])
            chunk = ET.fromstring(result['musicxml'])
            new_chunks += 1
        if merged is None:
            merged = chunk
        else:
            merge(merged, chunk)
        if args.budget_pages and new_chunks >= args.budget_pages and queue:
            print(f'paused after {new_chunks} new call(s): pages {queue[0][0]}–{queue[-1][-1]} remain', flush=True)
            return 4          # 파이프라인이 다른 일을 끼워 넣고 다음에 이어 한다(끝난 조각은 다시 부르지 않는다)

    xml = ET.tostring(merged, encoding='unicode')
    out = args.outdir / 'score.musicxml'
    out.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + xml, encoding='utf-8')
    problems = check(out.read_text())
    summary = {pid: len(merged.find(f"part[@id='{pid}']").findall('measure')) for pid, _ in parts_of(merged)}
    print(f'-> {out}  parts/measures={summary}  final check problems={problems}')
    write_result(args, 'failed' if problems else 'ok', problems, log)
    return 3 if problems else 0


def finished_from(outdir, start):
    """start 쪽에서 시작하는 끝난 조각 → (경로, 마지막 쪽). 가장 긴 것. 없으면 (None, None)"""
    import re
    found = []
    for path in (outdir / 'chunks').glob('*/chunk.musicxml'):
        match = re.fullmatch(r'(?:p(\d{3})-(\d{3})|\d{3}_p(\d+)-(\d+))', path.parent.name)
        if match:
            first, last = [int(x) for x in (match.groups()[:2] if match.group(1) else match.groups()[2:])]
            if first == start:
                found.append((last, path))
    if not found:
        return None, None
    last, path = max(found)
    return path, last


def finished_chunk(outdir, pages):
    """이미 끝난 조각 — 지금 이름(pNNN-NNN) 또는 예전 이름(NNN_pA-B)"""
    for path in (outdir / 'chunks' / f'p{pages[0]:03d}-{pages[-1]:03d}' / 'chunk.musicxml',
                 *(outdir / 'chunks').glob(f'[0-9][0-9][0-9]_p{pages[0]}-{pages[-1]}/chunk.musicxml')):
        if path.exists():
            return path
    return None


def log_entry(log, pages, attempt, elapsed, usage, result, problems, notes):
    with log.open('a') as f:
        f.write(json.dumps({'pages': pages, 'attempt': attempt, 'elapsed': elapsed, 'usage': usage,
                            'measures': [result['first_measure'], result['last_measure']] if result else None,
                            'problems': problems, 'notes': notes}, ensure_ascii=False) + '\n')


def page_measures(entries):
    """조각마다 어느 쪽이 몇 마디부터 몇 마디까지 — 웹 들어보기가 쪽을 따라 넘긴다. 통과한 시도만, 같은 쪽은 마지막 것"""
    found = {}
    for entry in entries:
        if not entry.get('problems') and entry.get('measures') and entry.get('pages'):
            found[tuple(entry['pages'])] = {'pages': entry['pages'], 'first': entry['measures'][0],
                                            'last': entry['measures'][1]}
    return sorted(found.values(), key=lambda item: item['pages'][0])


def write_result(args, status, problems, log):
    entries = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    usage = {}
    for entry in entries:
        for turn in entry.get('usage') or []:
            for name, value in (turn or {}).items():
                if isinstance(value, int):
                    usage[name] = usage.get(name, 0) + value
    run = {'model': MODEL, 'effort': args.effort, 'dpi': args.dpi, 'pages_per_call': args.chunk, 'format': args.format,
           'calls': len(entries), 'elapsed_seconds': round(sum(e.get('elapsed', 0) for e in entries), 1),
           'usage': usage,
           'notes': [f"pages {e['pages'][0]}-{e['pages'][-1]}: {e['notes']}" for e in entries if e.get('notes')][-40:],
           'page_measures': page_measures(entries)}
    meta_file = args.outdir / 'metadata.json'
    metadata = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    (args.outdir / 'result.json').write_text(json.dumps({'status': status, 'problems': problems, 'run': run,
                                                         'metadata': metadata},
                                                        ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
