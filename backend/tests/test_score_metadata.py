"""
곡 정보 — 편곡 칸, PDF 문서 속성에서 제목 · 파트 짐작(scores/pdfmeta.py), 고치기 화면의 제안(PDF · 악보 인식)
"""
import io
import json
from unittest.mock import patch

import fitz
from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse

from scores import pdfmeta
from scores.models import Score, ScoreVersion
from .factories import ScoreFactory
from .test_web import WebTestBase, pdf_file

SHA = 'ab' * 32


def pdf_with(**metadata):
    document = fitz.open()
    document.new_page()
    document.set_metadata(metadata)
    return document.tobytes()


class SuggestTest(SimpleTestCase):

    def test_title_and_part_split(self):
        self.assertEqual(pdfmeta.suggest({'title': 'Die Moldau (Vltava) - Full Score', 'author': '전예완'}),
                         {'title': 'Die Moldau (Vltava)', 'part_name': 'Full Score', 'author': '전예완'})
        self.assertEqual(pdfmeta.suggest({'title': 'Arpeggione Sonata - Violoncello'}),
                         {'title': 'Arpeggione Sonata', 'part_name': 'Violoncello'})

    def test_subtitle_is_not_a_part(self):
        self.assertEqual(pdfmeta.suggest({'title': 'Suite - Prelude and Fugue'}), {'title': 'Suite - Prelude and Fugue'})

    def test_generic_titles_are_ignored(self):
        for title in ('Untitled', 'Microsoft Word - notes.docx', 'moldau.pdf', 'Document1', ''):
            self.assertEqual(pdfmeta.suggest({'title': title}), {}, title)

    def test_read_bytes(self):
        meta = pdfmeta.read(pdf_with(title='Clair de Lune - Piano', author='Debussy'))
        self.assertEqual((meta['title'], meta['author']), ('Clair de Lune - Piano', 'Debussy'))
        self.assertEqual(pdfmeta.read(b'not a pdf'), {})


class MetadataWebTest(WebTestBase):

    def upload(self, data, name='SM-000234705_02052026.pdf', **fields):
        self.client.force_login(self.owner)
        return self.client.post(reverse('web:score_upload'), {'files': [pdf_file(name, data)], **fields})

    def test_upload_uses_pdf_title_instead_of_file_name(self):
        self.upload(pdf_with(title='Die Moldau (Vltava) - Full Score', author='전예완'))
        score = Score.objects.get(user=self.owner)
        self.assertEqual((score.title, score.part_name), ('Die Moldau (Vltava)', 'Full Score'))
        self.assertEqual(score.arranger, '')   # 작성자는 제안만 — 저절로 채우지 않는다

    def test_typed_title_wins_and_no_metadata_falls_back_to_file_name(self):
        self.upload(pdf_with(title='Die Moldau - Full Score'), title='블타바', composer='Smetana', arranger='전예완')
        self.upload(pdf_with(), name='Gazza.pdf')
        titles = {s.title: s for s in Score.objects.filter(user=self.owner)}
        self.assertEqual(set(titles), {'블타바', 'Gazza'})
        self.assertEqual((titles['블타바'].composer, titles['블타바'].arranger, titles['블타바'].part_name),
                         ('Smetana', '전예완', ''))

    def test_edit_page_suggests_pdf_and_omr_metadata(self):
        self.upload(pdf_with(title='Die Moldau (Vltava) - Full Score', author='전예완'), title='SM-000234705')
        score = Score.objects.get(user=self.owner)
        ScoreVersion.objects.filter(score=score).update(content_hash=SHA)
        Score.objects.filter(pk=score.pk).update(content_hash=SHA)
        bundle = {'version_id': score.current_version_id, 'sha256': SHA, 'status': 'failed', 'problems': ['x'],
                  'metadata': {'title': 'Die Moldau', 'composer': 'Bedřich Smetana', 'arranger': '전예완',
                               'instrumentation': 'Guitar ensemble', 'part_name': 'Full Score', 'parts': ['진호', '예진'],
                               'subtitle': '', 'lyricist': '', 'notes': ''}}
        with patch('sys.stdin', io.StringIO(json.dumps(bundle))):
            call_command('omr_ingest', stdout=io.StringIO())   # 인식이 실패해도 곡 정보는 남는다

        page = self.client.get(reverse('web:score_edit', args=[score.pk]))
        self.assertContains(page, 'PDF 문서 정보')
        self.assertContains(page, 'Die Moldau (Vltava)')
        self.assertContains(page, '악보 인식이 첫 쪽에서 읽은 것')
        self.assertContains(page, 'Bedřich Smetana')
        self.assertContains(page, 'data-value="arranger"')
        self.assertContains(page, 'id="id_arranger"')

        self.client.post(reverse('web:score_edit', args=[score.pk]),
                         {'title': 'Die Moldau', 'part_name': 'Full Score', 'composer': 'Bedřich Smetana',
                          'arranger': '전예완', 'instrumentation': 'Guitar ensemble', 'note': '', 'tags_text': ''})
        score.refresh_from_db()
        self.assertEqual((score.title, score.composer, score.arranger), ('Die Moldau', 'Bedřich Smetana', '전예완'))
        detail = self.client.get(reverse('web:score_detail', args=[score.pk]))
        self.assertContains(detail, '<dt>편곡</dt><dd>전예완</dd>', html=True)

    def test_no_suggestions_without_metadata(self):
        score = ScoreFactory(user=self.owner, s3_key='')
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('web:score_edit', args=[score.pk])), '찾은 정보')

    def test_arranger_in_api_and_search(self):
        score = ScoreFactory(user=self.owner, title='Moldau', arranger='전예완')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('web:scores'), {'q': '전예완'}), 'Moldau')
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(user=self.owner)
        self.assertEqual(api.get(f'/api/v1/scores/{score.pk}/').data['arranger'], '전예완')
