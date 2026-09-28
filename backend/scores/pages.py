"""
쪽 이미지 — 악보 상세에서 쪽마다 보기. 처음 볼 때 그 쪽만 그려 저장소에 두고(캐시), 받기는 서명 URL 로(파일은 Django 를 지나지 않는다)

키: {user}/scores/{score}/pages/{판 해시 앞 16자}/{크기}-{쪽:04d}.jpg — 판(파일)이 바뀌면 키가 바뀌어 옛 이미지를 쓰지 않는다.
판 · 악보를 지우면 pages/ 아래를 지운다(scores/services.py).
"""
import fitz  # PyMuPDF

from files.utils import get_storage

SIZES = {'thumb': 320, 'view': 1600}   # 가로 픽셀
JPEG_QUALITY = {'thumb': 70, 'view': 85}


class PageError(ValueError):
    pass


def pages_prefix(score):
    return f'{score.user_id}/scores/{score.pk}/pages'


def page_key(score, version, number, size):
    return f'{pages_prefix(score)}/{(version.content_hash or str(version.pk))[:16]}/{size}-{number:04d}.jpg'


def render(pdf_bytes, number, size):
    """PDF 한 쪽 → JPEG bytes (가로 SIZES[size] 픽셀)"""
    with fitz.open(stream=pdf_bytes, filetype='pdf') as document:
        if not 1 <= number <= len(document):
            raise PageError(f'No page {number}')
        page = document[number - 1]
        zoom = SIZES[size] / max(page.rect.width, 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pixmap.tobytes('jpg', jpg_quality=JPEG_QUALITY[size])


def page_image_key(score, version, number, size):
    """그 쪽 이미지의 저장소 키 — 없으면 지금 그려서 둔다"""
    if size not in SIZES:
        raise PageError(f'Unknown size {size}')
    if version.pages and not 1 <= number <= version.pages:
        raise PageError(f'No page {number}')
    storage = get_storage()
    key = page_key(score, version, number, size)
    if not storage.check_file_exists(key):
        storage.write_bytes(key, render(storage.read_bytes(version.s3_key), number, size), 'image/jpeg')
    return key
