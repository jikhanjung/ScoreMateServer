"""Score PDF → per-page layout read by the model (systems · staves · barlines · staff names · time signatures).

Host-side, like astra_musicxml.py (Codex CLI gpt-6-astra, ChatGPT login). One call per page, coordinates normalized to
0..1000 of the page image. The container turns them into points and the TV app's ScoreLayout shape (scores/model_layouts.py).
On clean vector PDFs this matched the PDF analysis to within one grid step (devlog 070); its real use is scanned scores,
where the vector analysis finds nothing, and as a cross-check of the vector analysis.

    ~/venv/omr/bin/python model_layout.py score.pdf out/v12 [--effort high]

Resumable (pages/pNNN.json). Writes out/result.json {"status", "pages": [{page, systems, notes}], "run"} and exits
0 = ok, 3 = a page failed the checks twice (a verdict), 4 = paused by --budget-pages (more to do),
anything else = could not run (retry later).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import pymupdf

try:
    from .astra_musicxml import MODEL, call_astra, render
except ImportError:
    from astra_musicxml import MODEL, call_astra, render

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['systems', 'notes'], 'properties': {
    'notes': {'type': 'string'},
    'systems': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
        'required': ['bbox', 'staves', 'barlines', 'staff_names', 'time_signatures'], 'properties': {
            'bbox': {'type': 'array', 'items': {'type': 'integer'}},
            'staves': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'integer'}}},
            'barlines': {'type': 'array', 'items': {'type': 'integer'}},
            'staff_names': {'type': 'array', 'items': {'type': 'string'}},
            'time_signatures': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                'required': ['x', 'numerator', 'denominator'], 'properties': {
                    'x': {'type': 'integer'}, 'numerator': {'type': 'integer'}, 'denominator': {'type': 'integer'}}}}}}}}}

PROMPT = """The attached image is one page of a printed music score. Measure its layout in coordinates normalized to
0..1000 of the image (x: 0 = left edge, 1000 = right edge; y: 0 = top edge, 1000 = bottom edge). For every system (one
printed line of staves played together), top to bottom:
- bbox [x0, y0, x1, y1]: x0/x1 = left/right ends of the staff lines, y0 = the TOP staff line of the first staff,
  y1 = the BOTTOM staff line of the last staff (the staff lines only — not notes, dynamics or text above/below)
- staves: for each staff top to bottom, [y of its top line, y of its bottom line]
- barlines: x of every barline that ends a measure in this system, left to right, including the final one at the right end
  (not the line at the very start of the system; a double or final barline counts once, at its centre)
- staff_names: for each staff, the name printed at its left (instrument or player), "" if none
- time_signatures: every time signature printed in this system: its x (centre), numerator, denominator
  (common time C = 4/4, cut time = 2/2); [] if none
If the page has no staves (title page, text), return "systems": [].
Be as precise as you can. Inspect the attached image directly. Do not read other files, run commands, or use external tools."""


def check(page):
    """읽은 값이 말이 되는가 — 문제 목록(비면 통과)"""
    problems = []
    for index, system in enumerate(page.get('systems') or [], 1):
        bbox = system.get('bbox') or []
        if len(bbox) != 4 or not (0 <= bbox[0] < bbox[2] <= 1000 and 0 <= bbox[1] < bbox[3] <= 1000):
            problems.append(f'system {index}: bbox must be [x0, y0, x1, y1] with x0 < x1, y0 < y1 inside 0..1000')
            continue
        staves = system.get('staves') or []
        if not staves or any(len(s) != 2 or s[0] >= s[1] for s in staves):
            problems.append(f'system {index}: staves must be [[top, bottom], …] with top < bottom')
        elif abs(staves[0][0] - bbox[1]) > 3 or abs(staves[-1][1] - bbox[3]) > 3:
            problems.append(f'system {index}: the first staff top / last staff bottom must equal bbox y0 / y1')
        bars = system.get('barlines') or []
        if not bars or bars != sorted(bars) or bars[0] <= bbox[0] or bars[-1] > bbox[2] + 3:
            problems.append(f'system {index}: barlines must be increasing, right of x0, the last at the right end x1')
        if len(system.get('staff_names') or []) not in (0, len(staves)):
            problems.append(f'system {index}: give one staff name per staff')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('outdir', type=Path)
    parser.add_argument('--effort', default='high', choices=('low', 'medium', 'high', 'xhigh', 'max'))
    parser.add_argument('--dpi', type=int, default=200)
    parser.add_argument('--timeout', type=float, default=1200)
    parser.add_argument('--budget-pages', type=int, default=0,
                        help='stop after this many newly read pages (exit 4 = more to do); 0 = all')
    args = parser.parse_args()

    pdf = pymupdf.open(args.pdf)
    (args.outdir / 'pages').mkdir(parents=True, exist_ok=True)
    # 여러 번에 나눠 돌 수 있다(--budget-pages) — 호출 수 · 시간 · 토큰은 run.json 에 쌓는다
    run_file = args.outdir / 'run.json'
    total = json.loads(run_file.read_text()) if run_file.exists() else {'calls': 0, 'elapsed_seconds': 0.0, 'usage': {}}
    started, pages, calls, usage, new_pages = time.monotonic(), [], 0, total['usage'], 0

    def save_run():
        total.update(calls=total['calls'] + calls, usage=usage,
                     elapsed_seconds=round(total['elapsed_seconds'] + time.monotonic() - started, 1))
        run_file.write_text(json.dumps(total))
        return total

    for number in range(1, len(pdf) + 1):
        done = args.outdir / 'pages' / f'p{number:03d}.json'
        if done.exists():
            pages.append(json.loads(done.read_text()))
            continue
        images = render(pdf, [number], args.outdir, args.dpi)
        prompt, problems, result = PROMPT, [], None
        for attempt in (1, 2):
            result, elapsed, turns = call_astra(images, prompt, args.outdir / 'calls' / f'p{number:03d}-{attempt}',
                                                args.effort, args.timeout, SCHEMA)
            calls += 1
            for turn in turns or []:
                for name, value in (turn or {}).items():
                    if isinstance(value, int):
                        usage[name] = usage.get(name, 0) + value
            problems = check(result)
            print(f'page {number} attempt {attempt}: {elapsed}s systems={len(result.get("systems") or [])} '
                  f'problems={len(problems)}', flush=True)
            if not problems:
                break
            prompt = PROMPT + '\n\nYour previous answer failed these checks — fix them:\n- ' + '\n- '.join(problems)
        if problems:
            save_run()
            (args.outdir / 'result.json').write_text(json.dumps(
                {'status': 'failed', 'problems': [f'page {number}: {p}' for p in problems]}, ensure_ascii=False))
            return 3
        page = {'page': number, 'systems': result.get('systems') or [], 'notes': result.get('notes', '')}
        done.write_text(json.dumps(page, ensure_ascii=False))
        pages.append(page)
        new_pages += 1
        if args.budget_pages and new_pages >= args.budget_pages and number < len(pdf):
            save_run()
            print(f'paused after page {number}: pages {number + 1}–{len(pdf)} remain', flush=True)
            return 4          # 파이프라인이 다른 일을 끼워 넣고 다음에 이어 한다
    total = save_run()
    run = {'model': MODEL, 'effort': args.effort, 'dpi': args.dpi, 'calls': total['calls'],
           'elapsed_seconds': total['elapsed_seconds'], 'usage': total['usage']}
    (args.outdir / 'result.json').write_text(json.dumps({'status': 'ok', 'pages': pages, 'run': run}, ensure_ascii=False))
    print(f'-> {len(pages)} pages, {sum(len(p["systems"]) for p in pages)} systems', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
