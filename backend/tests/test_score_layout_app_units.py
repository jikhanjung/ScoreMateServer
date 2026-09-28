"""
TV 앱(MrgqPdfViewer) 의 악보 분석 단위 테스트를 그대로 옮겼다 — scores/score_layout.py 가 앱의 Kotlin 과 같은 규칙인가.

  app/src/test/java/com/mrgq/pdfviewer/StaffSystemDetectorTest.kt   → StaffSystemDetectorTest
  app/src/test/java/com/mrgq/pdfviewer/StaffLabelDetectorTest.kt    → StaffLabelDetectorTest
  app/src/test/java/com/mrgq/pdfviewer/TimeSignatureDetectorTest.kt → TimeSignatureDetectorTest
  app/src/test/java/com/mrgq/pdfviewer/PathContentInterpreterTest.kt → PathContentInterpreterTest

입력 · 기대값은 Kotlin 테스트와 같다. 앱은 Float(32비트)로 계산하므로 입력을 만드는 식(`x - 0.4f` 등)도 f32 로 거친다.
테스트 이름은 Kotlin 함수 이름 앞에 test_ 를 붙인 것이다.
"""
from dataclasses import replace

from django.test import SimpleTestCase

from scores.score_layout import (
    ContentInterpreter, PageLayout, PathBox, SystemLayout, TextRun, TimeSignatureMark, attach_labels, detect_systems,
    detect_time_signatures, f32, to_measures,
)


def fl(v):
    """Kotlin Float 리터럴 (예: 124.6f)"""
    return f32(v)


def measure_count(pages):
    """ScoreLayout.measureCount"""
    return sum(s.measure_count for p in pages for s in p.systems)


# --------------------------------------------------------------------------------------------- StaffSystemDetectorTest

class StaffSystemDetectorTest(SimpleTestCase):
    """
    시스템·마디선 판정 규칙 (data/segment_score.py 포트). 합성 경로로 규칙 하나씩 확인한다.
    실제 악보와의 일치는 골든 테스트(test_score_layout.GoldenLayoutTest)가 본다.

    좌표는 PDF y-up. 보표 하나 = 아래 오선 y 부터 5pt 간격 5줄(폭 20pt).
    """

    page_height = 842.0

    @staticmethod
    def line(x0, x1, y):
        return PathBox(x0, f32(y - 0.25), x1, f32(y + 0.25), curved=False)

    @classmethod
    def staff(cls, bottom_y, x0=50.0, x1=500.0):
        return [cls.line(x0, x1, f32(bottom_y + k * 5.0)) for k in range(5)]

    @staticmethod
    def bar(x, bottom_y):
        return PathBox(f32(x - fl(0.4)), bottom_y, f32(x + fl(0.4)), f32(bottom_y + 20.0), curved=False)

    @staticmethod
    def head(x, y):
        return PathBox(f32(x - 3.0), f32(y - 2.5), f32(x + 3.0), f32(y + 2.5), curved=True)

    @staticmethod
    def system_staves(lowest_bottom):
        """한 시스템 = 보표 5개, 보표 사이 25pt. 아래 보표부터."""
        return [f32(lowest_bottom + k * 45.0) for k in range(5)]

    def system_with_bars(self, lowest_bottom, bar_xs):
        bottoms = self.system_staves(lowest_bottom)
        return [ln for b in bottoms for ln in self.staff(b)] + [self.bar(x, b) for b in bottoms for x in bar_xs]

    def detect(self, boxes, texts=()):
        return detect_systems(boxes, self.page_height, texts)

    def test_오선이_없으면_빈_결과(self):
        self.assertEqual(self.detect([]), [])
        self.assertEqual(self.detect([self.bar(100.0, 100.0)]), [])

    def test_오선이_다섯줄이_안되면_보표가_아니다(self):
        four_lines = [self.line(50.0, 500.0, 400.0 + k * 5.0) for k in range(4)]
        self.assertEqual(self.detect(four_lines), [])

    def test_마디선으로_세_마디를_나눈다(self):
        systems = self.detect(self.system_with_bars(420.0, [200.0, 350.0, 500.0]))
        self.assertEqual(len(systems), 1)
        s = systems[0]
        self.assertEqual(s.barlines, [50.0, 200.0, 350.0, 500.0])
        self.assertEqual(s.measure_count, 3)
        self.assertEqual(len(s.staff_bands), 5)

    def test_좌표는_위에서_아래로_뒤집는다(self):
        [s] = self.detect(self.system_with_bars(420.0, [200.0, 500.0]))
        # 가장 위 보표의 위 오선 y = 420 + 4×45 + 20 = 620 → 842 - 620
        self.assertAlmostEqual(s.top, 222.0, delta=0.05)
        # 가장 아래 보표의 아래 오선 y = 420 → 842 - 420
        self.assertAlmostEqual(s.bottom, 422.0, delta=0.05)
        self.assertEqual(s.staff_bands[0], (222.0, 242.0))

    def test_끝_마디선이_없으면_오선_끝을_경계로_쓴다(self):
        [s] = self.detect(self.system_with_bars(420.0, [200.0, 350.0]))
        self.assertEqual(s.barlines, [50.0, 200.0, 350.0, 500.0])

    def test_끝세로줄은_가짜_마디를_만들지_않는다(self):
        # 가는 선(495) + 굵은 선(497~500, 폭 3pt 라 마디선 후보가 아님). 오선 끝은 500.
        # 예전 규칙(4pt 초과면 오선 끝 추가)은 495~500 을 마디로 잡았다 — 실기기 몰다우.pdf 의 가짜 마디 "64"
        bottoms = self.system_staves(420.0)
        thick = [PathBox(497.0, b, 500.0, f32(b + 20.0), curved=False) for b in bottoms]
        [s] = self.detect(self.system_with_bars(420.0, [200.0, 350.0, 495.0]) + thick)
        self.assertEqual(s.barlines, [50.0, 200.0, 350.0, 495.0])
        self.assertEqual(s.measure_count, 3)

    def test_음표_머리가_붙은_세로선은_기둥이다(self):
        bottoms = self.system_staves(420.0)
        stems = [box for b in bottoms for box in (self.bar(280.0, b), self.head(280.0, b))]
        [s] = self.detect(self.system_with_bars(420.0, [200.0, 500.0]) + stems)
        self.assertEqual(s.barlines, [50.0, 200.0, 500.0],
                         '16분음표가 빽빽한 마디에서 기둥이 마디선으로 잡히던 문제(#037)')

    def test_일부_보표에만_있는_세로선은_마디선이_아니다(self):
        bottoms = self.system_staves(420.0)
        # 5개 보표 중 2개에만 — max(3, 5-1) = 4 개 이상이어야 마디선
        partial = [self.bar(280.0, b) for b in bottoms[:2]]
        [s] = self.detect(self.system_with_bars(420.0, [200.0, 500.0]) + partial)
        self.assertEqual(s.barlines, [50.0, 200.0, 500.0])

    def test_붙어있는_겹세로줄은_더_많은_보표에_있는_쪽_하나만(self):
        bottoms = self.system_staves(420.0)
        thin = [self.bar(350.0, b) for b in bottoms[:4]]    # 4개 보표
        thick = [self.bar(358.0, b) for b in bottoms]       # 5개 보표, 8pt 옆
        [s] = self.detect(self.system_with_bars(420.0, [200.0, 500.0]) + thin + thick)
        self.assertEqual(s.barlines, [50.0, 200.0, 358.0, 500.0])

    def test_시스템은_페이지_위부터_정렬한다(self):
        # 아래 시스템(y 100~300)을 먼저 넣어도 위 시스템(y 420~620)이 먼저 나와야 한다
        lower = self.system_with_bars(100.0, [300.0, 500.0])
        upper = self.system_with_bars(420.0, [200.0, 350.0, 500.0])
        systems = self.detect(lower + upper)
        self.assertEqual(len(systems), 2)
        self.assertEqual(systems[0].measure_count, 3)
        self.assertEqual(systems[1].measure_count, 2)
        self.assertTrue(systems[0].top < systems[1].top)

    # ── MuseScore 형식 (#056): 오선을 마디마다 끊어 그림 · 마디선이 보표 사이를 이음 · 음표 머리가 글자 · 보표 2개 시스템 ──

    def muse_score_system(self, low_bottom, bars):
        """보표 2개(아래 보표 아랫선 low_bottom, 보표 사이 25pt), 오선은 bars 사이마다 끊은 조각"""
        bottoms = [low_bottom, f32(low_bottom + 45.0)]
        edges = [50.0] + bars
        lines = [ln for b in bottoms for x0, x1 in zip(edges, edges[1:]) for ln in self.staff(b, x0, x1)]
        # 마디선: 위 보표 윗선 → 아래 보표 윗선 (보표 사이를 잇는다), 아래 보표 윗선 → 아랫선
        pieces = []
        for x in [50.0] + bars:
            pieces += [
                PathBox(f32(x - fl(0.4)), f32(low_bottom + 20.0), f32(x + fl(0.4)), f32(low_bottom + 65.0), curved=False),
                PathBox(f32(x - fl(0.4)), low_bottom, f32(x + fl(0.4)), f32(low_bottom + 20.0), curved=False),
            ]
        return lines + pieces

    def test_보표_두_개_시스템의_이어_그린_마디선과_끊어_그린_오선(self):
        # 60pt 짜리 짧은 마디 — 조각 하나로는 오선 폭 기준(80pt)에 못 미친다
        [s] = self.detect(self.muse_score_system(420.0, [110.0, 250.0, 400.0]))
        self.assertEqual(len(s.staff_bands), 2)
        self.assertEqual(s.barlines, [50.0, 110.0, 250.0, 400.0])
        self.assertEqual(s.measure_count, 3)

    def test_연결선이_있으면_간격이_좁아도_시스템을_나눈다(self):
        # 두 시스템 사이 간격 30pt (< 55pt) — 간격 규칙이면 보표 4개가 한 시스템이 된다
        upper = self.muse_score_system(500.0, [200.0, 400.0])
        lower = self.muse_score_system(405.0, [300.0, 400.0])
        systems = self.detect(upper + lower)
        self.assertEqual([len(s.staff_bands) for s in systems], [2, 2])
        self.assertEqual([s.measure_count for s in systems], [2, 2])

    def test_떨어진_가로_조각은_합치지_않는다(self):
        # 셋잇단 괄호처럼 같은 높이에 띄엄띄엄 있는 짧은 선은 오선이 아니다
        brackets = [self.line(60.0 + k * 50.0, 100.0 + k * 50.0, 300.0) for k in range(5)]
        self.assertEqual(self.detect(brackets), [])

    def test_글자로_찍힌_음표_머리가_붙은_세로선은_기둥이다(self):
        boxes = self.muse_score_system(420.0, [250.0, 400.0])
        # 두 보표를 모두 덮는 기둥 두 조각 (마디선과 같은 모양) + 위 끝에 SMuFL 음표 머리 글자 (원점 = 왼쪽, 세로 가운데)
        stem = [
            PathBox(f32(180.0 - fl(0.4)), 440.0, f32(180.0 + fl(0.4)), 485.0, curved=False),
            PathBox(f32(180.0 - fl(0.4)), 420.0, f32(180.0 + fl(0.4)), 440.0, curved=False),
        ]
        heads = [TextRun('', 176.0, 485.0, 19.0), TextRun('', 176.0, 440.0, 19.0)]
        [without_heads] = self.detect(boxes + stem)
        self.assertEqual(without_heads.barlines, [50.0, 180.0, 250.0, 400.0],
                         '음표 머리 글자가 없으면 마디선으로 보인다 — 이 테스트의 기둥이 실제로 속일 수 있는 모양인지 확인')
        [with_heads] = self.detect(boxes + stem, heads)
        self.assertEqual(with_heads.barlines, [50.0, 250.0, 400.0])

    def test_곡선_경로는_오선이_아니다(self):
        curved_lines = [PathBox(50.0, 400.0 + k * 5.0, 500.0, 400.5 + k * 5.0, curved=True) for k in range(5)]
        self.assertEqual(self.detect(curved_lines), [])

    def test_마디_번호는_페이지와_시스템을_넘어_이어진다(self):
        def system(top, *bars):
            return SystemLayout(top, f32(top + 200.0), bars[0], bars[-1], [], list(bars))
        pages = [
            PageLayout(0, 595.0, 842.0, [system(100.0, 50.0, 200.0, 350.0), system(400.0, 50.0, 300.0, 500.0, 550.0)]),
            PageLayout(1, 595.0, 842.0, []),
            PageLayout(2, 595.0, 842.0, [system(100.0, 50.0, 500.0)]),
        ]
        measures = to_measures(pages)

        self.assertEqual(measure_count(pages), 6)
        self.assertEqual([m['measureNumber'] for m in measures], list(range(1, 7)))
        self.assertEqual([m['pageIndex'] for m in measures], [0, 0, 0, 0, 0, 2])
        self.assertEqual([m['systemIndex'] for m in measures], [0, 0, 1, 1, 1, 0])
        third = measures[2]
        self.assertEqual(third['leftPt'], 50.0)
        self.assertEqual(third['rightPt'], 300.0)
        self.assertEqual(third['topPt'], 400.0)
        self.assertEqual(third['bottomPt'], 600.0)


# --------------------------------------------------------------------------------------------- StaffLabelDetectorTest

class StaffLabelDetectorTest(SimpleTestCase):
    """보표 이름 읽기 (P07). 시스템 = 보표 4개(높이 20pt, 간격 45pt), 왼쪽 끝 x=80. 텍스트는 해석기처럼 PDF y-up 으로 넣는다."""

    page_height = 842.0

    system = SystemLayout(
        top=100.0,
        bottom=255.0,
        left=80.0,
        right=560.0,
        staff_bands=[(f32(100.0 + k * 45.0), f32(120.0 + k * 45.0)) for k in range(4)],
        barlines=[80.0, 300.0, 560.0],
    )

    def label(self, text, staff, x=20.0, dy=0.0):
        """보표 staff 가운데 높이에 기준선을 둔 텍스트"""
        top, bottom = self.system.staff_bands[staff]
        return TextRun(text, x, f32(self.page_height - f32(f32(f32(f32(top + bottom) / 2) + 4.0) + dy)), 12.0)

    def labels(self, *runs):
        [system] = attach_labels(list(runs), [self.system], self.page_height)
        return system.staff_labels

    def test_보표마다_왼쪽_이름을_읽는다(self):
        self.assertEqual(
            self.labels(self.label('Violin I', 0), self.label('Violin II', 1), self.label('Viola', 2), self.label('Cello', 3)),
            ['Violin I', 'Violin II', 'Viola', 'Cello'],
        )

    def test_못_읽은_보표는_null(self):
        self.assertEqual(self.labels(self.label('진호', 0), self.label('은석', 3)), ['진호', None, None, '은석'])

    def test_시스템_안의_글자와_숫자는_이름이_아니다(self):
        in_system = self.label('pizz.', 1, x=120.0)
        measure_number = TextRun('5', 60.0, f32(self.page_height - 92.0), 10.0)   # 시스템 왼쪽 위 마디 번호
        digits_beside_staff = self.label('12', 2)
        self.assertEqual(self.labels(in_system, measure_number, digits_beside_staff), [None, None, None, None])

    def test_여러_조각은_위에서_아래_왼쪽에서_오른쪽으로_잇는다(self):
        # 두 줄 이름: "Clarinet" / "in B♭", 같은 줄은 조각이 둘
        runs = (
            self.label('in', 2, x=22.0, dy=6.0),
            self.label('B♭', 2, x=34.0, dy=6.0),
            self.label('Clarinet', 2, x=20.0, dy=-6.0),
        )
        self.assertEqual(self.labels(*runs)[2], 'Clarinet in B♭')

    def test_한_글자씩_찍힌_이름은_붙여_읽고_띄어_쓴_곳만_띄운다(self):
        # MuseScore: "Guitar 1" 을 글자마다 따로 (글꼴 12pt, 글자 간격 6pt, 띄어쓰기는 한 칸 더)
        xs = [20.0, 26.0, 32.0, 38.0, 44.0, 50.0, 62.0]
        runs = [self.label(c, 1, x=xs[i]) for i, c in enumerate('Guitar1')]
        self.assertEqual(self.labels(*runs)[1], 'Guitar 1')

    def test_보표_사이의_이름은_가까운_보표로(self):
        # 보표 0 과 1 사이(가운데 y 132.5)보다 조금 위 → 보표 0
        between = TextRun('Horn', 20.0, f32(self.page_height - (128.0 + 4.0)), 12.0)
        self.assertEqual(self.labels(between), ['Horn', None, None, None])

    def test_보표가_없는_시스템은_빈_목록(self):
        empty = replace(self.system, staff_bands=[])
        [system] = attach_labels([self.label('x', 0)], [empty], self.page_height)
        self.assertEqual(system.staff_labels, [])


# --------------------------------------------------------------------------------------------- TimeSignatureDetectorTest

def smufl(n):
    """MuseScore (#056): SMuFL 박자 숫자 글자(U+E080+n)"""
    return chr(0xE080 + n)


class TimeSignatureDetectorTest(SimpleTestCase):
    """
    박자표 찾기 규칙과 마디 적용. 실제 악보(Moldau 6/8)는 골든 테스트가 본다.

    시스템 = 보표 5개(높이 20pt, 간격 25pt), 위→아래 좌표. 텍스트는 해석기처럼 PDF y-up 으로 넣는다.
    """

    page_height = 842.0

    @staticmethod
    def system(top, barlines=(50.0, 200.0, 350.0, 500.0)):
        barlines = list(barlines)
        return SystemLayout(
            top=top,
            bottom=f32(top + 200.0),
            left=barlines[0],
            right=barlines[-1],
            staff_bands=[(f32(top + k * 45.0), f32(f32(top + k * 45.0) + 20.0)) for k in range(5)],
            barlines=barlines,
        )

    def signature_on(self, system, staff, x, numerator, denominator):
        """보표 staff 에 분자·분모를 Moldau 처럼 x 가 같게, 보표 높이 절반 간격으로 놓는다."""
        top, _ = system.staff_bands[staff]
        return [
            TextRun(str(numerator), x, f32(self.page_height - f32(top + 8.0)), 16.0),
            TextRun(str(denominator), x, f32(self.page_height - f32(top + 18.0)), 16.0),
        ]

    def on_all_staves(self, system, x, numerator, denominator):
        return [r for k in range(5) for r in self.signature_on(system, k, x, numerator, denominator)]

    def detect(self, runs, systems):
        return detect_time_signatures(runs, systems, self.page_height)

    def test_모든_보표에_있는_6_8_을_찾는다(self):
        s = self.system(100.0)
        self.assertEqual(self.detect(self.on_all_staves(s, 70.0, 6, 8), [s]), [TimeSignatureMark(0, 70.0, 6, 8)])

    def test_SMuFL_박자_숫자도_읽는다(self):
        s = self.system(100.0)
        runs = []
        for staff in range(5):
            top, _ = s.staff_bands[staff]
            runs += [TextRun(smufl(9), fl(124.6), f32(self.page_height - f32(top + 9.5)), 19.0),
                     TextRun(smufl(8), fl(124.6), f32(self.page_height - f32(top + 19.0)), 19.0)]
        self.assertEqual(self.detect(runs, [s]), [TimeSignatureMark(0, fl(124.6), 9, 8)])

    def test_한_글자씩_찍힌_두_자리_분자를_합친다(self):
        s = self.system(100.0)
        # "12" 는 원점이 7pt 떨어진 두 글자, "8" 은 그 가운데 아래
        runs = []
        for staff in range(5):
            top, _ = s.staff_bands[staff]
            runs += [
                TextRun(smufl(1), 120.0, f32(self.page_height - f32(top + 9.5)), 19.0),
                TextRun(smufl(2), 127.0, f32(self.page_height - f32(top + 9.5)), 19.0),
                TextRun(smufl(8), 123.5, f32(self.page_height - f32(top + 19.0)), 19.0),
            ]
        self.assertEqual(self.detect(runs, [s]), [TimeSignatureMark(0, 123.5, 12, 8)])

    def symbol_on_all_staves(self, s, text, x=76.0, size=20.0):
        """Sibelius Opus 글꼴: 보표마다 가운데 줄 높이에 기준선을 둔 기호 글자 한 개 (Arpeggione: x 76pt)"""
        return [TextRun(text, x, f32(self.page_height - f32(f32(top + bottom) / 2)), size) for top, bottom in s.staff_bands]

    def test_C_기호는_4_4_알라_브레베는_2_2(self):
        s = self.system(100.0)
        self.assertEqual(self.detect(self.symbol_on_all_staves(s, 'c'), [s]), [TimeSignatureMark(0, 76.0, 4, 4)])
        self.assertEqual(self.detect(self.symbol_on_all_staves(s, 'C'), [s]), [TimeSignatureMark(0, 76.0, 2, 2)])
        # MuseScore (SMuFL timeSigCommon)
        self.assertEqual(self.detect(self.symbol_on_all_staves(s, ''), [s]), [TimeSignatureMark(0, 76.0, 4, 4)])

    def test_작은_글자_c_는_박자표가_아니다(self):
        # 가사 · 코드 이름 크기(보표 높이 20pt 의 절반)
        s = self.system(100.0)
        self.assertEqual(self.detect(self.symbol_on_all_staves(s, 'c', size=10.0), [s]), [])

    def test_보표_과반에_없으면_박자표가_아니다(self):
        s = self.system(100.0)
        two_staves = self.signature_on(s, 0, 70.0, 3, 4) + self.signature_on(s, 1, 70.0, 3, 4)
        self.assertEqual(self.detect(two_staves, [s]), [])

    def test_분모가_2의_거듭제곱이_아니면_박자표가_아니다(self):
        s = self.system(100.0)
        self.assertEqual(self.detect(self.on_all_staves(s, 70.0, 6, 5), [s]), [])

    def test_혼자_있는_마디_번호나_운지는_무시한다(self):
        s = self.system(100.0)
        numbers = [
            TextRun('5', 50.0, f32(self.page_height - 90.0), 12.0),     # 보표 위 마디 번호
            TextRun('0', 140.0, f32(self.page_height - 125.0), 8.0),    # 운지
            TextRun('pizz.', 60.0, f32(self.page_height - 310.0), 10.0),
        ]
        self.assertTrue(all(m.numerator == 6 and m.denominator == 8
                            for m in self.detect(numbers + self.on_all_staves(s, 70.0, 6, 8), [s])))
        self.assertEqual(self.detect(numbers, [s]), [])

    def test_시스템_중간의_박자_바뀜도_찾는다(self):
        s = self.system(100.0)
        marks = self.detect(self.on_all_staves(s, 70.0, 6, 8) + self.on_all_staves(s, 210.0, 3, 4), [s])
        self.assertEqual(marks, [TimeSignatureMark(0, 70.0, 6, 8), TimeSignatureMark(0, 210.0, 3, 4)])

    def test_두_번째_시스템의_박자표는_그_시스템_번호로(self):
        upper = self.system(100.0)
        lower = self.system(450.0)
        marks = self.detect(self.on_all_staves(lower, 70.0, 2, 4), [upper, lower])
        self.assertEqual(marks, [TimeSignatureMark(1, 70.0, 2, 4)])

    def test_박자표는_놓인_마디부터_다음_박자표_전까지_적용된다(self):
        first = self.system(100.0)                                   # 마디 1~3
        second = self.system(450.0)                                  # 마디 4~6
        pages = [
            PageLayout(0, 595.0, 842.0, [first, second], [
                TimeSignatureMark(0, 70.0, 6, 8),                     # 마디 1 안
                TimeSignatureMark(1, 210.0, 3, 4),                    # 마디 5 (200~350) 안
            ]),
            PageLayout(1, 595.0, 842.0, [self.system(100.0)]),       # 마디 7~9: 이어서 3/4
        ]
        signatures = [(m['timeSigNumerator'], m['timeSigDenominator']) for m in to_measures(pages)]
        self.assertEqual(signatures, [(6, 8), (6, 8), (6, 8), (6, 8), (3, 4), (3, 4), (3, 4), (3, 4), (3, 4)])

    def test_첫_박자표_이전_마디는_박자를_모른다(self):
        s = self.system(100.0)
        pages = [PageLayout(0, 595.0, 842.0, [s], [TimeSignatureMark(0, 210.0, 3, 4)])]
        self.assertEqual([m['timeSigNumerator'] for m in to_measures(pages)], [None, 3, 3])


# --------------------------------------------------------------------------------------------- PathContentInterpreterTest

class Resolver:
    """Kotlin XObjectResolver — form(name) 은 (content, matrix, resolver) 또는 None, decode_text 기본값은 None"""

    def __init__(self, form=None, decode_text=None):
        self._form = form or (lambda name: None)
        self._decode = decode_text or (lambda font_name, data: None)

    def form(self, name):
        return self._form(name)

    def decode_text(self, font_name, data):
        return self._decode(font_name, data)


def form_x_object(content, matrix, resolver):
    """Kotlin FormXObject(content, matrix, resolver)"""
    return content, [f32(v) for v in matrix], resolver


# 글꼴 코드를 ISO-8859-1 로 해독하는 가짜 리소스
LATIN_FONTS = Resolver(decode_text=lambda font_name, data: data.decode('latin-1'))


def boxes(content, origin_x=0.0, origin_y=0.0, resolver=None):
    """textSink 없이 (경로만)"""
    if isinstance(content, str):
        content = content.encode('latin-1')
    return ContentInterpreter(origin_x, origin_y, collect_text=False).run(content, resolver).boxes


def texts(content, resolver=LATIN_FONTS):
    return ContentInterpreter(collect_text=True).run(content.encode('latin-1'), resolver).texts


class PathContentInterpreterTest(SimpleTestCase):
    """
    콘텐츠 스트림 경량 해석기 — PDF 문법 경계 사례.
    실제 악보에서 PdfBox 엔진과 같은 박스를 내는지는 앱의 계측 테스트 PathInterpreterEquivalenceTest 가 본다.
    """

    def test_직선_경로의_박스(self):
        self.assertEqual(boxes('10 20 m 30 40 l S'), [PathBox(10.0, 20.0, 30.0, 40.0, curved=False)])

    def test_곡선은_끝점만_넣고_곡선으로_표시한다(self):
        # 제어점(50)은 박스에 들어가지 않는다 — PdfBox 수집기·파이썬 분석과 같다
        self.assertEqual(boxes('0 0 m 10 50 20 50 30 0 c f'), [PathBox(0.0, 0.0, 30.0, 0.0, curved=True)])
        self.assertEqual(boxes('0 0 m 5 5 10 0 v f'), [PathBox(0.0, 0.0, 10.0, 0.0, curved=True)])
        self.assertEqual(boxes('0 0 m 5 5 10 0 y f'), [PathBox(0.0, 0.0, 10.0, 0.0, curved=True)])

    def test_사각형은_네_모서리(self):
        self.assertEqual(boxes('10 10 100 0.5 re f'), [PathBox(10.0, 10.0, 110.0, 10.5, curved=False)])

    def test_칠하기_전까지_점이_모인다(self):
        self.assertEqual(boxes('0 0 m 1 1 l 5 5 m 6 6 l S'), [PathBox(0.0, 0.0, 6.0, 6.0, curved=False)])

    def test_칠_연산자마다_박스를_넘긴다(self):
        for op in ['f', 'F', 'f*', 'B', 'B*', 'b', 'b*', 'S', 's', 'n']:
            self.assertEqual(len(boxes(f'0 0 m 1 1 l {op}')), 1, f'연산자 {op}')
        self.assertEqual(boxes('0 0 m 1 1 l h W'), [], 'W 와 h 는 박스를 넘기지 않는다')

    def test_클립_뒤_n_도_박스를_남긴다(self):
        self.assertEqual(boxes('0 0 595 842 re W n'), [PathBox(0.0, 0.0, 595.0, 842.0, curved=False)])

    def test_cm_은_q_Q_로_되돌린다(self):
        result = boxes('q 2 0 0 2 100 200 cm 0 0 m 10 10 l S Q 0 0 m 1 1 l S')
        self.assertEqual(result, [PathBox(100.0, 200.0, 120.0, 220.0, False), PathBox(0.0, 0.0, 1.0, 1.0, False)])

    def test_cm_은_새_행렬을_앞에_곱한다(self):
        # Microsoft Print to PDF 가 쓰는 형태: 페이지 뒤집기 후 0.75 배율
        result = boxes('q 1 0 0 -1 0 842 cm 0.75 0 0 0.75 10 0 cm 0 0 m 4 4 l S Q')
        self.assertEqual(result, [PathBox(10.0, 839.0, 13.0, 842.0, False)])

    def test_페이지_원점을_뺀다(self):
        self.assertEqual(boxes('10 10 m 20 20 l S', origin_x=5.0, origin_y=7.0), [PathBox(5.0, 3.0, 15.0, 13.0, False)])

    def test_짝이_맞지_않는_Q_는_무시한다(self):
        self.assertEqual(boxes('Q Q 1 1 m 2 2 l S'), [PathBox(1.0, 1.0, 2.0, 2.0, False)])

    def test_문자열_안의_연산자는_실행하지_않는다(self):
        content = '(0 0 m 10 10 l S) Tj (a\\) 5 5 m (nested) 9 9 l S) Tj <4142> Tj [(a) -120 (b)] TJ 1 2 m 3 4 l S'
        self.assertEqual(boxes(content), [PathBox(1.0, 2.0, 3.0, 4.0, False)])

    def test_배열_딕셔너리_안의_숫자는_피연산자가_아니다(self):
        # TJ 배열의 숫자나 마킹 콘텐츠 속성이 다음 연산자의 피연산자로 새면 좌표가 틀어진다
        self.assertEqual(boxes('/Span <</MCID 3 /Rect [7 8 9]>> BDC 1 2 m 3 4 l S EMC'), [PathBox(1.0, 2.0, 3.0, 4.0, False)])
        self.assertEqual(boxes('[1 2 3] 0 d 5 5 m 6 6 l S'), [PathBox(5.0, 5.0, 6.0, 6.0, False)])

    def test_구분자에_붙은_토큰도_읽는다(self):
        self.assertEqual(boxes('[1 2]0 d/GS1 gs 1 1 m 2 2 l S'), [PathBox(1.0, 1.0, 2.0, 2.0, False)])

    def test_주석은_건너뛴다(self):
        self.assertEqual(boxes('% 0 0 m 9 9 l S\n1 1 m 2 2 l S'), [PathBox(1.0, 1.0, 2.0, 2.0, False)])

    def test_피연산자가_모자라면_연산자를_건너뛴다(self):
        self.assertEqual(boxes('5 m 1 1 m 2 2 l S'), [PathBox(1.0, 1.0, 2.0, 2.0, False)])

    def test_숫자_형식(self):
        self.assertEqual(boxes('.5 -.5 m +1. 2 l S'), [PathBox(0.5, -0.5, 1.0, 2.0, False)])

    def test_인라인_이미지_데이터는_건너뛴다(self):
        head = 'BI /W 2 /H 2 /BPC 8 /CS /G ID '.encode('latin-1')
        data = bytes([0x31, 0x20, 0x31, 0x20, 0x6D, 0x0A, 0x53, 0x66])   # "1 1 m\nSf" 처럼 보이는 바이너리
        tail = ' EI 1 1 m 2 2 l S'.encode('latin-1')
        self.assertEqual(boxes(head + data + tail), [PathBox(1.0, 1.0, 2.0, 2.0, False)])

    def test_Form_XObject_는_행렬을_곱해_실행한다(self):
        form = form_x_object(b'0 0 m 10 10 l S', [2.0, 0.0, 0.0, 2.0, 5.0, 5.0], resolver=None)
        resolver = Resolver(form=lambda name: form if name == 'Fm1' else None)
        result = boxes('q 1 0 0 1 100 0 cm /Fm1 Do Q /Im0 Do 0 0 m 1 1 l S', resolver=resolver)
        self.assertEqual(result, [PathBox(105.0, 5.0, 125.0, 25.0, False), PathBox(0.0, 0.0, 1.0, 1.0, False)])

    def test_Form_XObject_안의_Q_는_바깥_상태를_꺼내지_못한다(self):
        form = form_x_object(b'Q Q Q', [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], None)
        resolver = Resolver(form=lambda name: form)
        # Do 뒤에도 바깥 cm(×3)이 살아 있어야 한다
        result = boxes('q 3 0 0 3 0 0 cm /Fm1 Do 1 1 m 2 2 l S Q', resolver=resolver)
        self.assertEqual(result, [PathBox(3.0, 3.0, 6.0, 6.0, False)])

    def test_자기_자신을_부르는_Form_은_깊이_제한에서_멈춘다(self):
        resolver = Resolver(form=lambda name: form_x_object(b'0 0 m 1 1 l S /Loop Do', [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], resolver))
        result = boxes('/Loop Do', resolver=resolver)
        self.assertEqual(len(result), 8)

    def test_이름의_16진_이스케이프를_푼다(self):
        asked = []
        boxes('/Fm#201 Do', resolver=Resolver(form=lambda name: asked.append(name)))
        self.assertEqual(asked, ['Fm 1'])

    # --- 텍스트 (박자표 읽기용) ---

    def test_텍스트_행렬의_위치와_글꼴_크기(self):
        self.assertEqual(texts('BT /F1 12 Tf 1 0 0 1 100 200 Tm (6) Tj ET'), [TextRun('6', 100.0, 200.0, 12.0)])

    def test_Td_는_누적하고_TD_는_행간을_정한다(self):
        result = texts('BT /F1 10 Tf 10 20 Td (a) Tj 5 -3 TD (b) Tj T* (c) Tj ET')
        self.assertEqual(result, [TextRun('a', 10.0, 20.0, 10.0), TextRun('b', 15.0, 17.0, 10.0), TextRun('c', 15.0, 14.0, 10.0)])

    def test_작은따옴표는_다음_줄에서_보여준다(self):
        result = texts("BT /F1 10 Tf 12 TL 0 100 Td (a) Tj (b) ' ET")
        self.assertEqual(result, [TextRun('a', 0.0, 100.0, 10.0), TextRun('b', 0.0, 88.0, 10.0)])

    def test_TJ_배열의_문자열을_잇는다(self):
        self.assertEqual([t.text for t in texts('BT /F1 10 Tf 0 0 Td [(1) -250 (2)] TJ ET')], ['12'])

    def test_헥사_문자열과_리터럴_이스케이프를_푼다(self):
        self.assertEqual([t.text for t in texts('BT /F1 10 Tf <3638> Tj (\\061\\(x\\)) Tj ET')], ['68', '1(x)'])

    def test_뒤집힌_CTM_에서도_위치와_크기가_맞다(self):
        # Microsoft Print to PDF 형태: 페이지를 뒤집고 텍스트 행렬도 뒤집는다
        result = texts('1 0 0 -1 0 842 cm BT /F1 10 Tf 1 0 0 -1 50 100 Tm (8) Tj ET')
        self.assertEqual(result, [TextRun('8', 50.0, 742.0, 10.0)])

    def test_텍스트를_모아도_경로와_피연산자는_그대로다(self):
        it = ContentInterpreter(collect_text=True).run(b'BT /F1 10 Tf (1 2 m) Tj ET 1 1 m 2 2 l S', LATIN_FONTS)
        self.assertEqual(it.boxes, [PathBox(1.0, 1.0, 2.0, 2.0, False)])
        self.assertEqual([t.text for t in it.texts], ['1 2 m'])

    def test_글꼴을_모르면_텍스트를_넘기지_않는다(self):
        self.assertEqual(texts('BT /F1 10 Tf (6) Tj ET', resolver=Resolver()), [])
        self.assertEqual(texts('BT (6) Tj ET'), [], 'Tf 없이 보여 주면 무시')
