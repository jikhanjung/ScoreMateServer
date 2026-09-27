"""
웹에서 앙상블을 숨긴 상태(WEB_ENSEMBLES=False, 운영 기본값) — 메뉴 · 선택 · 표시가 없고, API 와 직접 주소는 그대로
"""
import shutil
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from ensembles.models import Membership
from scores.models import Score
from setlists.models import Setlist
from .factories import EnsembleFactory, MembershipFactory, ScoreFactory, UserFactory

PDF = (Path(__file__).parent / 'LaGazzaLadra.pdf').read_bytes()


class EnsemblesHiddenTest(TestCase):

    def setUp(self):
        self.files_root = Path(tempfile.mkdtemp(prefix='scoremate-hidden-'))
        self.addCleanup(shutil.rmtree, self.files_root, ignore_errors=True)
        # conftest 가 테스트마다 WEB_ENSEMBLES=True 로 켜므로 여기서(그 뒤에) 끈다
        overrides = override_settings(STORAGE_BACKEND='local', FILES_ROOT=self.files_root, FILES_X_ACCEL_PREFIX='',
                                      WEB_ENSEMBLES=False)
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.user = UserFactory(total_quota_mb=500)
        self.ensemble = EnsembleFactory(name='Hidden Ensemble')
        MembershipFactory(ensemble=self.ensemble, user=self.user, role=Membership.ROLE_OWNER)
        self.mine = ScoreFactory(user=self.user, title='Mine')
        self.client.force_login(self.user)

    def test_no_ensemble_ui_on_main_pages(self):
        pages = [reverse('web:scores'), reverse('web:score_upload'), reverse('web:setlists'), reverse('web:devices'),
                 reverse('web:account'), reverse('web:score_detail', args=[self.mine.pk]), reverse('web:activate')]
        for url in pages:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, '앙상블', msg_prefix=url)
            self.assertNotContains(response, reverse('web:ensembles'), msg_prefix=url)
            self.assertNotContains(response, 'name="ensemble"', msg_prefix=url)
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('web:login')), '앙상블')

    def test_upload_and_setlist_are_personal_even_if_ensemble_posted(self):
        self.client.post(reverse('web:score_upload'), {
            'files': SimpleUploadedFile('a.pdf', PDF, content_type='application/pdf'), 'title': 'Solo',
            'ensemble': self.ensemble.pk})
        self.assertIsNone(Score.objects.get(title='Solo').ensemble)
        self.client.post(reverse('web:setlists'), {'title': '연습', 'ensemble': self.ensemble.pk})
        self.assertIsNone(Setlist.objects.get(title='연습').ensemble)

    def test_api_and_direct_pages_still_work(self):
        self.assertEqual(self.client.get(reverse('web:ensemble_detail', args=[self.ensemble.pk])).status_code, 200)
        api = APIClient()
        api.force_authenticate(user=self.user)
        self.assertEqual([e['name'] for e in api.get('/api/v1/ensembles/').data], ['Hidden Ensemble'])
