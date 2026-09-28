"""
악보 인식 짧은 형식 → MusicXML (scripts/omr_compact.py) — 모델이 MusicXML 대신 짧게 쓰고 우리가 바꾼다
"""
import xml.etree.ElementTree as ET
from fractions import Fraction

from django.test import SimpleTestCase

from scripts import omr_compact


def page(events_by_part, attributes='key=1 time=6/8 clef=G2-8', staves=1, measures=None, implicit=False):
    parts = [{'id': pid, 'name': pid, 'staves': staves} for pid in events_by_part]
    measures = measures or [{'number': '1', 'implicit': implicit, 'parts': [
        {'id': pid, 'attributes': attributes, 'barline': '', 'voices': voices} for pid, voices in events_by_part.items()]}]
    return {'parts': parts, 'measures': measures, 'first_measure': 1, 'last_measure': len(measures), 'notes': ''}


def voice(events, number=1, staff=1):
    return {'voice': number, 'staff': staff, 'events': events}


class CompactTest(SimpleTestCase):

    def convert(self, data, ties=None, first_state=None):
        text, problems = omr_compact.to_musicxml(data, ties, first_state)
        return ET.fromstring(text), problems

    def test_notes_chords_dots_and_attributes(self):
        root, problems = self.convert(page({'P1': [voice('E4/8 F#4/8 G4+B4/8 C5/4.')]}))
        self.assertEqual(problems, [])
        measure = root.find('part/measure')
        attributes = measure.find('attributes')
        self.assertEqual((attributes.findtext('divisions'), attributes.findtext('key/fifths'),
                          attributes.findtext('time/beats'), attributes.findtext('clef/clef-octave-change')),
                         (str(omr_compact.DIVISIONS), '1', '6', '-1'))
        notes = measure.findall('note')
        self.assertEqual([n.findtext('pitch/step') + (n.findtext('pitch/alter') or '') for n in notes],
                         ['E', 'F1', 'G', 'B', 'C'])
        self.assertIsNotNone(notes[3].find('chord'))
        self.assertIsNotNone(notes[4].find('dot'))
        self.assertEqual(int(notes[4].findtext('duration')), omr_compact.DIVISIONS * 3 // 2)

    def test_voices_get_backup_and_staff(self):
        root, problems = self.convert(page({'P1': [voice('G4/4.', 1, 1), voice('G2/4.', 5, 2)]},
                                           attributes='key=0 time=3/8 clef=G2 clef2=F4', staves=2))
        self.assertEqual(problems, [])
        measure = root.find('part/measure')
        self.assertEqual(measure.findtext('backup/duration'), str(omr_compact.DIVISIONS * 3 // 2))
        self.assertEqual([n.findtext('staff') for n in measure.findall('note')], ['1', '2'])
        self.assertEqual(measure.findtext('attributes/staves'), '2')
        self.assertEqual([c.get('number') for c in measure.findall('attributes/clef')], ['1', '2'])

    def test_tuplet_grace_rest_and_marks(self):
        root, problems = self.convert(page({'P1': [voice('[mf] [w:pizz.] (3:2 A4/16 B4/16 C5/16 ) g:D5/16 '
                                                         'B4/8{st,s(}')]}, attributes='time=2/8'))
        self.assertEqual(problems, [])   # 셋잇단 16분 셋 = 8분 하나, 꾸밈음은 길이 없음
        notes = root.find('part/measure').findall('note')
        self.assertEqual(notes[0].findtext('time-modification/actual-notes'), '3')
        self.assertEqual(notes[0].find('notations/tuplet').get('type'), 'start')
        self.assertEqual(notes[2].find('notations/tuplet').get('type'), 'stop')
        self.assertIsNotNone(notes[3].find('grace'))
        self.assertIsNone(notes[3].find('duration'))
        self.assertIsNotNone(notes[4].find('notations/articulations/staccato'))
        self.assertEqual(notes[4].find('notations/slur').get('type'), 'start')
        self.assertIsNotNone(root.find('part/measure/direction/direction-type/dynamics/mf'))
        self.assertEqual(root.findtext('part/measure/direction/direction-type/words'), 'pizz.')

    def test_ties_cross_measures_and_pages(self):
        ties = omr_compact.TieState()
        first = page({'P1': [voice('B4/4.~')]}, attributes='time=3/8')
        root, problems = self.convert(first, ties)
        self.assertEqual(problems, [])
        self.assertEqual(root.find('part/measure/note/tie').get('type'), 'start')
        # 다음 쪽 — 박자표를 다시 적지 않아도 앞 쪽 상태로 길이를 잰다
        second = page({'P1': [voice('B4/8 r/4')]}, attributes='')
        root, problems = self.convert(second, ties, {'P1': {'time': Fraction(3, 2)}})
        self.assertEqual(problems, [])
        self.assertEqual(root.find('part/measure/note/tie').get('type'), 'stop')
        self.assertEqual(dict(ties), {})

    def test_problems_are_reported(self):
        _, problems = self.convert(page({'P1': [voice('C4/4 Q7/4 D4 (3:2 E4/8')]}, attributes='time=3/4 tempo=fast'))
        joined = ' | '.join(problems)
        self.assertIn('cannot read "Q7/4"', joined)
        self.assertIn('"D4" needs a duration', joined)
        self.assertIn('tuplet opened but not closed', joined)
        self.assertIn('unknown attributes', joined)
        self.assertIn('time signature wants', joined)

    def test_missing_part_and_pickup(self):
        data = page({'P1': [voice('C5/8')], 'P2': [voice('R')]}, attributes='time=6/8', implicit=True)
        data['measures'][0]['parts'].pop()
        root, problems = self.convert(data)
        self.assertIn('P2 m1: part missing in this measure', problems)
        self.assertNotIn('time signature wants', ' '.join(problems))   # 못갖춘마디는 짧아도 된다
        self.assertEqual(root.find('part/measure').get('implicit'), 'yes')

    def test_compact_is_much_shorter_than_musicxml(self):
        events = ' '.join(['C5/16 D5/16 E5/16 F5/16'] * 3)
        data = page({'P1': [voice(events)]}, attributes='time=3/4')
        text, problems = omr_compact.to_musicxml(data)
        self.assertEqual(problems, [])
        self.assertGreater(len(text), 8 * len(events))


class KeyCheckTest(SimpleTestCase):

    def test_first_key_must_agree_with_independent_reading(self):
        from scripts.astra_musicxml import key_disagreement
        wrong = page({'P1': [voice('F#5/8')]}, attributes='key=3 time=6/8')
        self.assertIn('key=3', key_disagreement(wrong, {'key_fifths': 2})[0])
        self.assertEqual(key_disagreement(wrong, {'key_fifths': 3}), [])
        self.assertEqual(key_disagreement(wrong, {}), [])                       # 예전 곡 정보(조표 없음)


class StavesCheckTest(SimpleTestCase):
    """보표 분석이 잰 시스템마다 보표 수와 첫 쪽 파트들의 보표 합이 달라야 걸린다 (Arpeggione: 기타 셋 → 아르페지오네 + 피아노)"""

    def run_first_page(self, parts, staves):
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import fitz
        from scripts import astra_musicxml as script
        tmp = Path(tempfile.mkdtemp(prefix='omr-'))
        self.addCleanup(__import__('shutil').rmtree, tmp, ignore_errors=True)
        document = fitz.open()
        document.new_page()
        document.save(tmp / 'score.pdf')
        prompts = []

        def fake_call(images, prompt, workdir, effort, timeout, schema=script.SCHEMA):
            if schema is script.META_SCHEMA:
                return {'title': 'T'}, 1.0, []
            prompts.append(prompt)
            voices = []
            data = {'parts': parts, 'first_measure': 1, 'last_measure': 1, 'notes': '', 'measures': [{
                'number': '1', 'implicit': False, 'parts': [
                    {'id': p['id'], 'attributes': 'key=0 time=3/4 clef=G2' + (' clef2=F4' if p['staves'] == 2 else ''),
                     'barline': '', 'voices': [{'voice': 1, 'staff': 1, 'events': 'R'}]} for p in parts]}]}
            return data, 1.0, []
        argv = ['astra_musicxml.py', str(tmp / 'score.pdf'), str(tmp / 'out'), '--dpi', '20', '--staves', str(staves)]
        with patch.object(script, 'call_astra', fake_call), patch.object(script, 'check', lambda text, expected=None: []), \
                patch.object(sys, 'argv', argv):
            code = script.main()
        return code, prompts

    def test_wrong_part_list_is_rejected(self):
        code, prompts = self.run_first_page([{'id': 'P1', 'name': 'Arpeggione', 'staves': 1},
                                             {'id': 'P2', 'name': 'Pianoforte', 'staves': 2}], staves=2)
        self.assertEqual(code, 3)
        self.assertIn('every system here has exactly 2 staves', prompts[0])
        self.assertIn('NEVER infer instruments from the title', prompts[0])
        self.assertIn('your parts have 3 staves in total', prompts[1])

    def test_matching_part_list_passes(self):
        code, _ = self.run_first_page([{'id': f'P{i}', 'name': f'Staff {i}', 'staves': 1} for i in (1, 2, 3)], staves=3)
        self.assertEqual(code, 0)
