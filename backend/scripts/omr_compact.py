"""Compact score text → MusicXML. The model writes this short form (≈4x fewer tokens than MusicXML); we build the XML.

A page is JSON: {"parts": [{"id", "name", "staves"}], "measures": [{"number", "implicit", "system_start",
"parts": [{"id", "attributes", "barline", "voices": [{"voice", "staff", "events"}]}]}]}

system_start: true for the first measure of every system (printed line) on the page — the page's first measure is always true.

attributes (space separated, only when something is set or changes): key=-3..7  time=6/8  clef=G2 | F4 | C3 | G2-8
(octave down, e.g. guitar) — clef2=… for the second staff of a multi-staff part.
barline: "" | "repeat-start" | "repeat-end" | "repeat-both" | "double" | "final"

events (space separated tokens, in time order within one voice):
  note     C#5/8   Bb3/4.   Fn4/16 (explicit natural)  — the SOUNDING-AS-WRITTEN pitch: apply the key signature
           and accidentals yourself (in G major every F is F#). Octave 4 = middle C octave.
  rest     r/4     R (whole-measure rest, no duration)
  chord    C4+E4+G4/2
  dots     /4.  /8..
  tie      C5/4~   (tie starts here, continues to the next note of the same pitch in the same voice)
  grace    g:D5/16
  tuplet   (3:2 C5/8 D5/8 E5/8 )    — "(actual:normal" opens, ")" closes
  marks    C5/8{st,s(}   st=staccato acc=accent ten=tenuto marc=marcato fer=fermata harm=harmonic x=cross notehead
           tr=trill arp=arpeggio s( / s) = slur start / stop  f:3 = fingering  str:5 = string number
  text     [p] [mf] [ff] [sfz] (dynamics)   [w:pizz.] (words)   [tempo:Andante]
"""
import re
import xml.etree.ElementTree as ET
from fractions import Fraction

DIVISIONS = 10080                      # quarter — divisible by 2^5 · 3^2 · 5 · 7 (tuplets up to 9)
TYPES = {1: 'whole', 2: 'half', 4: 'quarter', 8: 'eighth', 16: '16th', 32: '32nd', 64: '64th', 128: '128th'}
DYNAMICS = {'ppp', 'pp', 'p', 'mp', 'mf', 'f', 'ff', 'fff', 'sf', 'sfz', 'sffz', 'fp', 'rf', 'rfz', 'fz'}
ARTICULATIONS = {'st': 'staccato', 'acc': 'accent', 'ten': 'tenuto', 'marc': 'strong-accent', 'stis': 'staccatissimo'}
TOKEN = re.compile(r'\[[^\]]*\]|\S+')
NOTE = re.compile(r'^(g:)?((?:[A-G](?:##|bb|#|b|n)?-?\d)(?:\+[A-G](?:##|bb|#|b|n)?-?\d)*|r|R)'
                  r'(?:/(\d+)(\.{0,2}))?(~)?(?:\{([^}]*)\})?$')
PITCH = re.compile(r'^([A-G])(##|bb|#|b|n)?(-?\d)$')
ALTER = {'#': 1, '##': 2, 'b': -1, 'bb': -2, 'n': 0, None: 0}

SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['parts', 'measures', 'first_measure', 'last_measure', 'notes'],
    'properties': {
        'first_measure': {'type': 'integer'}, 'last_measure': {'type': 'integer'}, 'notes': {'type': 'string'},
        'parts': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['id', 'name', 'staves'],
            'properties': {'id': {'type': 'string'}, 'name': {'type': 'string'}, 'staves': {'type': 'integer'}}}},
        'measures': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['number', 'implicit', 'system_start', 'parts'],
            'properties': {
                'number': {'type': 'string'}, 'implicit': {'type': 'boolean'}, 'system_start': {'type': 'boolean'},
                'parts': {'type': 'array', 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'required': ['id', 'attributes', 'barline', 'voices'],
                    'properties': {
                        'id': {'type': 'string'}, 'attributes': {'type': 'string'}, 'barline': {'type': 'string'},
                        'voices': {'type': 'array', 'items': {
                            'type': 'object', 'additionalProperties': False, 'required': ['voice', 'staff', 'events'],
                            'properties': {'voice': {'type': 'integer'}, 'staff': {'type': 'integer'},
                                           'events': {'type': 'string'}}}}}}}}}},
    },
}

FORMAT_HELP = __doc__[__doc__.index('system_start:'):]


def systems_on_page(page):
    """이 쪽의 시스템 수 — 첫 마디 + system_start 인 마디"""
    measures = page.get('measures') or []
    return (1 if measures else 0) + sum(1 for m in measures[1:] if m.get('system_start'))


class TieState(dict):
    """(part, staff, voice, step, alter, octave) → open tie. Carried from page to page"""


def _sub(parent, tag, text=None, **attrib):
    element = ET.SubElement(parent, tag, {k.replace('_', '-'): str(v) for k, v in attrib.items()})
    if text is not None:
        element.text = str(text)
    return element


def _attributes(measure_el, spec, staves, first, time_state):
    """'key=2 time=6/8 clef=G2 clef2=F4' → <attributes>. first: this document's first measure (divisions, staves)"""
    values = dict(item.split('=', 1) for item in spec.split() if '=' in item)
    unknown = [item for item in spec.split() if '=' not in item or item.split('=', 1)[0] not in
               ('key', 'time', 'clef', 'clef2')]
    if not values and not first:
        return unknown
    attributes = _sub(measure_el, 'attributes')
    if first:
        _sub(attributes, 'divisions', DIVISIONS)
    if 'key' in values:
        key = _sub(attributes, 'key')
        _sub(key, 'fifths', int(values['key']))
    if 'time' in values:
        beats, beat_type = values['time'].split('/')
        time = _sub(attributes, 'time')
        _sub(time, 'beats', int(beats))
        _sub(time, 'beat-type', int(beat_type))
        time_state['time'] = Fraction(int(beats) * 4, int(beat_type))
    if first and staves > 1:
        _sub(attributes, 'staves', staves)
    for name, number in (('clef', 1), ('clef2', 2)):
        if name in values:
            match = re.fullmatch(r'([GFC])(\d)(?:([-+])(8|15))?', values[name])
            if not match:
                unknown.append(f'{name}={values[name]}')
                continue
            clef = _sub(attributes, 'clef', number=number) if staves > 1 else _sub(attributes, 'clef')
            _sub(clef, 'sign', match.group(1))
            _sub(clef, 'line', match.group(2))
            if match.group(3):
                _sub(clef, 'clef-octave-change', (1 if match.group(3) == '+' else -1) * (1 if match.group(4) == '8' else 2))
    if len(attributes) == 0:
        measure_el.remove(attributes)
    return unknown


def _direction(measure_el, token, voice, staff, staves):
    body = token[1:-1].strip()
    direction = _sub(measure_el, 'direction', placement='below' if body in DYNAMICS else 'above')
    kind = _sub(direction, 'direction-type')
    if body in DYNAMICS:
        _sub(_sub(kind, 'dynamics'), body)
    elif body.startswith('tempo:'):
        _sub(kind, 'words', body[6:].strip(), font_weight='bold')
    elif body.startswith('w:'):
        _sub(kind, 'words', body[2:].strip())
    else:
        _sub(kind, 'words', body)
    _sub(direction, 'voice', voice)
    if staves > 1:
        _sub(direction, 'staff', staff)


def _voice(measure_el, part_id, voice, staff, staves, events, measure_length, ties, where):
    """One voice's events → <note>s. Returns (duration in divisions, problems)"""
    problems, total, tuplet = [], Fraction(0), None
    tokens = TOKEN.findall(events or '')
    pending_tuplet_start = False
    for index, token in enumerate(tokens):
        if token.startswith('['):
            _direction(measure_el, token, voice, staff, staves)
            continue
        match = re.fullmatch(r'\((\d+):(\d+)', token)
        if match:
            tuplet = (int(match.group(1)), int(match.group(2)))
            pending_tuplet_start = True
            continue
        if token == ')':
            if tuplet is None:
                problems.append(f'{where}: ")" without an open tuplet')
            else:
                notes = [n for n in measure_el.findall('note') if n.find('chord') is None]
                if notes:
                    notations = notes[-1].find('notations')
                    if notations is None:
                        notations = _sub(notes[-1], 'notations')
                    _sub(notations, 'tuplet', type='stop')
            tuplet = None
            continue
        match = NOTE.match(token)
        if not match:
            problems.append(f'{where}: cannot read "{token}"')
            continue
        grace, body, denominator, dots, tie, marks = match.groups()
        if body == 'R':
            length = measure_length
        else:
            if not denominator or int(denominator) not in TYPES:
                problems.append(f'{where}: "{token}" needs a duration /1 /2 /4 /8 /16 /32 /64')
                continue
            length = Fraction(4, int(denominator)) * (2 - Fraction(1, 2 ** len(dots)))
            if tuplet:
                length = length * tuplet[1] / tuplet[0]
        pitches = [] if body in ('r', 'R') else body.split('+')
        marks = [m.strip() for m in (marks or '').split(',') if m.strip()]
        for position, pitch in enumerate(pitches or [None]):
            step = accidental = octave = None
            note = _sub(measure_el, 'note')
            if grace:
                _sub(note, 'grace')
            if position > 0:
                _sub(note, 'chord')
            if pitch is None:
                _sub(note, 'rest', **({'measure': 'yes'} if body == 'R' else {}))
            else:
                step, accidental, octave = PITCH.match(pitch).groups()
                element = _sub(note, 'pitch')
                _sub(element, 'step', step)
                if ALTER[accidental]:
                    _sub(element, 'alter', ALTER[accidental])
                _sub(element, 'octave', octave)
            if not grace:
                _sub(note, 'duration', int(length * DIVISIONS))
            key = None
            if pitch is not None:
                key = (part_id, staff, voice, step, ALTER[accidental], octave)
                if key in ties:
                    _sub(note, 'tie', type='stop')
                if tie:
                    _sub(note, 'tie', type='start')
            _sub(note, 'voice', voice)
            if body != 'R' and denominator:
                _sub(note, 'type', TYPES[int(denominator)])
                for _ in dots or '':
                    _sub(note, 'dot')
            if accidental == 'n' and pitch is not None:
                _sub(note, 'accidental', 'natural')
            if tuplet and not grace:
                modification = _sub(note, 'time-modification')
                _sub(modification, 'actual-notes', tuplet[0])
                _sub(modification, 'normal-notes', tuplet[1])
            if 'harm' in marks:
                _sub(note, 'notehead', 'diamond')
            elif 'x' in marks:
                _sub(note, 'notehead', 'x')
            if staves > 1:
                _sub(note, 'staff', staff)
            notations = None

            def notation():
                nonlocal notations
                if notations is None:
                    notations = _sub(note, 'notations')
                return notations
            if key is not None and key in ties:
                _sub(notation(), 'tied', type='stop')
                ties.pop(key)
            if key is not None and tie:
                _sub(notation(), 'tied', type='start')
                ties[key] = True
            if position == 0:
                if pending_tuplet_start and tuplet and not grace:
                    _sub(notation(), 'tuplet', type='start')
                    pending_tuplet_start = False
                for mark in marks:
                    if mark == 's(':
                        _sub(notation(), 'slur', type='start', number=1)
                    elif mark == 's)':
                        _sub(notation(), 'slur', type='stop', number=1)
                    elif mark == 'fer':
                        _sub(notation(), 'fermata')
                    elif mark == 'arp':
                        _sub(notation(), 'arpeggiate')
                    elif mark == 'tr':
                        _sub(_sub(notation(), 'ornaments'), 'trill-mark')
                    elif mark in ARTICULATIONS:
                        articulations = notation().find('articulations')
                        if articulations is None:
                            articulations = _sub(notation(), 'articulations')
                        _sub(articulations, ARTICULATIONS[mark])
                    elif mark == 'harm' or mark.startswith('f:') or mark.startswith('str:'):
                        technical = notation().find('technical')
                        if technical is None:
                            technical = _sub(notation(), 'technical')
                        if mark == 'harm':
                            _sub(technical, 'harmonic')
                        elif mark.startswith('f:'):
                            _sub(technical, 'fingering', mark[2:])
                        else:
                            _sub(technical, 'string', mark[4:])
        if not grace:
            total += length
    if tuplet is not None:
        problems.append(f'{where}: tuplet opened but not closed')
    return total, problems


def to_musicxml(page, ties=None, first_state=None, new_page=False):
    """page (dict in the compact form) → (MusicXML text, problems). ties: TieState carried between pages.
    first_state: {part_id: {'time': Fraction}} — the time signature in force before this page.
    new_page: this page is not the score's first — its first measure gets <print new-page>, later system starts <print new-system>"""
    ties = ties if ties is not None else TieState()
    problems = []
    root = ET.Element('score-partwise', version='4.0')
    part_list = _sub(root, 'part-list')
    parts = page.get('parts') or []
    staves = {}
    for part in parts:
        score_part = _sub(part_list, 'score-part', id=part['id'])
        _sub(score_part, 'part-name', part.get('name', ''))
        staves[part['id']] = max(1, int(part.get('staves') or 1))
    part_elements = {part['id']: _sub(root, 'part', id=part['id']) for part in parts}
    time_state = {pid: dict((first_state or {}).get(pid, {})) for pid in part_elements}
    for index, measure in enumerate(page.get('measures') or []):
        number = str(measure.get('number', index + 1))
        seen = set()
        for entry in measure.get('parts') or []:
            pid = entry.get('id')
            if pid not in part_elements:
                problems.append(f'm{number}: unknown part {pid}')
                continue
            seen.add(pid)
            measure_el = _sub(part_elements[pid], 'measure', number=number,
                              **({'implicit': 'yes'} if measure.get('implicit') else {}))
            if index == 0 and new_page:
                _sub(measure_el, 'print', new_page='yes')           # 한 쪽씩 옮기므로 쪽 바뀜은 호출 경계로 정확하다
            elif index > 0 and measure.get('system_start'):
                _sub(measure_el, 'print', new_system='yes')
            unknown = _attributes(measure_el, entry.get('attributes') or '', staves[pid], index == 0, time_state[pid])
            if unknown:
                problems.append(f'{pid} m{number}: unknown attributes {unknown}')
            measure_length = time_state[pid].get('time')
            if measure_length is None:
                problems.append(f'{pid} m{number}: no time signature yet')
                measure_length = Fraction(4)
            voices = entry.get('voices') or []
            for position, voice in enumerate(voices):
                where = f'{pid} m{number} voice {voice.get("voice")}'
                length, found = _voice(measure_el, pid, int(voice.get('voice') or 1), int(voice.get('staff') or 1),
                                       staves[pid], voice.get('events', ''), measure_length, ties, where)
                problems += found
                if length != measure_length and not measure.get('implicit') and length > 0:
                    problems.append(f'{where}: {length} quarters, time signature wants {measure_length}')
                if position < len(voices) - 1 and length > 0:
                    _sub(_sub(measure_el, 'backup'), 'duration', int(length * DIVISIONS))
            barline = (entry.get('barline') or '').strip()
            if barline:
                _barline(measure_el, barline, problems, f'{pid} m{number}')
        for pid in part_elements.keys() - seen:
            problems.append(f'{pid} m{number}: part missing in this measure')
    return ET.tostring(root, encoding='unicode'), problems[:40]


def _barline(measure_el, kind, problems, where):
    if kind in ('repeat-start', 'repeat-both'):
        left = ET.Element('barline', location='left')
        _sub(left, 'bar-style', 'heavy-light')
        _sub(left, 'repeat', direction='forward')
        attributes = measure_el.find('attributes')
        measure_el.insert(list(measure_el).index(attributes) + 1 if attributes is not None else 0, left)
    if kind in ('repeat-end', 'repeat-both'):
        right = _sub(measure_el, 'barline', location='right')
        _sub(right, 'bar-style', 'light-heavy')
        _sub(right, 'repeat', direction='backward')
    elif kind == 'double':
        _sub(_sub(measure_el, 'barline', location='right'), 'bar-style', 'light-light')
    elif kind == 'final':
        _sub(_sub(measure_el, 'barline', location='right'), 'bar-style', 'light-heavy')
    elif kind not in ('repeat-start',):
        problems.append(f'{where}: unknown barline "{kind}"')
