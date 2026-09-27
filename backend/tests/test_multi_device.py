"""
한 계정 · 여러 기기 — TV 여러 대(거실 · 합주실)와 휴대폰 · PC 웹이 서로 간섭하지 않는다
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from devices import services as device_services
from devices.models import Device
from scores.models import ScoreVersion
from .factories import ScoreFactory, UserFactory

SHA = 'ab' * 32


@override_settings(SYNC_LAG_SECONDS=0)
class MultiDeviceTest(TestCase):

    def setUp(self):
        self.user = UserFactory(username='jikhan')
        self.score = ScoreFactory(user=self.user, title='Mine', content_hash=SHA)
        ScoreVersion.objects.filter(score=self.score).update(content_hash=SHA)

    def link(self, name):
        codes_client = APIClient()
        codes = codes_client.post('/api/v1/device/code', {'name': name}, format='json').data
        self.client.force_login(self.user)
        self.client.post(reverse('web:activate'), {'code': codes['user_code'], 'decision': 'approve'})
        tokens = codes_client.post('/api/v1/device/token', {'device_code': codes['device_code']}, format='json').data
        tv = APIClient()
        tv.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
        return tv, tokens

    def test_each_tv_is_its_own_device(self):
        living, living_tokens = self.link('거실 TV')
        studio, studio_tokens = self.link('합주실 TV')
        self.assertNotEqual(living_tokens['device_id'], studio_tokens['device_id'])
        self.assertEqual(Device.objects.filter(user=self.user).count(), 2)
        self.assertEqual(living.get('/api/v1/devices/me/').data['name'], '거실 TV')
        self.assertEqual(studio.get('/api/v1/devices/me/').data['name'], '합주실 TV')

        # 동기화는 기기마다 따로(커서는 TV 가 가진다) — 둘 다 전부를 받는다
        for tv in (living, studio):
            data = tv.get('/api/v1/sync/scores/').data
            self.assertEqual(data['ids'], [self.score.pk])
            self.assertEqual(len(data['scores']), 1)
        listing = APIClient()
        listing.force_authenticate(user=self.user)
        devices = {d['name']: d for d in listing.get('/api/v1/devices/').data}
        self.assertTrue(all(d['last_synced_at'] for d in devices.values()))

    def test_revoking_one_tv_leaves_the_others(self):
        living, living_tokens = self.link('거실 TV')
        studio, studio_tokens = self.link('합주실 TV')
        device_services.revoke(Device.objects.get(pk=living_tokens['device_id']))

        self.assertEqual(living.get('/api/v1/sync/scores/').status_code, 401)
        self.assertEqual(studio.get('/api/v1/sync/scores/').status_code, 200)
        refresh = APIClient().post('/api/v1/auth/token/refresh/', {'refresh': studio_tokens['refresh_token']}, format='json')
        self.assertEqual(refresh.status_code, 200)
        refresh = APIClient().post('/api/v1/auth/token/refresh/', {'refresh': living_tokens['refresh_token']}, format='json')
        self.assertEqual(refresh.status_code, 401)
        # 웹 로그인(휴대폰)도 그대로
        self.assertEqual(self.client.get(reverse('web:scores')).status_code, 200)

    def test_phone_and_pc_web_sessions_are_independent(self):
        phone, pc = self.client_class(), self.client_class()
        for client in (phone, pc):
            client.post(reverse('web:login'), {'email': self.user.email, 'password': 'testpass123'})
            self.assertEqual(client.get(reverse('web:scores')).status_code, 200)
        phone.post(reverse('web:logout'))
        self.assertEqual(phone.get(reverse('web:scores')).status_code, 302)
        self.assertEqual(pc.get(reverse('web:scores')).status_code, 200)

    def test_second_tv_of_same_user_sees_existing_analysis(self):
        """같은 계정의 두 번째 TV 가 같은 분석기로 또 올리면 409 not_newer — '이미 있음'으로 받아들이면 된다"""
        living, _ = self.link('거실 TV')
        studio, _ = self.link('합주실 TV')
        body = {'analyzer': 'mrgq-measures', 'analyzer_version': '12', 'sha256': SHA, 'data': {'m': 1}}
        self.assertEqual(living.put(f'/api/v1/scores/{self.score.pk}/analysis/', body, format='json').status_code, 201)
        # 본인 악보라 owner 권한(can_edit) — 같은 버전도 덮어쓸 수 있다
        self.assertEqual(studio.put(f'/api/v1/scores/{self.score.pk}/analysis/', body, format='json').status_code, 200)
        self.assertEqual(len(studio.get(f'/api/v1/scores/{self.score.pk}/analysis/').data['analyses']), 1)
