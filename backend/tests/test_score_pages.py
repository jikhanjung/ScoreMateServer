"""
쪽 보기 — 상세 화면의 쪽 이미지(scores/pages.py): 처음 볼 때 그려 캐시, 서명 URL 로 보내기, 판 · 악보를 지우면 캐시도
"""
from unittest.mock import patch

from django.test import Client
from django.urls import reverse

from scores import pages
from scores.models import Score
from scores.services import delete_score, delete_version
from .test_web import PDF, WebTestBase, pdf_file


class ScorePagesTest(WebTestBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.post(reverse('web:score_upload'), {'files': [pdf_file('Gazza.pdf')], 'title': 'Gazza'})
        self.score = Score.objects.get(user=self.owner)
        self.version = self.score.current_version

    def page(self, number, size='thumb', client=None):
        return (client or self.client).get(reverse('web:score_page', args=[self.score.pk, number]), {'size': size})

    def test_detail_lists_every_page(self):
        response = self.client.get(reverse('web:score_detail', args=[self.score.pk]))
        self.assertGreater(self.score.pages, 1)
        self.assertContains(response, f'쪽 ({self.score.pages})')
        self.assertContains(response, 'class="page-thumb"', count=self.score.pages)
        self.assertContains(response, reverse('web:score_page', args=[self.score.pk, self.score.pages]))
        self.assertContains(response, 'data-fit="width"')    # 너비 맞춤 · 높이 맞춤
        self.assertContains(response, 'data-fit="height"')

    def test_page_is_rendered_once_and_redirected(self):
        with patch('scores.pages.render', wraps=pages.render) as render:
            first = self.page(2)
            second = self.page(2)
        self.assertEqual(render.call_count, 1)                    # 두 번째는 캐시
        self.assertEqual((first.status_code, second.status_code), (302, 302))
        self.assertIn('/api/v1/files/blob/', first['Location'])
        self.assertIn('max-age', first['Cache-Control'])
        key = pages.page_key(self.score, self.version, 2, 'thumb')
        self.assertEqual((self.files_root / key).read_bytes()[:2], b'\xff\xd8')   # JPEG
        blob = Client().get(first['Location'])
        self.assertEqual(b''.join(blob.streaming_content)[:2], b'\xff\xd8')

    def test_view_size_is_bigger(self):
        self.page(1, 'thumb')
        self.page(1, 'view')
        thumb = (self.files_root / pages.page_key(self.score, self.version, 1, 'thumb')).stat().st_size
        view = (self.files_root / pages.page_key(self.score, self.version, 1, 'view')).stat().st_size
        self.assertGreater(view, thumb)

    def test_bad_requests(self):
        self.assertEqual(self.page(self.score.pages + 1).status_code, 404)
        self.assertEqual(self.page(1, 'huge').status_code, 404)
        self.assertEqual(self.page(1, client=self.as_other(self.outsider)).status_code, 404)

    def as_other(self, user):
        client = Client()
        client.force_login(user)
        return client

    def test_new_version_gets_new_images_and_deleting_cleans_up(self):
        self.page(1)
        old_dir = (self.files_root / pages.page_key(self.score, self.version, 1, 'thumb')).parent
        other = PDF.replace(b'%%EOF', b'%%EOF\n% v2', 1) if b'%%EOF' in PDF else PDF + b'\n% v2'
        self.client.post(reverse('web:version_upload', args=[self.score.pk]),
                         {'file': pdf_file('Gazza v2.pdf', other), 'note': 'v2'})
        self.score.refresh_from_db()
        v2 = self.score.current_version
        self.assertNotEqual(v2.content_hash, self.version.content_hash)
        self.page(1)
        new_dir = (self.files_root / pages.page_key(self.score, v2, 1, 'thumb')).parent
        self.assertNotEqual(old_dir, new_dir)
        self.assertTrue(old_dir.is_dir() and new_dir.is_dir())

        delete_version(self.score, self.score.versions.get(number=1))
        self.assertFalse(old_dir.exists())
        self.assertTrue(new_dir.exists())
        self.score.refresh_from_db()
        pages_root = new_dir.parent
        delete_score(self.score)
        self.assertFalse(pages_root.exists())
