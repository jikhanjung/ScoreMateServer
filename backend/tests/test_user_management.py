"""
사용자 관리 — 관리자(superuser)만: 등급 · 저장 공간 · 관리자 권한 · 사용 중지 (core/services.py · 웹 /manage/users/ · API). devlog 075
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from core import services
from devices import services as device_services
from devices.models import Device
from .factories import UserFactory
from .test_web import WebTestBase


class UserManagementTest(WebTestBase):

    def setUp(self):
        super().setUp()
        self.admin = UserFactory(username='boss', is_superuser=True, is_staff=True)

    # --- 규칙 ---
    def test_grade_sets_default_quota_unless_given(self):
        services.update_user(self.admin, self.member, grade='pro')
        self.member.refresh_from_db()
        self.assertEqual((self.member.plan, self.member.total_quota_mb), ('pro', 1000))
        services.update_user(self.admin, self.member, grade='enterprise', quota_mb=1234)
        self.member.refresh_from_db()
        self.assertEqual((self.member.plan, self.member.total_quota_mb), ('enterprise', 1234))
        with self.assertRaises(services.UserRuleError):
            services.update_user(self.admin, self.member, grade='gold')

    def test_only_superusers(self):
        self.owner.is_staff = True
        self.owner.save()
        with self.assertRaises(PermissionDenied):
            services.update_user(self.owner, self.member, quota_mb=999)

    def test_superuser_role_follows_staff(self):
        services.update_user(self.admin, self.member, is_superuser=True)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_superuser and self.member.is_staff)
        services.update_user(self.admin, self.member, is_superuser=False)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_superuser or self.member.is_staff)

    def test_guards(self):
        with self.assertRaises(services.UserRuleError):
            services.update_user(self.admin, self.admin, is_superuser=False)
        with self.assertRaises(services.UserRuleError):
            services.update_user(self.admin, self.admin, is_active=False)
        other = UserFactory(username='boss2', is_superuser=True)
        services.update_user(other, self.admin, is_superuser=False)            # 다른 관리자가 있으면 내릴 수 있다
        self.admin.refresh_from_db()
        with self.assertRaises(services.UserRuleError):                        # 이제 other 가 마지막 활성 관리자
            services.update_user(other, other, is_active=False)

    def test_last_active_superuser_cannot_be_removed_by_another(self):
        # 사용 중지된 관리자가 남은 유일한 활성 관리자를 내릴 수는 없다(요청 자체가 거부된다)
        other = UserFactory(username='boss2', is_superuser=True, is_active=False)
        with self.assertRaises(PermissionDenied):
            services.update_user(other, self.admin, is_superuser=False)

    # --- 사용 중지 ---
    def test_deactivated_user_cannot_log_in_or_sync(self):
        tokens = device_services.issue_tokens(Device.objects.create(user=self.member, name='TV'))
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
        self.assertEqual(api.get('/api/v1/sync/scores/').status_code, 200)
        self.assertTrue(self.client_class().login(username=self.member.email, password='testpass123'))
        services.update_user(self.admin, self.member, is_active=False)
        self.assertFalse(self.client.login(username=self.member.email, password='testpass123'))
        self.assertEqual(api.get('/api/v1/sync/scores/').status_code, 401)
        self.assertEqual(APIClient().post('/api/v1/auth/token/refresh/', {'refresh': tokens['refresh_token']},
                                          format='json').status_code, 401)

    def test_deactivated_session_ends(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('web:scores')).status_code, 200)
        services.update_user(self.admin, self.member, is_active=False)
        self.assertEqual(self.client.get(reverse('web:scores')).status_code, 302)

    # --- 웹 ---
    def test_menu_and_pages_are_superuser_only(self):
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('web:scores')), '사용자 관리')
        self.assertEqual(self.client.get(reverse('web:users')).status_code, 404)
        self.assertEqual(self.client.post(reverse('web:user_edit', args=[self.member.pk]), {'quota_mb': 9}).status_code, 404)
        self.client.force_login(self.admin)
        page = self.client.get(reverse('web:users'))
        self.assertContains(page, '사용자 관리')
        self.assertContains(page, 'member')
        self.assertContains(self.client.get(reverse('web:users'), {'q': 'lead'}), 'leader')
        self.assertNotContains(self.client.get(reverse('web:users'), {'q': 'lead'}), '>member<')

    def test_edit_form(self):
        self.client.force_login(self.admin)
        url = reverse('web:user_edit', args=[self.member.pk])
        self.assertContains(self.client.get(url), '저장 공간 한도')
        # 등급만 바꾸고 한도 칸은 그대로 → 등급 기본 한도
        self.client.post(url, {'grade': 'pro', 'quota_mb': self.member.total_quota_mb, 'is_active': 'on'})
        self.member.refresh_from_db()
        self.assertEqual((self.member.plan, self.member.total_quota_mb), ('pro', 1000))
        self.client.post(url, {'grade': 'pro', 'quota_mb': '1500', 'is_active': 'on', 'is_superuser': 'on'})
        self.member.refresh_from_db()
        self.assertEqual((self.member.total_quota_mb, self.member.is_superuser), (1500, True))
        self.client.post(url, {'grade': 'pro', 'quota_mb': '1500'})             # 둘 다 끄기
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active or self.member.is_superuser)

    def test_edit_self_keeps_role(self):
        self.client.force_login(self.admin)
        url = reverse('web:user_edit', args=[self.admin.pk])
        page = self.client.post(url, {'grade': 'solo', 'quota_mb': '300'}, follow=True)   # 체크 칸이 꺼져 와도
        self.assertContains(page, '자기 자신의 관리자 권한은 뺄 수 없습니다')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser and self.admin.is_active)
        self.client.post(url, {'grade': 'solo', 'quota_mb': '300', 'is_superuser': 'on', 'is_active': 'on'})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.total_quota_mb, 300)

    # --- API ---
    def test_api_goes_through_rules(self):
        api = APIClient()
        api.force_authenticate(self.admin)
        url = f'/api/v1/admin/users/{self.member.pk}/'
        response = api.patch(url, {'plan': 'pro', 'used_quota_mb': 0.0}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['plan'], response.json()['total_quota_mb']), ('pro', 1000))
        self.assertEqual(api.patch(f'/api/v1/admin/users/{self.admin.pk}/', {'is_active': False},
                                   format='json').status_code, 400)
        staff = UserFactory(username='staff', is_staff=True)
        api.force_authenticate(staff)
        self.assertEqual(api.get('/api/v1/admin/users/').status_code, 403)

    # --- 비밀번호 다시 정하기 ---
    def test_reset_password_on_web(self):
        member_client = self.client_class()
        member_client.force_login(self.member)
        self.client.force_login(self.admin)
        url = reverse('web:user_password', args=[self.member.pk])
        page = self.client.post(url, {'new_password1': 'Fresh-pass-2026', 'new_password2': 'Fresh-pass-2026'}, follow=True)
        self.assertContains(page, '비밀번호를 새로 정했습니다')
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('Fresh-pass-2026'))
        self.assertEqual(member_client.get(reverse('web:scores')).status_code, 302)     # 웹 세션이 끝났다
        self.assertTrue(self.client_class().login(username=self.member.email, password='Fresh-pass-2026'))

    def test_reset_password_checks(self):
        self.client.force_login(self.admin)
        url = reverse('web:user_password', args=[self.member.pk])
        self.client.post(url, {'new_password1': 'Fresh-pass-2026', 'new_password2': 'other-pass-2026'})   # 서로 다름
        self.client.post(url, {'new_password1': '1234', 'new_password2': '1234'})                         # 너무 짧음
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('testpass123'))
        page = self.client.post(reverse('web:user_password', args=[self.admin.pk]),
                                {'new_password1': 'Fresh-pass-2026', 'new_password2': 'Fresh-pass-2026'}, follow=True)
        self.assertContains(page, '자기 비밀번호는 계정 화면에서')
        self.assertNotContains(self.client.get(reverse('web:user_edit', args=[self.admin.pk])), '비밀번호 정하기</button>')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, {'new_password1': 'Fresh-pass-2026',
                                                'new_password2': 'Fresh-pass-2026'}).status_code, 404)

    def test_reset_password_api(self):
        api = APIClient()
        api.force_authenticate(self.admin)
        url = f'/api/v1/admin/users/{self.member.pk}/reset_password/'
        self.assertEqual(api.post(url, {'new_password': '1234'}, format='json').status_code, 400)
        self.assertEqual(api.post(url, {'new_password': 'Fresh-pass-2026'}, format='json').status_code, 200)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('Fresh-pass-2026'))

    # --- 사용자 추가 ---
    def test_create_user_on_web(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('web:users')), '사용자 추가')
        page = self.client.post(reverse('web:user_create'), {
            'email': 'New@Example.com', 'username': 'newbie', 'password1': 'Fresh-pass-2026',
            'password2': 'Fresh-pass-2026', 'grade': 'pro'}, follow=True)
        self.assertContains(page, 'newbie (new@example.com) 을 추가했습니다')
        user = get_user_model().objects.get(email='new@example.com')
        self.assertEqual((user.plan, user.total_quota_mb, user.is_superuser, user.is_active), ('pro', 1000, False, True))
        self.assertTrue(self.client_class().login(username='new@example.com', password='Fresh-pass-2026'))

    def test_create_user_checks(self):
        self.client.force_login(self.admin)
        url = reverse('web:user_create')
        base = {'username': 'x2', 'password1': 'Fresh-pass-2026', 'password2': 'Fresh-pass-2026', 'grade': 'solo'}
        self.assertContains(self.client.post(url, dict(base, email=self.member.email)), '이미 가입된 이메일')
        self.assertContains(self.client.post(url, dict(base, email='a@b.kr', username='member')), '이미 쓰는 이름')
        self.client.post(url, dict(base, email='c@d.kr', password1='1234', password2='1234'))
        self.assertFalse(get_user_model().objects.filter(email__in=['a@b.kr', 'c@d.kr']).exists())
        with self.assertRaises(services.UserRuleError):
            services.create_user(self.admin, email='e@f.kr', username='e', password='Fresh-pass-2026', grade='gold')
        with self.assertRaises(PermissionDenied):
            services.create_user(self.owner, email='e@f.kr', username='e', password='Fresh-pass-2026')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 404)

    @override_settings(REGISTRATION_OPEN=False)
    def test_create_user_while_registration_closed(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('web:user_create'), {'email': 'g@h.kr', 'username': 'g', 'password1': 'Fresh-pass-2026',
                                                      'password2': 'Fresh-pass-2026', 'grade': 'solo', 'is_superuser': 'on'})
        user = get_user_model().objects.get(email='g@h.kr')
        self.assertTrue(user.is_superuser and user.is_staff)

    def test_create_user_api(self):
        api = APIClient()
        api.force_authenticate(self.admin)
        response = api.post('/api/v1/admin/users/', {'email': 'i@j.kr', 'username': 'ij', 'password': 'Fresh-pass-2026',
                                                      'plan': 'enterprise'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['total_quota_mb'], 5000)
        self.assertEqual(api.post('/api/v1/admin/users/', {'email': 'i@j.kr', 'username': 'ij2',
                                                           'password': 'Fresh-pass-2026'}, format='json').status_code, 400)

