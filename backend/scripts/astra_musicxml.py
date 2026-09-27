"""Score PDF -> MusicXML via Codex CLI (gpt-6-astra), a few pages per call, then merged into one score.

Same call shape as fsis2026 scripts/astra_cli_bbox.py: ChatGPT login (API keys removed), read-only sandbox,
--output-schema + --output-last-message. Experimental (devlog P01) — not used by the server.

    ~/venv/omr/bin/python tools/omr/astra_musicxml.py score.pdf out/score7 [--chunk 2] [--effort high]

Resumable: each chunk is kept under out/chunks/; rerunning skips finished chunks.
Each chunk must keep the part list of chunk 1 and every voice of every measure must fill its time signature;
a chunk that fails is retried once with the error, then the run stops (nothing is guessed).

Writes out/result.json — {"status": "ok"|"failed", "problems": [...], "run": {...}} — and exits
0 = ok (out/score.musicxml), 3 = transcription failed the checks (a verdict: do not retry),
anything else = could not run (codex missing, login, timeout — retry later).
"""
import argparse
import copy
import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

import pymupdf

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

META_SCHEMA = {'type': 'object', 'additionalProperties': False,
               'required': ['title', 'subtitle', 'composer', 'arranger', 'lyricist', 'instrumentation', 'part_name',
                            'parts', 'notes'],
               'properties': {k: {'type': 'string'} for k in ('title', 'subtitle', 'composer', 'arranger', 'lyricist',
                                                              'instrumentation', 'part_name', 'notes')} |
               {'parts': {'type': 'array', 'items': {'type': 'string'}}}}

META_PROMPT = """The attached image is the first page of a printed music score. Read the header and the staff labels and
return JSON with exactly what is PRINTED (empty string when absent — never guess from general knowledge):
title, subtitle, composer, arranger (incl. "arr." / "편곡"), lyricist, instrumentation (e.g. "Guitar ensemble",
"Piano solo", "String quartet" — describe the parts you see), part_name ("Full Score" if all parts are shown together,
otherwise the single part printed, e.g. "Violin I"), parts (the staff names in order), notes.
Inspect the attached image directly. Do not read other files, run commands, or use external tools."""

FIRST_CONTEXT = """- These are the first pages. Use the instrument names printed at the left as part names, part ids P1, P2, …
  in score order. Number measures as printed (a pickup measure is 0)."""

NEXT_CONTEXT = """- This continues a transcription already made from the previous pages. Use EXACTLY these parts, ids and order
  (a part may be printed with an abbreviated name or be absent on a page — still include it, filling absent measures
  with whole-measure rests):
{parts}
- The previous pages ended with measure {last}. Continue numbering from {next} unless the printed measure numbers
  say otherwise.
- State at the end of the previous pages (carry it into your first measure's <attributes>):
{state}"""


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
    parser.add_argument('--chunk', type=int, default=2, help='pages per call')
    parser.add_argument('--effort', default='high', choices=('low', 'medium', 'high', 'xhigh', 'max'))
    parser.add_argument('--dpi', type=int, default=200)
    parser.add_argument('--timeout', type=float, default=2400)
    parser.add_argument('--pages', help='only these pages, e.g. 1-4 (for trials)')
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
        print(f'metadata: {elapsed}s {meta.get("title")!r} / {meta.get("composer")!r} / {meta.get("arranger")!r}', flush=True)

    merged = None
    for index, pages in enumerate(chunks, 1):
        workdir = args.outdir / 'chunks' / f'{index:03d}_p{pages[0]}-{pages[-1]}'
        done = workdir / 'chunk.musicxml'
        if done.exists():
            chunk = ET.parse(done).getroot()
        else:
            if merged is None:
                context, expected = FIRST_CONTEXT, None
            else:
                expected = [pid for pid, _ in parts_of(merged)]
                parts = '\n'.join(f'  {pid}: {name}' for pid, name in parts_of(merged))
                state = '\n'.join(f'  {pid}: {json.dumps(s, ensure_ascii=False)}' for pid, s in end_state(merged).items())
                previous = int(last_measure(merged)) if last_measure(merged).isdigit() else 0
                context = NEXT_CONTEXT.format(parts=parts, last=previous, next=previous + 1, state=state)
            prompt = PROMPT.format(pages=pages, total=total, context=context)
            images = render(pdf, pages, args.outdir, args.dpi)
            for attempt in (1, 2):
                result, elapsed, usage = call_astra(images, prompt, workdir / f'attempt{attempt}', args.effort, args.timeout)
                problems = check(result['musicxml'], expected)
                with log.open('a') as f:
                    f.write(json.dumps({'chunk': index, 'pages': pages, 'attempt': attempt, 'elapsed': elapsed,
                                        'usage': usage, 'measures': [result['first_measure'], result['last_measure']],
                                        'problems': problems, 'notes': result['notes']}, ensure_ascii=False) + '\n')
                print(f'chunk {index}/{len(chunks)} pages {pages} attempt {attempt}: {elapsed}s '
                      f"m{result['first_measure']}-{result['last_measure']} problems={len(problems)}", flush=True)
                if not problems:
                    break
                prompt = prompt + '\n\nYour previous answer failed these checks — fix them and answer again:\n- ' + \
                    '\n- '.join(problems)
            else:
                (workdir / 'failed.musicxml').write_text(result['musicxml'])
                print(f'STOP: chunk {index} still fails: {problems}', file=sys.stderr)
                write_result(args, 'failed', [f'pages {pages[0]}-{pages[-1]}: {p}' for p in problems], log)
                return 3
            done.write_text(result['musicxml'])
            chunk = ET.fromstring(result['musicxml'])
        if merged is None:
            merged = chunk
        else:
            merge(merged, chunk)

    xml = ET.tostring(merged, encoding='unicode')
    out = args.outdir / 'score.musicxml'
    out.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + xml, encoding='utf-8')
    problems = check(out.read_text())
    summary = {pid: len(merged.find(f"part[@id='{pid}']").findall('measure')) for pid, _ in parts_of(merged)}
    print(f'-> {out}  parts/measures={summary}  final check problems={problems}')
    write_result(args, 'failed' if problems else 'ok', problems, log)
    return 3 if problems else 0


def write_result(args, status, problems, log):
    entries = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    usage = {}
    for entry in entries:
        for turn in entry.get('usage') or []:
            for name, value in (turn or {}).items():
                if isinstance(value, int):
                    usage[name] = usage.get(name, 0) + value
    run = {'model': MODEL, 'effort': args.effort, 'dpi': args.dpi, 'pages_per_call': args.chunk,
           'calls': len(entries), 'elapsed_seconds': round(sum(e.get('elapsed', 0) for e in entries), 1),
           'usage': usage,
           'notes': [f"pages {e['pages'][0]}-{e['pages'][-1]}: {e['notes']}" for e in entries if e.get('notes')][-40:]}
    meta_file = args.outdir / 'metadata.json'
    metadata = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    (args.outdir / 'result.json').write_text(json.dumps({'status': status, 'problems': problems, 'run': run,
                                                         'metadata': metadata},
                                                        ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
