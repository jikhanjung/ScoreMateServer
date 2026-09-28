"""
악보 구조 분석 — PDF 에서 시스템 · 보표 · 마디선 · 박자표 · 보표 이름. **TV 앱(MrgqPdfViewer) 의 `score/` 를 그대로 옮겼다**:

  PathContentInterpreter.kt → ContentInterpreter   (콘텐츠 스트림을 직접 읽는 경량 해석기)
  StaffSystemDetector.kt    → detect_systems        (오선 · 보표 · 시스템 · 마디선)
  StaffLabelDetector.kt     → attach_labels         (보표 왼쪽 이름)
  TimeSignatureDetector.kt  → detect_time_signatures
  ScoreLayout.kt            → to_measures · to_staves (앱 DB 의 ScoreMeasure · ScoreStaff 행)

앱과 같은 결과를 내는 것이 목적이다 — 임계값 · 규칙 · 반올림을 바꾸지 않는다(바꿀 때는 앱과 함께).
PyMuPDF 는 앱의 PdfBox 처럼 문서 열기 · 스트림 압축 해제 · XObject · 글꼴(ToUnicode) 조회에만 쓴다.
좌표: 해석 단계는 PDF 사용자 공간(원점 좌하단, y 위로) — 결과(SystemLayout 등)는 앱처럼 위→아래, 페이지 좌상단 원점.
"""
import math
import re
import struct
from dataclasses import dataclass, field, replace

import fitz  # PyMuPDF

FORMAT = 'scoremate-score-layout'
FORMAT_VERSION = 1
SOURCE = 'MrgqPdfViewer app/src/main/java/com/mrgq/pdfviewer/score (2026-09-28)'


# --------------------------------------------------------------------------------------------- 모델

@dataclass
class PathBox:
    x0: float
    y0: float
    x1: float
    y1: float
    curved: bool

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0


@dataclass
class TextRun:
    text: str
    x: float
    y: float
    size: float


@dataclass
class SystemLayout:
    top: float
    bottom: float
    left: float
    right: float
    staff_bands: list          # [(위 오선, 아래 오선)] 위 보표부터
    barlines: list             # 첫 값 = 시스템 왼쪽 끝, 마지막 = 끝 마디선
    staff_labels: list = field(default_factory=list)

    @property
    def measure_count(self):
        return max(len(self.barlines) - 1, 0)


@dataclass
class TimeSignatureMark:
    system_index: int
    x: float
    numerator: int
    denominator: int


@dataclass
class PageLayout:
    page_index: int
    width_pt: float
    height_pt: float
    systems: list
    time_signatures: list = field(default_factory=list)


_F32 = struct.Struct('f')


def f32(v):
    """앱은 Float(32비트)로 계산한다 — **Float 연산 하나마다** 이것을 거친다: f32(a op b) 는 Kotlin 의 a op b 와 같다
    (두 float 의 + - * / 를 double 로 한 뒤 float 로 반올림하면 float 로 바로 한 것과 같다). 넘치면 무한대(Kotlin 과 같이)"""
    try:
        return _F32.unpack(_F32.pack(v))[0]
    except OverflowError:
        return math.copysign(math.inf, v)


def round1(v):
    """Kotlin Math.round(v * 10f) / 10f — Float 결과. Math.round 는 .5 에서 위로, NaN 은 0, Int 범위로 자른다"""
    x = f32(f32(v) * f32(10.0))
    if math.isnan(x):
        n = 0
    elif x >= 2147483647:
        n = 2147483647
    elif x <= -2147483648:
        n = -2147483648
    else:
        n = math.floor(x + 0.5)
    return f32(f32(n) / f32(10.0))


# Kotlin Char.isWhitespace (JVM: Character.isWhitespace || isSpaceChar) — 파이썬 isspace 와는 U+0085 만 다르다
_KT_WHITESPACE = ''.join(c for c in map(chr, range(0x3001)) if c.isspace() and c != '\x85')


def kt_trim(s):
    """Kotlin String.trim()"""
    return s.strip(_KT_WHITESPACE)


def kt_length(s):
    """Kotlin String.length — UTF-16 코드 단위 수 (BMP 밖 글자는 2)"""
    return len(s) + sum(1 for c in s if ord(c) > 0xFFFF)


def kt_json_float(v):
    """Float 를 JSON 에 — Kotlin Float.toString 처럼 그 Float 로 되돌아오는 가장 짧은 십진수"""
    if not isinstance(v, float) or not math.isfinite(v):
        return v
    for digits in range(1, 10):
        s = float(f'{v:.{digits}g}')
        if f32(s) == v:
            return s
    return v


# --------------------------------------------------------------------------------------------- 해석기

WHITESPACE = b' \n\r\t\f\x00'
DELIMITERS = b'()<>[]{}/%'
TOKEN_END = re.compile(rb'[ \n\r\t\f\x00()<>\[\]{}/%]')
MAX_OPERANDS = 32
MAX_FORM_DEPTH = 8


class ContentInterpreter:
    """PathContentInterpreter.kt 와 같은 동작 — 칠하거나 끝낸 경로마다 바운딩 박스, 텍스트 연산마다 TextRun.

    경로 점: m · l 은 그 점, c · v · y 는 끝점만 + 곡선 표시, re 는 네 모서리. f F f* B B* b b* S s n 에서 박스.
    Do: Form XObject 면 행렬을 곱해 실행(깊이 8). 텍스트: BT Tf Td TD Tm T* TL, Tj TJ ' " 에서 TextRun(글리프 폭 이동은 없다).
    """

    def __init__(self, origin_x=0.0, origin_y=0.0, collect_text=True):
        self.origin_x, self.origin_y = origin_x, origin_y
        self.collect_text = collect_text
        self.boxes, self.texts = [], []
        self.operands = []
        self.name_span = None        # Kotlin nameStart/nameEnd — 이름은 쓸 때 **그때의 content** 에서 푼다
        self.ctm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        self.saved = []
        self.floor = 0
        self.points = None           # [minx, miny, maxx, maxy]
        self.curved = False
        self.text_matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        self.line_matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        self.font_name = None
        self.font_size = 0.0
        self.leading = 0.0
        self.text_bytes = bytearray()

    def run(self, content, resolver=None):
        self._interpret(content, resolver, 0)
        return self

    # -- 토큰 --
    def _interpret(self, content, resolver, depth):
        n = len(content)
        i = 0
        array_depth = dict_depth = 0
        collect = self.collect_text
        while i < n:
            b = content[i]
            if b in WHITESPACE:
                i += 1
            elif b == 0x25:                                   # %
                while i < n and content[i] not in (10, 13):
                    i += 1
            elif b == 0x28:                                   # (
                i = self._read_literal(content, i) if collect and dict_depth == 0 else _skip_literal(content, i)
            elif b == 0x3C:                                   # <
                if i + 1 < n and content[i + 1] == 0x3C:
                    dict_depth += 1
                    i += 2
                else:
                    i = self._read_hex(content, i) if collect and dict_depth == 0 else _skip_hex(content, i)
            elif b == 0x3E:                                   # >
                if i + 1 < n and content[i + 1] == 0x3E:
                    dict_depth = max(0, dict_depth - 1)
                    i += 2
                else:
                    i += 1
            elif b == 0x5B:
                array_depth += 1
                i += 1
            elif b == 0x5D:
                array_depth = max(0, array_depth - 1)
                i += 1
            elif b in (0x7B, 0x7D, 0x29):
                i += 1
            elif b == 0x2F:                                   # /name
                end = _regular_end(content, i + 1)
                if array_depth == 0 and dict_depth == 0:
                    self.name_span = (i + 1, end)
                i = end
            else:
                end = max(_regular_end(content, i), i + 1)
                if array_depth > 0 or dict_depth > 0:
                    i = end
                elif b in b'0123456789-+.':
                    self._push_number(content, i, end)
                    i = end
                else:
                    i = self._operator(content, i, end, resolver, depth)

    def _push_number(self, content, start, end):
        """Kotlin pushNumber 그대로 — 부호, 정수부, '.' 뒤 소수부만 double 로 쌓아 Float 로. 지수 · 나머지 글자는 무시"""
        j = start
        negative = False
        sign = content[j]
        if sign == 0x2D or sign == 0x2B:
            negative = sign == 0x2D
            j += 1
        value = 0.0
        digits = False
        while j < end and 0x30 <= content[j] <= 0x39:
            value = value * 10 + (content[j] - 0x30)
            digits = True
            j += 1
        if j < end and content[j] == 0x2E:
            j += 1
            scale = 0.1
            while j < end and 0x30 <= content[j] <= 0x39:
                value += (content[j] - 0x30) * scale
                scale *= 0.1
                digits = True
                j += 1
        if not digits:
            return                                        # "-" 같은 깨진 토큰은 무시
        value = f32(-value if negative else value)
        if len(self.operands) == MAX_OPERANDS:
            self.operands.pop(0)
        self.operands.append(value)

    def _op(self, from_end):
        return self.operands[-from_end]

    def _operator(self, content, start, end, resolver, depth):
        token = content[start:end]
        nxt = end
        count = len(self.operands)
        if len(token) == 1:
            c = token
            if c == b'q':
                self._save()
            elif c == b'Q':
                self._restore()
            elif c in (b'm', b'l') and count >= 2:
                self._add_point(self._op(2), self._op(1))
            elif c == b'c' and count >= 6:
                self.curved = True
                self._add_point(self._op(2), self._op(1))
            elif c in (b'v', b'y') and count >= 4:
                self.curved = True
                self._add_point(self._op(2), self._op(1))
            elif c in (b'f', b'F', b'B', b'b', b'S', b's', b'n'):
                self._finish_path()
            elif c in (b"'", b'"') and self.collect_text:
                self._next_line()
                self._emit_text(resolver)
        elif len(token) == 2:
            if token == b'cm' and count >= 6:
                self._concat(*[self._op(k) for k in (6, 5, 4, 3, 2, 1)])
            elif token == b're' and count >= 4:
                x, y, w, h = self._op(4), self._op(3), self._op(2), self._op(1)
                for px, py in ((x, y), (f32(x + w), y), (f32(x + w), f32(y + h)), (x, f32(y + h))):
                    self._add_point(px, py)
            elif token in (b'f*', b'B*', b'b*'):
                self._finish_path()
            elif token == b'Do':
                self._draw_xobject(content, resolver, depth)
            elif token == b'BI':
                nxt = _skip_inline_image(content, end)
            elif self.collect_text and token == b'BT':
                self.text_matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
                self.line_matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
            elif self.collect_text and token[:1] == b'T':
                self._text_operator(content, token[1:2], resolver)
        self.operands = []
        self.name_span = None
        self.text_bytes = bytearray()
        return nxt

    def _text_operator(self, content, c1, resolver):
        count = len(self.operands)
        if c1 == b'f':
            if count >= 1 and self.name_span is not None:
                self.font_name = _decode_name(content, *self.name_span)
                self.font_size = self._op(1)
        elif c1 == b'd':
            if count >= 2:
                self._move_text(self._op(2), self._op(1))
        elif c1 == b'D':
            if count >= 2:
                self.leading = -self._op(1)
                self._move_text(self._op(2), self._op(1))
        elif c1 == b'm':
            if count >= 6:
                self.line_matrix = [self._op(6 - k) for k in range(6)]
                self.text_matrix = list(self.line_matrix)
        elif c1 == b'*':
            self._next_line()
        elif c1 == b'L':
            if count >= 1:
                self.leading = self._op(1)
        elif c1 in (b'j', b'J'):
            self._emit_text(resolver)

    # -- 경로 --
    def _add_point(self, x, y):
        m = self.ctm
        px = f32(f32(f32(f32(m[0] * x) + f32(m[2] * y)) + m[4]) - self.origin_x)
        py = f32(f32(f32(f32(m[1] * x) + f32(m[3] * y)) + m[5]) - self.origin_y)
        if self.points is None:
            self.points = [px, py, px, py]
        else:
            p = self.points
            p[0], p[1], p[2], p[3] = min(p[0], px), min(p[1], py), max(p[2], px), max(p[3], py)

    def _finish_path(self):
        if self.points is not None:
            self.boxes.append(PathBox(self.points[0], self.points[1], self.points[2], self.points[3], self.curved))
        self.points = None
        self.curved = False

    def _concat(self, a, b, c, d, e, f):
        a2, b2, c2, d2, e2, f2 = self.ctm
        self.ctm = [f32(f32(a * a2) + f32(b * c2)), f32(f32(a * b2) + f32(b * d2)),
                    f32(f32(c * a2) + f32(d * c2)), f32(f32(c * b2) + f32(d * d2)),
                    f32(f32(f32(e * a2) + f32(f * c2)) + e2), f32(f32(f32(e * b2) + f32(f * d2)) + f2)]

    def _save(self):
        self.saved.append(list(self.ctm))

    def _restore(self):
        if len(self.saved) > self.floor:
            self.ctm = self.saved.pop()

    def _draw_xobject(self, content, resolver, depth):
        if resolver is None or self.name_span is None or depth >= MAX_FORM_DEPTH:
            return
        form = resolver.form(_decode_name(content, *self.name_span))
        if form is None:
            return
        form_content, matrix, inner = form
        outer_floor = self.floor
        self._save()
        self.floor = len(self.saved)
        self._concat(*matrix)
        # Kotlin 과 같이 피연산자 · 이름 · 텍스트 버퍼를 비우지 않고 폼 내용을 시작한다 (Do 뒤에 _operator 가 비운다)
        self._interpret(form_content, inner if inner is not None else resolver, depth + 1)
        del self.saved[self.floor:]
        self.floor = outer_floor
        self._restore()

    # -- 텍스트 --
    def _move_text(self, tx, ty):
        lm = self.line_matrix
        lm[4] = f32(lm[4] + f32(f32(tx * lm[0]) + f32(ty * lm[2])))
        lm[5] = f32(lm[5] + f32(f32(tx * lm[1]) + f32(ty * lm[3])))
        self.text_matrix = list(lm)

    def _next_line(self):
        self._move_text(0.0, -self.leading)

    def _emit_text(self, resolver):
        if not self.collect_text or self.font_name is None or not self.text_bytes or resolver is None:
            return
        text = resolver.decode_text(self.font_name, bytes(self.text_bytes))
        if text is None:
            return
        tm, m = self.text_matrix, self.ctm
        tx, ty = tm[4], tm[5]
        x = f32(f32(f32(f32(m[0] * tx) + f32(m[2] * ty)) + m[4]) - self.origin_x)
        y = f32(f32(f32(f32(m[1] * tx) + f32(m[3] * ty)) + m[5]) - self.origin_y)
        vx, vy = f32(tm[2] * self.font_size), f32(tm[3] * self.font_size)
        size = f32(math.hypot(f32(f32(m[0] * vx) + f32(m[2] * vy)), f32(f32(m[1] * vx) + f32(m[3] * vy))))
        self.texts.append(TextRun(text, x, y, size))

    def _read_literal(self, content, start):
        n = len(content)
        depth = 0
        j = start
        out = self.text_bytes
        while j < n:
            c = content[j]
            if c == 0x28:
                if depth > 0:
                    out.append(c)
                depth += 1
                j += 1
            elif c == 0x29:
                depth -= 1
                if depth == 0:
                    return j + 1
                out.append(c)
                j += 1
            elif c == 0x5C:
                if j + 1 >= n:
                    return n
                e = content[j + 1]
                if 0x30 <= e <= 0x37:
                    value, k = 0, j + 1
                    while k < n and k < j + 4 and 0x30 <= content[k] <= 0x37:
                        value = value * 8 + content[k] - 0x30
                        k += 1
                    out.append(value & 0xFF)
                    j = k
                elif e in b'nrtbf':
                    out.append({0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}[e])
                    j += 2
                elif e in (13, 10):
                    j += 2
                    if e == 13 and j < n and content[j] == 10:
                        j += 1
                else:
                    out.append(e)
                    j += 2
            else:
                out.append(c)
                j += 1
        return n

    def _read_hex(self, content, start):
        j = start + 1
        high = -1
        n = len(content)
        while j < n:
            c = content[j]
            if c == 0x3E:
                if high >= 0:
                    self.text_bytes.append(high << 4)
                return j + 1
            v = _hex_value(c)
            if v >= 0:
                if high < 0:
                    high = v
                else:
                    self.text_bytes.append((high << 4) | v)
                    high = -1
            j += 1
        return n


def _regular_end(content, start):
    m = TOKEN_END.search(content, start)
    return m.start() if m else len(content)


def _skip_literal(content, start):
    depth = 0
    j = start
    n = len(content)
    while j < n:
        c = content[j]
        if c == 0x5C:
            j += 2
        elif c == 0x28:
            depth += 1
            j += 1
        elif c == 0x29:
            depth -= 1
            j += 1
            if depth == 0:
                return j
        else:
            j += 1
    return n


def _skip_hex(content, start):
    end = content.find(b'>', start + 1)
    return len(content) if end < 0 else end + 1


def _hex_value(c):
    if 0x30 <= c <= 0x39:
        return c - 0x30
    if 0x61 <= c <= 0x66:
        return c - 0x61 + 10
    if 0x41 <= c <= 0x46:
        return c - 0x41 + 10
    return -1


def _skip_inline_image(content, start):
    n = len(content)
    j = start
    data = -1
    while j + 1 < n:
        if content[j] == 0x49 and content[j + 1] == 0x44 and \
                (j == 0 or content[j - 1] in WHITESPACE or content[j - 1] in DELIMITERS) and \
                (j + 2 >= n or content[j + 2] in WHITESPACE):
            data = j + 3
            break
        j += 1
    if data < 0:
        return n
    k = data
    while k + 1 < n:
        if content[k] == 0x45 and content[k + 1] == 0x49 and k > 0 and content[k - 1] in WHITESPACE and \
                (k + 2 >= n or content[k + 2] in WHITESPACE or content[k + 2] in DELIMITERS):
            return k + 2
        k += 1
    return n


def _kt_hex_int(two):
    """Kotlin String.toIntOrNull(16) — 두 글자, 앞의 + · - 부호도 받는다"""
    sign, body = 1, two
    if two[:1] in ('-', '+'):
        sign, body = (-1 if two[0] == '-' else 1), two[1:]
    if not body or any(c not in '0123456789abcdefABCDEF' for c in body):
        return None
    return sign * int(body, 16)


def _decode_name(content, start, end):
    """Kotlin decodeName — 이름의 #xx 이스케이프를 푼다 (/Fm#201 → "Fm 1"). 범위가 content 밖이면 Kotlin 처럼 예외"""
    if end > len(content):
        raise IndexError('name span outside content')
    out = []
    j = start
    while j < end:
        c = content[j]
        if c == 0x23 and j + 2 < end:
            value = _kt_hex_int(content[j + 1:j + 3].decode('latin-1'))
            if value is not None:
                out.append(chr(value & 0xFFFF))            # Int.toChar() — 하위 16비트
                j += 3
                continue
        out.append(chr(c))
        j += 1
    return ''.join(out)


# --------------------------------------------------------------------------------------------- 리소스 (PdfBoxContent.kt)

STANDARD_GLYPHS = {'space': ' ', 'period': '.', 'comma': ',', 'hyphen': '-', 'slash': '/', 'colon': ':',
                   'parenleft': '(', 'parenright': ')', 'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
                   'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'}


def _glyph_to_unicode(name):
    if name in STANDARD_GLYPHS:
        return STANDARD_GLYPHS[name]
    if len(name) == 1:
        return name
    m = re.fullmatch(r'uni([0-9A-Fa-f]{4})', name) or re.fullmatch(r'u([0-9A-Fa-f]{4,6})', name)
    return chr(int(m.group(1), 16)) if m else None


def _parse_cmap(data):
    """ToUnicode CMap → ({코드 바이트: 문자열}, 코드 바이트 길이 목록)"""
    text = data.decode('latin-1', errors='replace')
    mapping, lengths = {}, set()

    def to_bytes(h):
        return bytes.fromhex(h if len(h) % 2 == 0 else h + '0')

    def to_text(h):
        raw = to_bytes(h)
        try:
            return raw.decode('utf-16-be')
        except UnicodeDecodeError:
            return None
    for block in re.findall(r'begincodespacerange(.*?)endcodespacerange', text, re.S):
        for lo, _ in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            lengths.add(len(lo) // 2)
    for block in re.findall(r'beginbfchar(.*?)endbfchar', text, re.S):
        for src, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>', block):
            mapping[to_bytes(src)] = to_text(dst)
            lengths.add(len(src) // 2)
    for block in re.findall(r'beginbfrange(.*?)endbfrange', text, re.S):
        for lo, hi, rest in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)', block):
            size = len(lo) // 2
            lengths.add(size)
            start, stop = int(lo, 16), int(hi, 16)
            if rest.startswith('['):
                targets = re.findall(r'<([0-9A-Fa-f]*)>', rest)
                for k, code in enumerate(range(start, stop + 1)):
                    if k < len(targets):
                        mapping[code.to_bytes(size, 'big')] = to_text(targets[k])
            else:
                base = int(rest[1:-1] or '0', 16)
                width = len(rest[1:-1])
                for k, code in enumerate(range(start, stop + 1)):
                    mapping[code.to_bytes(size, 'big')] = to_text(format(base + k, f'0{width}X'))
    return mapping, sorted(lengths) or [1]


class Resources:
    """PdfBoxXObjects 와 같은 역할 — Form XObject(내용 · 행렬 · 리소스)와 글꼴 해독.
    owner_xref = /Resources 를 가진 객체(없으면 None — 리소스 없음). 폼에 리소스가 있으면 **그것만**, 없으면 바깥 것을 쓴다
    (Kotlin: PdfBoxXObjects(form.resources ?: resources) — 섞지 않는다)"""

    def __init__(self, doc, owner_xref):
        self.doc, self.owner = doc, owner_xref
        self.fonts = {}

    @classmethod
    def for_page(cls, doc, page):
        """PDPage.getResources — /Resources 는 페이지 트리에서 상속된다"""
        xref = page.xref
        for _ in range(64):
            if doc.xref_get_key(xref, 'Resources')[0] != 'null':
                return cls(doc, xref)
            kind, parent = doc.xref_get_key(xref, 'Parent')
            if kind != 'xref':
                break
            xref = int(parent.split()[0])
        return cls(doc, None)

    def _resource(self, category, name):
        if self.owner is None:
            return None
        kind, value = self.doc.xref_get_key(self.owner, f'Resources/{category}/{name}')
        if kind == 'xref':
            return int(value.split()[0])
        return None

    def form(self, name):
        xref = self._resource('XObject', name)
        if xref is None:
            return None
        if self.doc.xref_get_key(xref, 'Subtype')[1] != '/Form':
            return None                       # 이미지 — 경로가 아니다
        try:
            content = self.doc.xref_stream(xref) or b''
        except Exception:  # noqa: BLE001
            return None
        kind, value = self.doc.xref_get_key(xref, 'Matrix')
        matrix = [float(v) for v in re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value)] if kind == 'array' else []
        # PdfBox Matrix.createMatrix: 숫자 6개 이상이면 앞의 6개, 아니면 단위 행렬
        matrix = matrix[:6] if len(matrix) >= 6 else [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        has_own = self.doc.xref_get_key(xref, 'Resources')[0] != 'null'
        inner = Resources(self.doc, xref) if has_own else self
        return content, [f32(v) for v in matrix], inner

    def decode_text(self, font_name, data):
        if font_name not in self.fonts:
            self.fonts[font_name] = self._load_font(font_name)
        font = self.fonts[font_name]
        if font is None:
            return None
        mapping, lengths, simple = font
        out, i = [], 0
        while i < len(data):
            for size in lengths:
                code = data[i:i + size]
                if code in mapping:
                    if mapping[code]:
                        out.append(mapping[code])
                    i += size
                    break
            else:
                if simple is not None and data[i] in simple:
                    out.append(simple[data[i]])
                i += lengths[0]
        return ''.join(out) or None

    def _load_font(self, name):
        xref = self._resource('Font', name)
        if xref is None:
            return None
        doc = self.doc
        mapping, lengths = {}, [1]
        kind, value = doc.xref_get_key(xref, 'ToUnicode')
        if kind == 'xref':
            try:
                mapping, lengths = _parse_cmap(doc.xref_stream(int(value.split()[0])) or b'')
            except Exception:  # noqa: BLE001
                mapping, lengths = {}, [1]
        subtype = doc.xref_get_key(xref, 'Subtype')[1]
        simple = None
        if subtype != '/Type0':
            simple = {code: chr(code) for code in range(32, 127)}          # 표준 · WinAnsi 의 ASCII 부분
            enc_kind, enc = doc.xref_get_key(xref, 'Encoding')
            differences = ''
            if enc_kind == 'xref':
                differences = doc.xref_get_key(int(enc.split()[0]), 'Differences')[1] or ''
            elif enc_kind == 'dict':
                differences = doc.xref_get_key(xref, 'Encoding/Differences')[1] or ''
            code = None
            for token in re.findall(r'/[^\s/\[\]]+|\d+', differences or ''):
                if token.startswith('/'):
                    if code is not None:
                        glyph = _glyph_to_unicode(token[1:])
                        if glyph:
                            simple[code] = glyph
                        code += 1
                else:
                    code = int(token)
        elif not mapping:
            return None
        return mapping, sorted(set(lengths), reverse=True), simple


def _inherited(doc, xref, key):
    """PDPageTree.getInheritableAttribute — 페이지에서 Parent 를 따라 처음 있는 값 (kind, value), 간접 참조는 푼다"""
    for _ in range(64):
        kind, value = doc.xref_get_key(xref, key)
        if kind != 'null':
            if kind == 'xref':
                value = doc.xref_object(int(value.split()[0]), compressed=True).strip()
                kind = 'array' if value.startswith('[') else 'other'
            return kind, value
        parent_kind, parent = doc.xref_get_key(xref, 'Parent')
        if parent_kind != 'xref':
            break
        xref = int(parent.split()[0])
    return 'null', None


def _rectangle(kind, value):
    """PDRectangle(COSArray) — Float 4개(모자라면 0), 좌하단 = min · 우상단 = max. 배열이 아니면 None"""
    if kind != 'array':
        return None
    v = ([f32(float(n)) for n in re.findall(r'[-+]?\d*\.?\d+', value)] + [0.0] * 4)[:4]
    return [min(v[0], v[2]), min(v[1], v[3]), max(v[0], v[2]), max(v[1], v[3])]


def _page_box(doc, page):
    """PDPage.getCropBox — CropBox 를 MediaBox 로 자른 것, CropBox 가 없으면 MediaBox, 그것도 없으면 LETTER(612×792)"""
    media = _rectangle(*_inherited(doc, page.xref, 'MediaBox')) or [0.0, 0.0, 612.0, 792.0]
    crop = _rectangle(*_inherited(doc, page.xref, 'CropBox'))
    if crop is None:
        return media
    return [max(media[0], crop[0]), max(media[1], crop[1]), min(media[2], crop[2]), min(media[3], crop[3])]


def _page_rotation(doc, page):
    """PDPage.getRotation — 상속되는 /Rotate 의 intValue 가 90 의 배수면 0~270, 아니면 0"""
    kind, value = _inherited(doc, page.xref, 'Rotate')
    try:
        angle = int(float(value)) if kind in ('int', 'float') else 0
    except ValueError:
        angle = 0
    return (angle % 360 + 360) % 360 if angle % 90 == 0 else 0


def page_content(doc, page):
    """콘텐츠 스트림들을 이어 붙인다 — 사이에 줄바꿈(앱과 같다)"""
    return b'\n'.join(doc.xref_stream(xref) or b'' for xref in page.get_contents()) + b'\n'


# --------------------------------------------------------------------------------------------- StaffSystemDetector
# Float 연산은 Kotlin 과 같게 한 번마다 f32 — 비교의 경계(± 허용치, 반올림)에서 앱과 같은 판정을 내려고.

STAFF_LINE_MAX_HEIGHT = f32(1.5)
STAFF_LINE_MIN_WIDTH = f32(80.0)
VERTICAL_MAX_WIDTH = f32(2.0)
VERTICAL_MIN_HEIGHT = f32(6.0)
LINE_CLUSTER_TOL = f32(2.0)
STAFF_MAX_SPAN = f32(28.0)
SYSTEM_GAP = f32(55.0)
BAR_END_TOL = f32(1.5)
NOTEHEAD_TOL = f32(4.5)
BAR_CLUSTER_TOL = f32(3.0)
MIN_MEASURE_WIDTH = f32(15.0)
LEFT_EDGE_TOL = f32(4.0)
SEGMENT_Y_TOL = f32(0.3)
SEGMENT_GAP_TOL = f32(1.0)
SMUFL_NOTEHEADS = range(0xE0A0, 0xE100)
SMUFL_HEAD_CENTER = f32(0.15)


def cluster(values, tol):
    """정렬 후 인접 간격이 tol 이하인 값끼리 묶어 평균 (Kotlin: Iterable<Float>.average() 는 double 합 → toFloat)"""
    if not values:
        return []
    ordered = sorted(values)
    out, group = [], [ordered[0]]
    for v in ordered[1:]:
        if f32(v - group[-1]) <= tol:
            group.append(v)
        else:
            out.append(f32(sum(group) / len(group)))
            group = [v]
    out.append(f32(sum(group) / len(group)))
    return out


def _merge_segments(segments):
    """(cy, x0, x1) — 같은 높이(±SEGMENT_Y_TOL)에서 끝이 이어진(SEGMENT_GAP_TOL 이하) 가로 조각을 하나로"""
    if not segments:
        return []
    out = []
    ordered = sorted(segments, key=lambda s: (s[0], s[1]))
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and f32(ordered[j + 1][0] - ordered[i][0]) <= SEGMENT_Y_TOL:
            j += 1
        row = sorted(ordered[i:j + 1], key=lambda s: s[1])
        cur = row[0]
        for seg in row[1:]:
            if f32(seg[1] - cur[2]) <= SEGMENT_GAP_TOL:
                cur = (f32(f32(cur[0] + seg[0]) / 2), cur[1], max(cur[2], seg[2]))
            else:
                out.append(cur)
                cur = seg
        out.append(cur)
        i = j + 1
    return out


def detect_systems(boxes, page_height, texts=()):
    horizontals, verticals, heads = [], [], []
    for b in boxes:
        w, h = f32(b.x1 - b.x0), f32(b.y1 - b.y0)
        if b.curved:
            if 4 < w < 9 and 3 < h < 7:
                heads.append((f32(f32(b.x0 + b.x1) / 2), f32(f32(b.y0 + b.y1) / 2)))
            continue
        if h < STAFF_LINE_MAX_HEIGHT and w > 0:
            horizontals.append((f32(f32(b.y0 + b.y1) / 2), b.x0, b.x1))
        elif w < VERTICAL_MAX_WIDTH and h > VERTICAL_MIN_HEIGHT:
            verticals.append((f32(f32(b.x0 + b.x1) / 2), b.y0, b.y1))
    for t in texts:
        if kt_length(t.text) == 1 and ord(t.text) in SMUFL_NOTEHEADS:
            heads.append((f32(t.x + f32(t.size * SMUFL_HEAD_CENTER)), t.y))
    staff_lines = [s for s in _merge_segments(horizontals) if f32(s[2] - s[1]) > STAFF_LINE_MIN_WIDTH]
    if not staff_lines:
        return []
    centers = cluster([s[0] for s in staff_lines], LINE_CLUSTER_TOL)
    staves = []
    i = 0
    while i + 5 <= len(centers):
        g = centers[i:i + 5]
        if f32(g[4] - g[0]) < STAFF_MAX_SPAN:
            staves.append((g[0], g[4]))
            i += 5
        else:
            i += 1
    if not staves:
        return []
    staves.sort()

    def connected(lower, upper):
        # 보표 사이를 잇는 세로선 — 위 보표(높은 y)의 아랫선부터 아래 보표의 윗선까지 덮는다
        return any(v[1] <= f32(lower[1] + BAR_END_TOL) and v[2] >= f32(upper[0] - BAR_END_TOL) for v in verticals)
    pairs = list(zip(staves, staves[1:]))
    use_connectors = any(connected(lo, up) for lo, up in pairs)
    groups, current = [], [staves[0]]
    for lower, upper in pairs:
        same = connected(lower, upper) if use_connectors else f32(upper[0] - lower[1]) <= SYSTEM_GAP
        if same:
            current.append(upper)
        else:
            groups.append(current)
            current = [upper]
    groups.append(current)
    groups.sort(key=lambda g: -g[0][0])                          # 페이지 위(큰 y)부터, 안정 정렬

    def has_head_at(x, y):
        return any(abs(f32(hx - x)) < NOTEHEAD_TOL and abs(f32(hy - y)) < NOTEHEAD_TOL for hx, hy in heads)
    return [_build_system(g, staff_lines, verticals, page_height, has_head_at) for g in groups]


def _build_system(system, staff_lines, verticals, page_height, has_head_at):
    top_pdf, bottom_pdf = system[-1][1], system[0][0]
    system_lines = [ln for ln in staff_lines
                    if any(abs(f32(ln[0] - st)) < 2 or abs(f32(ln[0] - sb)) < 2 for st, sb in system)]
    x_left = min(ln[1] for ln in system_lines)
    x_right = max(ln[2] for ln in system_lines)
    tops = [s[1] for s in system]
    bottoms = [s[0] for s in system]

    def near(v, targets):
        return any(abs(f32(v - t)) <= BAR_END_TOL for t in targets)
    candidates = [v for v in verticals if near(v[2], tops) and (near(v[1], bottoms) or near(v[1], tops))]
    per_staff = []
    for st, sb in system:
        xs = [v[0] for v in candidates if v[1] <= f32(st + BAR_END_TOL) and v[2] >= f32(sb - BAR_END_TOL)
              and not (has_head_at(v[0], st) or has_head_at(v[0], sb))]
        per_staff.append(sorted(xs))

    def staff_count(x):
        return sum(1 for xs in per_staff if any(abs(f32(v - x)) <= BAR_CLUSTER_TOL for v in xs))
    bars = []
    all_x = [x for xs in per_staff for x in xs]
    if all_x:
        # 보표 3개 이하면 전부, 그보다 많으면 하나 빠져도 된다
        needed = len(system) if len(system) <= 3 else len(system) - 1
        for cx in cluster(all_x, BAR_CLUSTER_TOL):
            if staff_count(cx) >= needed:
                bars.append(round1(cx))
    if bars:
        merged = [bars[0]]
        for b in bars[1:]:
            if f32(b - merged[-1]) < MIN_MEASURE_WIDTH:
                if staff_count(b) > staff_count(merged[-1]):
                    merged[-1] = b
            else:
                merged.append(b)
        bars = merged
    # 끝 마디선이 안 잡혔으면 오선 오른쪽 끝을 경계로 — 남은 폭이 마디 하나가 될 만큼일 때만
    if bars and f32(x_right - bars[-1]) >= MIN_MEASURE_WIDTH:
        bars.append(round1(x_right))
    left_edge = f32(x_left + LEFT_EDGE_TOL)
    bounds = [round1(x_left)] + [b for b in bars if b > left_edge]
    return SystemLayout(
        top=round1(f32(page_height - top_pdf)), bottom=round1(f32(page_height - bottom_pdf)),
        left=round1(x_left), right=round1(x_right),
        staff_bands=[(round1(f32(page_height - sb)), round1(f32(page_height - st))) for st, sb in reversed(system)],
        barlines=bounds)


# --------------------------------------------------------------------------------------------- StaffLabelDetector

LABEL_LEFT_TOL = f32(1.0)
GLYPH_WIDTH = f32(0.55)
WORD_GAP = f32(0.25)
DIGITS_ONLY = re.compile(r'[\d\s]+', re.ASCII)       # Java 정규식의 \d \s 는 ASCII 만
WHITESPACE_RUN = re.compile(r'\s+', re.ASCII)


def attach_labels(runs, systems, page_height):
    return [replace(s, staff_labels=_labels(runs, s, page_height)) for s in systems]


def _labels(runs, system, page_height):
    bands = system.staff_bands
    if not bands:
        return []
    pieces = [[] for _ in bands]
    for run in runs:
        text = kt_trim(run.text)
        if not text or run.x >= f32(system.left - LABEL_LEFT_TOL):
            continue
        y = f32(page_height - run.y)                   # 기준선, 위→아래
        center = f32(y - f32(run.size / 3))            # 글자 가운데는 글꼴 크기의 1/3 위
        best, best_distance = -1, 3.4028234663852886e38   # Float.MAX_VALUE
        for k, (top, bottom) in enumerate(bands):
            height = f32(bottom - top)
            if center < f32(top - height) or center > f32(bottom + height):
                continue
            distance = abs(f32(center - f32(f32(top + bottom) / 2)))
            if distance < best_distance:
                best, best_distance = k, distance
        if best >= 0:
            pieces[best].append((y, run))
    return [_join(p) for p in pieces]


def _join(items):
    lines, line_y = [], float('nan')
    for y, run in sorted(items, key=lambda item: item[0]):
        if not lines or f32(y - line_y) > f32(run.size / 2):
            lines.append([])
            line_y = y
        lines[-1].append(run)
    texts = []
    for line in lines:
        ordered = sorted(line, key=lambda r: r.x)
        out = ''
        for i, run in enumerate(ordered):
            text = kt_trim(run.text)
            if i > 0:
                prev = ordered[i - 1]
                prev_text = kt_trim(prev.text)
                if kt_length(prev_text) == 1 and kt_length(text) == 1:
                    spaced = f32(run.x - f32(prev.x + f32(prev.size * GLYPH_WIDTH))) > f32(prev.size * WORD_GAP)
                else:
                    spaced = True
                if spaced:
                    out += ' '
            out += text
        texts.append(out)
    joined = kt_trim(WHITESPACE_RUN.sub(' ', ' '.join(t for t in texts if not DIGITS_ONLY.fullmatch(t))))
    return joined or None


# --------------------------------------------------------------------------------------------- TimeSignatureDetector

TS_X_TOL = f32(3.0)
MIN_SEPARATION = f32(0.25)
MAX_SEPARATION = f32(0.8)
DENOMINATORS = {1, 2, 4, 8, 16, 32}
DIGITS = re.compile(r'\d{1,2}', re.ASCII)
SMUFL_DIGIT_0 = 0xE080
MERGE_GAP = f32(0.6)
BASELINE_TOL = f32(0.5)
SYMBOLS = {'c': (4, 4), 'C': (2, 2), '': (4, 4), '': (2, 2)}
SYMBOL_MIN_SIZE = f32(0.6)


def _normalize(text):
    """SMuFL 박자 숫자를 일반 숫자로. 다른 글자는 그대로"""
    return ''.join(chr(ord('0') + ord(c) - SMUFL_DIGIT_0) if SMUFL_DIGIT_0 <= ord(c) <= SMUFL_DIGIT_0 + 9 else c
                   for c in text)


def _is_single_digit(text):
    """Kotlin text.length == 1 && text[0].isDigit() — isDigit 는 유니코드 Nd (= str.isdecimal)"""
    return kt_length(text) == 1 and text.isdecimal()


def _merge_digits(runs):
    singles = sorted([r for r in runs if _is_single_digit(r.text)], key=lambda r: (r.y, r.x))
    others = [r for r in runs if not _is_single_digit(r.text)]
    merged, group = [], []

    def flush():
        nonlocal group
        if group:
            merged.append(group[0] if len(group) == 1 else
                          TextRun(''.join(r.text for r in group), f32(f32(group[0].x + group[-1].x) / 2),
                                  group[0].y, group[0].size))
        group = []
    for r in singles:
        last = group[-1] if group else None
        if last is not None and (abs(f32(r.y - last.y)) > BASELINE_TOL or f32(r.x - last.x) > f32(r.size * MERGE_GAP)):
            flush()
        group.append(r)
    flush()
    return others + merged


def detect_time_signatures(runs, systems, page_height):
    # Kotlin: text.any { c.code >= 0xE080 } — UTF-16 코드 단위라 BMP 밖 글자(서로게이트)는 해당하지 않는다
    normalized = _merge_digits([replace(r, text=_normalize(r.text))
                                if any(SMUFL_DIGIT_0 <= ord(c) <= 0xFFFF for c in r.text) else r for r in runs])
    digits = []
    for run in normalized:
        t = kt_trim(run.text)
        if DIGITS.fullmatch(t):
            digits.append((int(t), run.x, f32(page_height - run.y)))
    symbols = [(SYMBOLS[kt_trim(run.text)], run.x, f32(page_height - run.y), run.size)
               for run in runs if kt_trim(run.text) in SYMBOLS]
    if not digits and not symbols:
        return []
    marks = []
    for system_index, system in enumerate(systems):
        per_staff = [_candidates_in_staff(digits, top, bottom, system) + _symbols_in_staff(symbols, top, bottom, system)
                     for top, bottom in system.staff_bands]
        needed = max(1, (len(system.staff_bands) + 1) // 2)
        accepted = []
        for candidate in sorted((c for lst in per_staff for c in lst), key=lambda c: c[0]):
            if any(abs(f32(a[0] - candidate[0])) <= TS_X_TOL for a in accepted):
                continue
            staves = sum(1 for lst in per_staff
                         if any(abs(f32(c[0] - candidate[0])) <= TS_X_TOL and c[1] == candidate[1] and c[2] == candidate[2]
                                for c in lst))
            if staves >= needed:
                accepted.append(candidate)
        marks += [TimeSignatureMark(system_index, a[0], a[1], a[2]) for a in accepted]
    return marks


def _in_system_x(x, system):
    return f32(system.left - TS_X_TOL) <= x <= f32(system.right + TS_X_TOL)


def _symbols_in_staff(symbols, top, bottom, system):
    height = f32(bottom - top)
    if height <= 0:
        return []
    half = f32(height / 2)
    return [(x, n, d) for (n, d), x, y, size in symbols
            if size >= f32(height * SYMBOL_MIN_SIZE) and f32(top - half) <= y <= f32(bottom + half)
            and _in_system_x(x, system)]


def _candidates_in_staff(digits, top, bottom, system):
    height = f32(bottom - top)
    if height <= 0:
        return []
    near = [d for d in digits if f32(top - height) <= d[2] <= f32(bottom + height) and _in_system_x(d[1], system)]
    low, high = f32(height * MIN_SEPARATION), f32(height * MAX_SEPARATION)
    out = []
    for ui, upper in enumerate(near):
        for li, lower in enumerate(near):
            if ui == li:
                continue
            separation = f32(lower[2] - upper[2])
            if abs(f32(upper[1] - lower[1])) <= TS_X_TOL and low <= separation <= high \
                    and 1 <= upper[0] <= 32 and lower[0] in DENOMINATORS:
                out.append((f32(f32(upper[1] + lower[1]) / 2), upper[0], lower[0]))
    return out


# --------------------------------------------------------------------------------------------- ScoreLayoutAnalyzer · ScoreLayout

def analyze(source):
    """PDF(bytes 또는 경로) → [PageLayout]. 회전된 쪽은 빈 쪽으로(앱과 같다)"""
    doc = fitz.open(stream=source, filetype='pdf') if isinstance(source, (bytes, bytearray)) else fitz.open(source)
    pages = []
    with doc:
        for index, page in enumerate(doc):
            llx, lly, urx, ury = _page_box(doc, page)
            width, height = f32(urx - llx), f32(ury - lly)
            if _page_rotation(doc, page) % 360 != 0:
                pages.append(PageLayout(index, width, height, []))
                continue
            interpreter = ContentInterpreter(llx, lly).run(page_content(doc, page), Resources.for_page(doc, page))
            systems = attach_labels(interpreter.texts, detect_systems(interpreter.boxes, height, interpreter.texts), height)
            pages.append(PageLayout(index, width, height, systems,
                                    detect_time_signatures(interpreter.texts, systems, height)))
    return pages


def to_measures(pages):
    """앱 ScoreLayout.toMeasures — 문서 전체에서 1부터 이어지는 마디, 박자표는 놓인 마디부터 다음 박자표 전까지"""
    measures, numerator, denominator = [], None, None
    for page in pages:
        for system_index, system in enumerate(page.systems):
            marks = sorted([m for m in page.time_signatures if m.system_index == system_index], key=lambda m: m.x)
            next_mark = 0
            for k in range(system.measure_count):
                right = system.barlines[k + 1]
                while next_mark < len(marks) and marks[next_mark].x < right:
                    numerator, denominator = marks[next_mark].numerator, marks[next_mark].denominator
                    next_mark += 1
                measures.append({
                    'measureNumber': len(measures) + 1, 'pageIndex': page.page_index, 'systemIndex': system_index,
                    'leftPt': system.barlines[k], 'topPt': system.top, 'rightPt': right, 'bottomPt': system.bottom,
                    'pageWidthPt': page.width_pt, 'pageHeightPt': page.height_pt,
                    'timeSigNumerator': numerator, 'timeSigDenominator': denominator})
    return measures


def to_staves(pages):
    return [{'pageIndex': page.page_index, 'systemIndex': system_index, 'staffIndex': staff_index,
             'topPt': top, 'bottomPt': bottom,
             'label': system.staff_labels[staff_index] if staff_index < len(system.staff_labels) else None}
            for page in pages for system_index, system in enumerate(page.systems)
            for staff_index, (top, bottom) in enumerate(system.staff_bands)]


def to_document(pages, sha256=''):
    """저장할 JSON — 쪽별 원자료 + 앱 DB 행(measures = ScoreMeasure, staves = ScoreStaff, pdfFileId 는 앱이 붙인다)"""
    num = kt_json_float          # 앱의 Float 값 그대로 (그 Float 로 되돌아오는 가장 짧은 십진수)
    measures = [{k: num(v) for k, v in m.items()} for m in to_measures(pages)]
    return {
        'format': FORMAT, 'format_version': FORMAT_VERSION, 'source': SOURCE, 'pdf_sha256': sha256,
        'page_count': len(pages), 'measure_count': len(measures),
        'system_count': sum(len(p.systems) for p in pages),
        'pages': [{
            'pageIndex': p.page_index, 'widthPt': num(p.width_pt), 'heightPt': num(p.height_pt),
            'systems': [{'top': num(s.top), 'bottom': num(s.bottom), 'left': num(s.left), 'right': num(s.right),
                         'staffBands': [[num(t), num(b)] for t, b in s.staff_bands],
                         'barlines': [num(x) for x in s.barlines],
                         'staffLabels': s.staff_labels} for s in p.systems],
            'timeSignatures': [{'systemIndex': m.system_index, 'x': num(m.x), 'numerator': m.numerator,
                                'denominator': m.denominator} for m in p.time_signatures],
        } for p in pages],
        'measures': measures,
        'staves': [{k: num(v) for k, v in s.items()} for s in to_staves(pages)],
    }
