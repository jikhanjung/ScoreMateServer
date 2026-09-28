"""모델 bbox 정확도 시험 — 쪽 이미지 → 시스템 · 보표 · 마디선 좌표(0..1000), PDF 보표 분석(layout JSON)과 pt 로 비교.
운영 호스트에서: python bbox_trial.py <pdf> <layout.json> <pages 1,2> <out_dir> [effort]"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, '/srv/scoremate/scripts')
import pymupdf
from astra_musicxml import call_astra

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['systems', 'notes'], 'properties': {
    'notes': {'type': 'string'},
    'systems': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
        'required': ['bbox', 'staves', 'barlines'], 'properties': {
            'bbox': {'type': 'array', 'items': {'type': 'integer'}},
            'staves': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'integer'}}},
            'barlines': {'type': 'array', 'items': {'type': 'integer'}}}}}}}
PROMPT = """The attached image is one page of a printed music score. Measure its layout in coordinates normalized to
0..1000 of the image (x: 0 = left edge, 1000 = right edge; y: 0 = top edge, 1000 = bottom edge). For every system (one
printed line of staves played together), top to bottom:
- bbox [x0, y0, x1, y1]: x0/x1 = left/right ends of the staff lines, y0 = the TOP staff line of the first staff,
  y1 = the BOTTOM staff line of the last staff (the staff lines only — not notes, dynamics or text above/below)
- staves: for each staff top to bottom, [y of its top line, y of its bottom line]
- barlines: x of every barline that ends a measure in this system, left to right, including the final one at the right end
  (not the line at the very start of the system)
Be as precise as you can. Inspect the attached image directly. Do not read other files, run commands, or use external tools."""

pdf, layout_path, pages, out = sys.argv[1], sys.argv[2], [int(p) for p in sys.argv[3].split(',')], Path(sys.argv[4])
effort = sys.argv[5] if len(sys.argv) > 5 else 'high'
out.mkdir(parents=True, exist_ok=True)
layout = json.loads(Path(layout_path).read_text())
doc = pymupdf.open(pdf)
report = []
for number in pages:
    image = out / f'page{number:03d}.png'
    doc[number - 1].get_pixmap(dpi=200).save(image)
    result, elapsed, usage = call_astra([image], PROMPT, out / f'call{number:03d}', effort, 1200, SCHEMA)
    page = layout['pages'][number - 1]
    W, H = page['widthPt'], page['heightPt']
    fx, fy = W / 1000, H / 1000
    truth = page['systems']
    row = {'page': number, 'elapsed': elapsed, 'systems_model': len(result['systems']), 'systems_pdf': len(truth),
           'output_tokens': (usage or [{}])[0].get('output_tokens')}
    edge, staff, bar, bar_count = [], [], [], []
    for s_model, s_true in zip(result['systems'], truth):
        x0, y0, x1, y1 = s_model['bbox']
        edge += [abs(x0 * fx - s_true['left']), abs(x1 * fx - s_true['right']), abs(y0 * fy - s_true['top']), abs(y1 * fy - s_true['bottom'])]
        for (mt, mb), (tt, tb) in zip(s_model['staves'], s_true['staffBands']):
            staff += [abs(mt * fy - tt), abs(mb * fy - tb)]
        truth_bars = s_true['barlines'][1:]
        model_bars = [b * fx for b in s_model['barlines']]
        bar_count.append((len(model_bars), len(truth_bars), len(s_model['staves']), len(s_true['staffBands'])))
        for t in truth_bars:
            if model_bars:
                bar.append(min(abs(t - m) for m in model_bars))
    def stats(v):
        v = sorted(v)
        return {'n': len(v), 'mean': round(sum(v) / len(v), 1), 'p90': round(v[int(len(v) * 0.9) - 1 if len(v) > 1 else 0], 1), 'max': round(v[-1], 1)} if v else None
    row.update(system_edges_pt=stats(edge), staff_lines_pt=stats(staff), barlines_pt=stats(bar),
               counts=bar_count, notes=result['notes'][:200])
    report.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
(out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
