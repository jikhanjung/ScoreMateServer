"""
S3 — TV 기기 연결 (RFC 8628 Device Authorization Grant), devlog 054 §3
"""
import re
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from devices.models import Device, DeviceAuthorization, hash_device_code
from .factories import ScoreFactory, UserFactory

CODE_RE = re.compile(r'^[BCDFGHJKMNPQRSTVWXZ2-9]{4}-[BCDFGHJKMNPQRSTVWXZ2-9]{4}$')


class DeviceFlowBase(TestCase):

    def setUp(self):
        self.user = UserFactory(username='jikhan')
        self.other = UserFactory(username='other')
        self.tv = APIClient()

    def request_code(self, **data):
        response = self.tv.post('/api/v1/device/code', data or {'name': '거실 TV', 'model': 'Chromecast with Google TV',
                                                             'app_version': 'MrgqPdfViewer 2.0'}, format='json')
        self.assertEqual(response.status_code, 200)
        return response.data

    def poll(self, device_code, **extra):
        return self.tv.post('/api/v1/device/token', {'device_code': device_code, **extra}, format='json')

    def allow_next_poll(self, device_code):
        """간격(interval)을 지킨 것처럼 — 마지막 폴링 시각을 과거로"""
        DeviceAuthorization.objects.filter(device_code_hash=hash_device_code(device_code)).update(
            last_polled_at=timezone.now() - timedelta(minutes=1))

    def approve_on_phone(self, user_code, user=None, name=None):
        self.client.force_login(user or self.user)
        data = {'code': user_code, 'decision': 'approve'}
        if name:
            data['name'] = name
        return self.client.post(reverse('web:activate'), data)

    def connect(self):
        """코드 → 휴대폰 승인 → 토큰"""
        codes = self.request_code()
        self.approve_on_phone(codes['user_code'])
        response = self.poll(codes['device_code'])
        self.assertEqual(response.status_code, 200, response.data)
        return response.data


class DeviceCodeTest(DeviceFlowBase):

    def test_code_response(self):
        data = self.request_code()
        self.assertRegex(data['user_code'], CODE_RE)
        self.assertEqual(data['verification_uri'], 'http://testserver/activate/')
        self.assertEqual(data['verification_uri_complete'], f"http://testserver/activate/?code={data['user_code']}")
        self.assertEqual((data['expires_in'], data['interval']), (600, 5))
        self.assertGreaterEqual(len(data['device_code']), 40)
        # device_code 원문은 DB 에 없다 — 해시만
        authorization = DeviceAuthorization.objects.get()
        self.assertEqual(authorization.device_code_hash, hash_device_code(data['device_code']))
        self.assertNotEqual(authorization.device_code_hash, data['device_code'])
        self.assertEqual((authorization.device_name, authorization.device_model), ('거실 TV', 'Chromecast with Google TV'))

    def test_code_without_body(self):
        response = self.tv.post('/api/v1/device/code', {}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_code_is_throttled(self):
        for _ in range(30):
            self.tv.post('/api/v1/device/code', {}, format='json')
        self.assertEqual(self.tv.post('/api/v1/device/code', {}, format='json').status_code, 429)


class DeviceTokenPollingTest(DeviceFlowBase):

    def test_pending_then_slow_down(self):
        codes = self.request_code()
        response = self.poll(codes['device_code'])
        self.assertEqual((response.status_code, response.data), (400, {'error': 'authorization_pending'}))
        # 간격보다 빨리 물으면 slow_down, 간격이 5초 는다
        response = self.poll(codes['device_code'])
        self.assertEqual(response.data, {'error': 'slow_down'})
        self.assertEqual(DeviceAuthorization.objects.get().interval, 10)
        self.allow_next_poll(codes['device_code'])
        self.assertEqual(self.poll(codes['device_code']).data, {'error': 'authorization_pending'})

    def test_unknown_code_and_grant_type(self):
        self.assertEqual(self.poll('nope').data, {'error': 'invalid_grant'})
        self.assertEqual(self.poll('').data, {'error': 'invalid_grant'})
        codes = self.request_code()
        response = self.poll(codes['device_code'], grant_type='password')
        self.assertEqual(response.data, {'error': 'unsupported_grant_type'})
        response = self.poll(codes['device_code'], grant_type='urn:ietf:params:oauth:grant-type:device_code')
        self.assertEqual(response.data, {'error': 'authorization_pending'})

    def test_form_encoded_request(self):
        """RFC 8628 의 토큰 요청은 application/x-www-form-urlencoded"""
        codes = self.request_code()
        response = self.tv.post('/api/v1/device/token', {'device_code': codes['device_code'],
                                                         'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'})
        self.assertEqual(response.data, {'error': 'authorization_pending'})

    def test_expired(self):
        codes = self.request_code()
        DeviceAuthorization.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.poll(codes['device_code']).data, {'error': 'expired_token'})
        self.client.force_login(self.user)
        response = self.client.get(reverse('web:activate'), {'code': codes['user_code']})
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, '만료된 코드', status_code=404)

    def test_approve_issues_tokens_once(self):
        codes = self.request_code()
        response = self.approve_on_phone(codes['user_code'].lower().replace('-', ''), name='합주실 TV')
        self.assertRedirects(response, reverse('web:devices'))
        device = Device.objects.get()
        self.assertEqual((device.user, device.name, device.model), (self.user, '합주실 TV', 'Chromecast with Google TV'))

        response = self.poll(codes['device_code'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual((response.data['token_type'], response.data['device_id']), ('Bearer', str(device.pk)))
        self.assertEqual(AccessToken(response.data['access_token'])['device_id'], str(device.pk))
        refresh = RefreshToken(response.data['refresh_token'])
        self.assertGreater(refresh['exp'] - refresh['iat'], 170 * 86400)   # 180일

        # 한 번만 — 다시 물으면 invalid_grant, 코드도 다시 못 쓴다
        self.allow_next_poll(codes['device_code'])
        self.assertEqual(self.poll(codes['device_code']).data, {'error': 'invalid_grant'})
        self.assertEqual(self.approve_on_phone(codes['user_code']).status_code, 404)
        self.assertEqual(Device.objects.count(), 1)

    def test_deny(self):
        codes = self.request_code()
        self.client.force_login(self.user)
        self.client.post(reverse('web:activate'), {'code': codes['user_code'], 'decision': 'deny'})
        self.assertEqual(self.poll(codes['device_code']).data, {'error': 'access_denied'})
        self.assertFalse(Device.objects.exists())


class ActivatePageTest(DeviceFlowBase):

    def test_login_required_keeps_code(self):
        url = f"{reverse('web:activate')}?code=BCDF-GHJK"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=/activate/%3Fcode%3DBCDF-GHJK', response['Location'])

    def test_confirm_page(self):
        codes = self.request_code()
        self.client.force_login(self.user)
        response = self.client.get(reverse('web:activate'), {'code': codes['user_code']})
        self.assertContains(response, codes['user_code'])
        self.assertContains(response, 'Chromecast with Google TV')
        self.assertContains(response, 'value="거실 TV"')
        self.assertFalse(Device.objects.exists())       # 보기만 해서는 연결되지 않는다

    def test_empty_form(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('web:activate')), '8글자 코드')

    def test_lookup_is_rate_limited(self):
        self.client.force_login(self.user)
        for _ in range(30):
            self.client.get(reverse('web:activate'), {'code': 'XXXX-XXXX'})
        self.assertEqual(self.client.get(reverse('web:activate'), {'code': 'XXXX-XXXX'}).status_code, 429)


class DeviceTokenUseTest(DeviceFlowBase):

    def as_device(self, tokens):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
        return client

    def test_device_token_reads_user_scores_and_updates_last_seen(self):
        ScoreFactory(user=self.user, title='Mine')
        tokens = self.connect()
        client = self.as_device(tokens)
        response = client.get('/api/v1/scores/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([s['title'] for s in response.data['results']], ['Mine'])
        device = Device.objects.get()
        self.assertIsNotNone(device.last_seen_at)
        me = client.get('/api/v1/devices/me/')
        self.assertEqual((me.status_code, me.data['id'], me.data['is_this_device']), (200, str(device.pk), True))

    def test_revoke_blocks_access_and_refresh_immediately(self):
        tokens = self.connect()
        client = self.as_device(tokens)
        self.assertEqual(client.get('/api/v1/scores/').status_code, 200)

        device = Device.objects.get()
        self.client.force_login(self.user)
        self.client.post(reverse('web:device_revoke', args=[device.pk]))
        device.refresh_from_db()
        self.assertIsNotNone(device.revoked_at)

        response = client.get('/api/v1/scores/')
        self.assertEqual(response.status_code, 401)
        refresh = APIClient().post('/api/v1/auth/token/refresh/', {'refresh': tokens['refresh_token']}, format='json')
        self.assertEqual(refresh.status_code, 401)

    def test_refresh_rotation_keeps_device_lifetime(self):
        tokens = self.connect()
        response = APIClient().post('/api/v1/auth/token/refresh/', {'refresh': tokens['refresh_token']}, format='json')
        self.assertEqual(response.status_code, 200)
        rotated = RefreshToken(response.data['refresh'])
        self.assertEqual(rotated['device_id'], tokens['device_id'])
        self.assertGreater(rotated['exp'] - rotated['iat'], 170 * 86400)
        self.assertEqual(AccessToken(response.data['access'])['device_id'], tokens['device_id'])

    def test_user_refresh_keeps_default_lifetime(self):
        refresh = RefreshToken.for_user(self.user)
        response = APIClient().post('/api/v1/auth/token/refresh/', {'refresh': str(refresh)}, format='json')
        self.assertEqual(response.status_code, 200)
        rotated = RefreshToken(response.data['refresh'])
        self.assertNotIn('device_id', rotated.payload)
        self.assertLessEqual(rotated['exp'] - rotated['iat'], 86400)

    def test_user_token_is_not_a_device(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        self.assertEqual(client.get('/api/v1/devices/me/').status_code, 404)


class DeviceManagementTest(DeviceFlowBase):

    def test_api_list_rename_revoke(self):
        tokens = self.connect()
        device_id = tokens['device_id']
        client = APIClient()
        client.force_authenticate(user=self.user)
        listing = client.get('/api/v1/devices/')
        self.assertEqual([d['id'] for d in listing.data], [device_id])
        self.assertEqual(client.patch(f'/api/v1/devices/{device_id}/', {'name': '안방 TV'}, format='json').status_code, 200)
        self.assertEqual(Device.objects.get().name, '안방 TV')
        self.assertEqual(client.delete(f'/api/v1/devices/{device_id}/').status_code, 204)
        self.assertFalse(Device.objects.get().is_active)
        self.assertTrue(Device.objects.exists())           # 기록은 남는다

    def test_other_users_device_is_invisible(self):
        tokens = self.connect()
        client = APIClient()
        client.force_authenticate(user=self.other)
        self.assertEqual(client.get('/api/v1/devices/').data, [])
        self.assertEqual(client.delete(f"/api/v1/devices/{tokens['device_id']}/").status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('web:device_revoke', args=[tokens['device_id']])).status_code, 404)
        self.assertTrue(Device.objects.get().is_active)

    def test_web_devices_page_and_rename(self):
        self.connect()
        device = Device.objects.get()
        self.client.force_login(self.user)
        response = self.client.get(reverse('web:devices'))
        self.assertContains(response, '거실 TV')
        self.assertContains(response, 'Chromecast with Google TV')
        self.client.post(reverse('web:device_rename', args=[device.pk]), {'name': '합주실 TV'})
        device.refresh_from_db()
        self.assertEqual(device.name, '합주실 TV')
