"""
S6 — Google 로그인 (OpenID Connect 인가 코드 흐름, web/google.py)

Google 과의 통신(exchange_code)만 바꿔 끼우고 state · nonce · iss · aud · exp · email_verified 확인과
계정 연결 · 초대 전용 규칙은 실제 코드로 돈다.
"""
import base64
import json
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import SocialAccount, User
from ensembles.models import Invite, Membership
from .factories import EnsembleFactory, MembershipFactory, UserFactory

CLIENT_ID = 'test-client.apps.googleusercontent.com'


def id_token(**claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return f'eyJhbGciOiJSUzI1NiJ9.{body}.signature'


@override_settings(GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET='secret', REGISTRATION_OPEN=False)
class GoogleLoginTest(TestCase):

    def setUp(self):
        self.owner = UserFactory(username='owner', email='owner@example.com')
        self.ensemble = EnsembleFactory(name='Guitar Ensemble')
        MembershipFactory(ensemble=self.ensemble, user=self.owner, role=Membership.ROLE_OWNER)

    def start(self, **params):
        response = self.client.get(reverse('web:google_start'), params)
        self.assertEqual(response.status_code, 302)
        location = urlparse(response['Location'])
        self.assertEqual(f'{location.scheme}://{location.netloc}{location.path}', 'https://accounts.google.com/o/oauth2/v2/auth')
        return {k: v[0] for k, v in parse_qs(location.query).items()}

    def finish(self, query, state=None, **claims):
        base = {'iss': 'https://accounts.google.com', 'aud': CLIENT_ID, 'exp': int(time.time()) + 3600,
                'nonce': query['nonce'], 'sub': '1234567890', 'email': 'new@gmail.com', 'email_verified': True,
                'name': 'New Person'}
        base.update(claims)
        with patch('web.google.exchange_code', return_value={'id_token': id_token(**base)}) as exchange:
            response = self.client.get(reverse('web:google_callback'), {'code': 'auth-code', 'state': state or query['state']})
        return response, exchange

    def test_disabled_without_credentials(self):
        with override_settings(GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET=''):
            self.assertEqual(self.client.get(reverse('web:google_start')).status_code, 404)
            self.assertNotContains(self.client.get(reverse('web:login')), 'Google')

    def test_start_parameters(self):
        query = self.start(next='/ensembles/')
        self.assertEqual(query['client_id'], CLIENT_ID)
        self.assertEqual(query['redirect_uri'], 'http://testserver/auth/google/callback/')
        self.assertEqual(query['scope'], 'openid email profile')
        self.assertTrue(query['state'] and query['nonce'])
        self.assertContains(self.client.get(reverse('web:login')), 'Google 로 계속하기')

    def test_existing_email_links_and_logs_in(self):
        query = self.start(next='/ensembles/')
        response, exchange = self.finish(query, sub='g-owner', email='OWNER@example.com')
        self.assertRedirects(response, '/ensembles/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.owner.pk)
        account = SocialAccount.objects.get()
        self.assertEqual((account.user, account.subject, account.email), (self.owner, 'g-owner', 'owner@example.com'))
        exchange.assert_called_once_with('auth-code', 'http://testserver/auth/google/callback/')

        # 다음부터는 sub 로 — 구글 쪽 이메일이 바뀌어도 같은 사람
        self.client.logout()
        response, _ = self.finish(self.start(), sub='g-owner', email='renamed@gmail.com')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.owner.pk)
        self.assertEqual(SocialAccount.objects.count(), 1)

    def test_new_person_without_invite_is_blocked(self):
        response, _ = self.finish(self.start())
        self.assertContains(response, '초대받은 분만', status_code=403)
        self.assertFalse(User.objects.filter(email='new@gmail.com').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_new_person_with_invite_joins(self):
        invite = Invite.objects.create(ensemble=self.ensemble, created_by=self.owner)
        query = self.start(next=reverse('web:join', args=[invite.code]))
        response, _ = self.finish(query)
        self.assertRedirects(response, reverse('web:ensemble_detail', args=[self.ensemble.pk]))
        user = User.objects.get(email='new@gmail.com')
        self.assertEqual(user.username, 'New Person')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(self.ensemble.is_member(user))
        invite.refresh_from_db()
        self.assertEqual(invite.uses, 1)

        # 비밀번호가 없는 계정은 기존 비밀번호 없이 정한다
        page = self.client.get(reverse('web:account'))
        self.assertContains(page, '비밀번호 정하기')
        self.assertContains(page, 'new@gmail.com 연결됨')
        self.client.post(reverse('web:account'), {'new_password1': 'a-Long-pass-9', 'new_password2': 'a-Long-pass-9'})
        user.refresh_from_db()
        self.assertTrue(user.check_password('a-Long-pass-9'))

    @override_settings(REGISTRATION_OPEN=True)
    def test_open_registration_creates_account(self):
        response, _ = self.finish(self.start(), name='owner')   # 이름이 겹치면 번호를 붙인다
        self.assertRedirects(response, reverse('web:scores'), fetch_redirect_response=False)
        self.assertEqual(User.objects.get(email='new@gmail.com').username, 'owner2')

    def test_rejections(self):
        cases = [
            ({'state': 'forged'}, {}),
            ({}, {'nonce': 'other'}),
            ({}, {'aud': 'someone-else'}),
            ({}, {'iss': 'https://evil.example'}),
            ({}, {'exp': int(time.time()) - 3600}),
            ({}, {'email_verified': False}),
        ]
        for extra_params, claims in cases:
            query = self.start()
            response, _ = self.finish(query, state=extra_params.get('state'), sub='g-owner', email='owner@example.com', **claims)
            self.assertRedirects(response, reverse('web:login'), fetch_redirect_response=False, msg_prefix=str(claims or extra_params))
            self.assertNotIn('_auth_user_id', self.client.session, str(claims or extra_params))
        self.assertFalse(SocialAccount.objects.exists())

    def test_callback_without_session_or_cancelled(self):
        response = self.client.get(reverse('web:google_callback'), {'code': 'x', 'state': 'y'})
        self.assertRedirects(response, reverse('web:login'), fetch_redirect_response=False)
        query = self.start()
        response = self.client.get(reverse('web:google_callback'), {'error': 'access_denied', 'state': query['state']})
        self.assertRedirects(response, reverse('web:login'), fetch_redirect_response=False)

    def test_state_is_single_use(self):
        query = self.start()
        self.finish(query, sub='g-owner', email='owner@example.com')
        self.client.logout()
        response, _ = self.finish(query, sub='g-owner', email='owner@example.com')   # 같은 state 로 다시
        self.assertRedirects(response, reverse('web:login'), fetch_redirect_response=False)
