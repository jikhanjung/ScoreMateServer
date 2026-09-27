"""
PDF 문서 속성(제목 · 작성자 …)에서 악보 정보를 짐작한다 — 파일 이름보다 나은 제목을 주려고

Sibelius · MuseScore 는 PDF 제목에 "곡 제목 - Full Score" / "곡 제목 - Violin I" 처럼 파트를 붙인다(Moldau0607.pdf:
"Die Moldau (Vltava) - Full Score"). 작성자(Author)는 편곡자 · 조판한 사람일 때가 많아 작곡가로 채우지 않고 보여 주기만 한다.
제안일 뿐이다 — 사람이 올리기 · 고치기 화면에서 고른다.
"""
import re

import fitz  # PyMuPDF

# 프로그램이 넣는 뜻 없는 제목 — 이런 것은 제목으로 쓰지 않는다
GENERIC_TITLE = re.compile(r'^(untitled|제목 없음|microsoft word - .*|document\d*|score\d*|.*\.(pdf|mscz|sib|musx|docx?))$', re.I)
# 제목 끝의 " - 파트" — 총보나 악기 이름일 때만 파트로 떼어 낸다(부제목을 잘못 자르지 않게 좁게)
PART_WORDS = re.compile(
    r'(full score|score|conductor|총보|지휘자|part|parts|파트|piano|violin|viola|cello|violoncello|contrabass|double bass|'
    r'bass|guitar|flute|oboe|clarinet|bassoon|horn|trumpet|trombone|tuba|harp|timpani|percussion|soprano|alto|tenor|'
    r'baritone|voice|vocal|기타|바이올린|비올라|첼로|플루트|피아노)', re.I)


def read(source):
    """bytes 또는 파일 경로 → 문서 속성 dict(빈 값은 뺀다). 읽지 못하면 {}"""
    try:
        document = fitz.open(stream=source, filetype='pdf') if isinstance(source, (bytes, bytearray)) else fitz.open(source)
        with document:
            raw = document.metadata or {}
    except Exception:  # noqa: BLE001 — 깨진 PDF 여도 올리기는 막지 않는다
        return {}
    keep = ('title', 'author', 'subject', 'keywords', 'creator', 'producer')
    return {k: str(raw[k]).strip() for k in keep if raw.get(k) and str(raw[k]).strip()}


def suggest(meta):
    """문서 속성 → {'title', 'part_name'?, 'author'?} 제안. 쓸 만한 제목이 없으면 {}"""
    title = (meta.get('title') or '').strip()
    if not title or GENERIC_TITLE.match(title):
        return {}
    result = {}
    head, sep, tail = title.rpartition(' - ')
    if sep and head.strip() and PART_WORDS.search(tail) and len(tail) <= 40:
        result['title'], result['part_name'] = head.strip(), tail.strip()
    else:
        result['title'] = title
    if meta.get('author'):
        result['author'] = meta['author']
    return result
