"""
local 저장소 (STORAGE_BACKEND=local) — 서버 디스크 + 서명 토큰 URL, 받기는 nginx X-Accel-Redirect

운영(dolfinid) 경로 그대로: upload-url → PUT blob → upload-confirm → (요청 안에서) 페이지 수 · 썸네일 → 받기
"""
import hashlib
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from files.utils import LocalStorageHandler, get_storage, load_blob_token, sign_blob_token
from scores.models import Score
from .factories import UserFactory, ScoreFactory, EnsembleFactory, MembershipFactory

TEST_PDF = Path(__file__).parent / 'LaGazzaLadra.pdf'


class LocalStorageTestBase(APITestCase):

    def setUp(self):
        self.files_root = Path(tempfile.mkdtemp(prefix='scoremate-files-'))
        self.addCleanup(shutil.rmtree, self.files_root, ignore_errors=True)
        overrides = override_settings(STORAGE_BACKEND='local', FILES_ROOT=self.files_root,
                                      FILES_X_ACCEL_PREFIX='', FILES_PUBLIC_BASE='')
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.user = UserFactory(total_quota_mb=500)
        self.client.force_authenticate(user=self.user)

    def blob_path(self, url):
        """응답의 URL 에서 테스트 클라이언트에 넣을 경로"""
        self.assertTrue(url.startswith('/api/v1/files/blob/'), url)
        return url

    def upload(self, data, filename='score.pdf', size=None):
        response = self.client.post('/api/v1/files/upload-url/', {
            'filename': filename, 'size_bytes': size or len(data), 'mime_type': 'application/pdf'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        put = self.client.generic('PUT', self.blob_path(response.data['upload_url']), data,
                                  content_type='application/pdf')
        return response.data, put


class LocalStorageHandlerTest(LocalStorageTestBase):

    def test_get_storage_follows_setting(self):
        self.assertIsInstance(get_storage(), LocalStorageHandler)

    def test_rejects_keys_outside_root(self):
        storage = LocalStorageHandler()
        for key in ('../etc/passwd', '1/../../x', '', '/abs/path'):
            with self.assertRaises(ValueError, msg=key):
                storage.path_for(key)

    def test_write_read_delete(self):
        storage = LocalStorageHandler()
        storage.write_bytes('1/scores/9/thumbs/cover.jpg', b'jpeg')
        self.assertTrue(storage.check_file_exists('1/scores/9/thumbs/cover.jpg'))
        self.assertEqual(storage.read_bytes('1/scores/9/thumbs/cover.jpg'), b'jpeg')
        storage.delete_file('1/scores/9/thumbs/cover.jpg')
        self.assertFalse(storage.check_file_exists('1/scores/9/thumbs/cover.jpg'))
        # 비게 된 디렉터리도 지워진다 — 저장소 루트는 남는다
        self.assertFalse((self.files_root / '1').exists())
        self.assertTrue(self.files_root.is_dir())

    def test_delete_keeps_non_empty_dirs(self):
        storage = LocalStorageHandler()
        storage.write_bytes('1/scores/9/original.pdf', b'pdf')
        storage.write_bytes('1/scores/9/thumbs/cover.jpg', b'jpeg')
        storage.delete_file('1/scores/9/thumbs/cover.jpg')
        self.assertFalse((self.files_root / '1/scores/9/thumbs').exists())
        self.assertTrue((self.files_root / '1/scores/9/original.pdf').is_file())

    def test_write_stream_limit_leaves_nothing(self):
        storage = LocalStorageHandler()
        with self.assertRaises(ValueError):
            storage.write_stream('1/uploads/a/original.pdf', [b'x' * 10, b'x' * 10], max_bytes=15)
        self.assertEqual(list((self.files_root / '1/uploads/a').iterdir()), [])

    def test_token_expiry_and_tamper(self):
        token = sign_blob_token({'op': 'get', 'k': '1/a.pdf'}, 300)
        self.assertEqual(load_blob_token(token)['k'], '1/a.pdf')
        self.assertIsNone(load_blob_token(token[:-2] + 'xx'))
        with patch('files.utils.time.time', return_value=time.time() + 3 * 3600):
            self.assertIsNone(load_blob_token(token))

    def test_urls_are_stable_within_a_window(self):
        storage = LocalStorageHandler()
        a = storage.generate_presigned_download_url('1/a.jpg', expiry=6 * 3600)['url']
        b = storage.generate_presigned_download_url('1/a.jpg', expiry=6 * 3600)['url']
        self.assertEqual(a, b)  # 목록을 다시 불러와도 썸네일이 브라우저 캐시에서 나온다


class LocalUploadFlowTest(LocalStorageTestBase):

    def test_full_upload_process_download(self):
        pdf = TEST_PDF.read_bytes()
        upload, put = self.upload(pdf, filename='La Gazza Ladra.pdf')
        self.assertEqual(put.status_code, status.HTTP_201_CREATED)
        self.assertEqual(put.json()['size_bytes'], len(pdf))

        confirm = self.client.post('/api/v1/files/upload-confirm/', {
            'upload_id': upload['upload_id'], 'title': 'La Gazza Ladra'})
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)

        # REDIS_URL 이 없으니 페이지 수 · 썸네일 · 해시가 요청 안에서 만들어졌다
        score = Score.objects.get(id=confirm.data['score_id'])
        self.assertGreater(score.pages or 0, 0)
        self.assertEqual(score.content_hash, hashlib.sha256(pdf).hexdigest())
        self.assertTrue((self.files_root / score.thumbnail_key).is_file())

        # 목록의 썸네일은 서명 URL — 받을 수 있다
        listing = self.client.get('/api/v1/scores/')
        thumb_url = listing.data['results'][0]['thumbnail_url']
        thumb = self.client.get(self.blob_path(thumb_url))
        self.assertEqual(thumb.status_code, status.HTTP_200_OK)
        self.assertEqual(thumb['Content-Type'], 'image/jpeg')

        # 원본 받기 (개발 모드: X-Accel 없이 직접)
        download = self.client.get('/api/v1/files/download-url/', {'score_id': score.id, 'file_type': 'original'})
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        response = self.client.get(self.blob_path(download.data['download_url']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b''.join(response.streaming_content), pdf)
        self.assertIn("filename*=UTF-8''La%20Gazza%20Ladra.pdf", response['Content-Disposition'])

    def test_upload_link_is_single_use(self):
        upload, put = self.upload(b'%PDF-1.4 small')
        self.assertEqual(put.status_code, status.HTTP_201_CREATED)
        again = self.client.generic('PUT', upload['upload_url'], b'%PDF-1.4 other', content_type='application/pdf')
        self.assertEqual(again.status_code, status.HTTP_409_CONFLICT)

    def test_upload_too_large(self):
        with override_settings(MAX_UPLOAD_SIZE=10):
            response = self.client.post('/api/v1/files/upload-url/', {
                'filename': 'a.pdf', 'size_bytes': 5, 'mime_type': 'application/pdf'})
            put = self.client.generic('PUT', response.data['upload_url'], b'x' * 50, content_type='application/pdf')
        self.assertEqual(put.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertFalse(any(self.files_root.rglob('original.pdf')))

    def test_bad_tokens(self):
        self.assertEqual(self.client.get('/api/v1/files/blob/not-a-token/').status_code, status.HTTP_403_FORBIDDEN)
        # 받기 토큰으로 올릴 수 없다
        get_token = sign_blob_token({'op': 'get', 'k': f'{self.user.id}/uploads/x/original.pdf'}, 300)
        put = self.client.generic('PUT', f'/api/v1/files/blob/{get_token}/', b'x', content_type='application/pdf')
        self.assertEqual(put.status_code, status.HTTP_403_FORBIDDEN)
        # 없는 파일
        self.assertEqual(self.client.get(f'/api/v1/files/blob/{get_token}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_blob_endpoint_off_for_s3_backend(self):
        token = sign_blob_token({'op': 'get', 'k': '1/a.pdf'}, 300)
        with override_settings(STORAGE_BACKEND='s3'):
            self.assertEqual(self.client.get(f'/api/v1/files/blob/{token}/').status_code, status.HTTP_404_NOT_FOUND)


class XAccelTest(LocalStorageTestBase):

    def test_download_is_handed_to_nginx(self):
        storage = LocalStorageHandler()
        storage.write_bytes(f'{self.user.id}/scores/1/original.pdf', b'%PDF')
        url = storage.generate_presigned_download_url(f'{self.user.id}/scores/1/original.pdf', filename='곡.pdf')['url']
        with override_settings(FILES_X_ACCEL_PREFIX='/_protected/'):
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['X-Accel-Redirect'], f'/_protected/{self.user.id}/scores/1/original.pdf')
        self.assertEqual(response.content, b'')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn("filename*=UTF-8''%EA%B3%A1.pdf", response['Content-Disposition'])


class DirectDownloadTest(LocalStorageTestBase):

    def test_redirects_to_signed_url_for_members_only(self):
        ensemble = EnsembleFactory()
        MembershipFactory(ensemble=ensemble, user=self.user)
        score = ScoreFactory(ensemble=ensemble, s3_key='9/scores/1/original.pdf')
        response = self.client.get(f'/api/v1/files/direct-download/{score.id}/')
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(response['Location'].startswith('/api/v1/files/blob/'))

        self.client.force_authenticate(user=UserFactory())
        self.assertEqual(self.client.get(f'/api/v1/files/direct-download/{score.id}/').status_code,
                         status.HTTP_404_NOT_FOUND)
