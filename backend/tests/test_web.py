"""
웹 화면 (Django 템플릿, 세션 로그인) — 규칙은 API 와 같은 곳(scores/services · ensembles/services · readable_by)을 쓴다
"""
import shutil
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ensembles.models import Ensemble, Invite, Membership
from files.utils import load_blob_token
from scores.models import Score
from .factories import EnsembleFactory, MembershipFactory, ScoreFactory, UserFactory

PDF = (Path(__file__).parent / 'LaGazzaLadra.pdf').read_bytes()


def pdf_file(name='Moldau.pdf', data=PDF):
    return SimpleUploadedFile(name, data, content_type='application/pdf')


class WebTestBase(TestCase):

    def setUp(self):
        self.files_root = Path(tempfile.mkdtemp(prefix='scoremate-web-'))
        self.addCleanup(shutil.rmtree, self.files_root, ignore_errors=True)
        overrides = override_settings(STORAGE_BACKEND='local', FILES_ROOT=self.files_root, FILES_X_ACCEL_PREFIX='')
        overrides.enable()
        self.addCleanup(overrides.disable)

        self.owner = UserFactory(username='owner', total_quota_mb=500)
        self.leader = UserFactory(username='leader', total_quota_mb=500, used_quota_mb=40)
        self.member = UserFactory(username='member')
        self.outsider = UserFactory(username='outsider')
        self.ensemble = EnsembleFactory(name='Guitar Ensemble', created_by=self.owner)
        MembershipFactory(ensemble=self.ensemble, user=self.owner, role=Membership.ROLE_OWNER)
        MembershipFactory(ensemble=self.ensemble, user=self.leader, role=Membership.ROLE_LEADER)
        MembershipFactory(ensemble=self.ensemble, user=self.member, role=Membership.ROLE_MEMBER)
        self.shared = ScoreFactory(user=self.leader, ensemble=self.ensemble, title='Moldau', part_name='총보',
                                   size_bytes=10 * 1024 * 1024, s3_key=f'{self.leader.id}/scores/1/original.pdf')
        self.private = ScoreFactory(user=self.outsider, title='Secret')

    def as_user(self, user):
        self.client.force_login(user)


class AuthTest(WebTestBase):

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(reverse('web:scores'))
        self.assertRedirects(response, f"{reverse('web:login')}?next={reverse('web:scores')}")
        self.assertRedirects(self.client.get('/'), reverse('web:login'))

    def test_login_with_email(self):
        response = self.client.post(reverse('web:login'), {'email': self.member.email.upper(), 'password': 'testpass123',
                                                           'next': '/ensembles/'})
        self.assertRedirects(response, '/ensembles/')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)

    def test_login_rejects_external_next(self):
        response = self.client.post(reverse('web:login'), {'email': self.member.email, 'password': 'testpass123',
                                                           'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('web:scores'))

    def test_wrong_password_and_lockout(self):
        for _ in range(10):
            response = self.client.post(reverse('web:login'), {'email': self.member.email, 'password': 'wrong'})
            self.assertContains(response, '맞지 않습니다')
        response = self.client.post(reverse('web:login'), {'email': self.member.email, 'password': 'testpass123'})
        self.assertContains(response, '너무 많습니다')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_register(self):
        response = self.client.post(reverse('web:register'), {
            'email': 'New@Example.com', 'username': 'newbie', 'password1': 'a-Long-pass-9', 'password2': 'a-Long-pass-9'})
        self.assertRedirects(response, reverse('web:scores'))
        self.assertTrue(self.client.session.get('_auth_user_id'))
        self.assertTrue(Score.objects.model._meta.apps.get_model('core', 'User').objects.filter(email='new@example.com').exists())

    def test_register_validation(self):
        response = self.client.post(reverse('web:register'), {
            'email': self.member.email, 'username': 'member', 'password1': '123', 'password2': '1234'})
        self.assertContains(response, '이미 가입된 이메일')
        self.assertContains(response, '이미 쓰는 이름')
        self.assertContains(response, '비밀번호가 서로 다릅니다')

    @override_settings(REGISTRATION_OPEN=False)
    def test_registration_closed_everywhere(self):
        self.assertEqual(self.client.get(reverse('web:register')).status_code, 404)
        self.assertNotContains(self.client.get(reverse('web:login')), reverse('web:register'))
        api = self.client.post('/api/v1/auth/register/', {'email': 'x@example.com', 'username': 'x',
                                                          'password': 'a-Long-pass-9', 'password_confirm': 'a-Long-pass-9'},
                               content_type='application/json')
        self.assertEqual(api.status_code, 403)

    def test_logout_needs_post(self):
        self.as_user(self.member)
        self.assertEqual(self.client.get(reverse('web:logout')).status_code, 405)
        self.assertRedirects(self.client.post(reverse('web:logout')), reverse('web:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_account_and_password_change(self):
        self.as_user(self.leader)
        response = self.client.get(reverse('web:account'))
        self.assertContains(response, '40MB / 500MB')
        response = self.client.post(reverse('web:account'), {
            'old_password': 'testpass123', 'new_password1': 'another-Long-9', 'new_password2': 'another-Long-9'})
        self.assertRedirects(response, reverse('web:account'))
        self.leader.refresh_from_db()
        self.assertTrue(self.leader.check_password('another-Long-9'))


class ScorePagesTest(WebTestBase):

    def test_list_shows_readable_only(self):
        self.as_user(self.member)
        response = self.client.get(reverse('web:scores'))
        self.assertContains(response, 'Moldau')
        self.assertNotContains(response, 'Secret')
        # 필터
        self.assertNotContains(self.client.get(reverse('web:scores'), {'ensemble': 'personal'}), 'Moldau')
        self.assertContains(self.client.get(reverse('web:scores'), {'ensemble': self.ensemble.pk, 'q': 'mold'}), 'Moldau')

    def test_detail_permissions(self):
        self.as_user(self.outsider)
        self.assertEqual(self.client.get(reverse('web:score_detail', args=[self.shared.pk])).status_code, 404)
        self.as_user(self.member)
        response = self.client.get(reverse('web:score_detail', args=[self.shared.pk]))
        self.assertContains(response, 'Moldau')
        self.assertNotContains(response, reverse('web:score_edit', args=[self.shared.pk]))
        self.assertEqual(self.client.get(reverse('web:score_edit', args=[self.shared.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('web:score_delete', args=[self.shared.pk])).status_code, 403)

    def test_view_and_download_links(self):
        self.as_user(self.member)
        view = self.client.get(reverse('web:score_view', args=[self.shared.pk]))
        self.assertEqual(view.status_code, 302)
        token = view['Location'].rstrip('/').rsplit('/', 1)[-1]
        self.assertNotIn('fn', load_blob_token(token))       # 보기 = 브라우저 PDF 뷰어(inline)
        download = self.client.get(reverse('web:score_download', args=[self.shared.pk]))
        token = download['Location'].rstrip('/').rsplit('/', 1)[-1]
        self.assertTrue(load_blob_token(token)['fn'].endswith('.pdf'))
        self.as_user(self.outsider)
        self.assertEqual(self.client.get(reverse('web:score_view', args=[self.shared.pk])).status_code, 404)

    def test_owner_edits_shared_score(self):
        self.as_user(self.owner)
        response = self.client.post(reverse('web:score_edit', args=[self.shared.pk]), {
            'title': 'Moldau v2', 'part_name': 'Guitar 1', 'composer': 'Smetana', 'instrumentation': '',
            'note': '42쪽까지', 'tags_text': '연주회, 2026'})
        self.assertRedirects(response, reverse('web:score_detail', args=[self.shared.pk]))
        self.shared.refresh_from_db()
        self.assertEqual((self.shared.title, self.shared.part_name, self.shared.tags), ('Moldau v2', 'Guitar 1', ['연주회', '2026']))
        self.assertEqual(self.shared.user, self.leader)

    def test_delete_refunds_uploader(self):
        self.as_user(self.owner)
        self.assertContains(self.client.get(reverse('web:score_delete', args=[self.shared.pk])), '멤버 모두에게서')
        response = self.client.post(reverse('web:score_delete', args=[self.shared.pk]))
        self.assertRedirects(response, reverse('web:ensemble_detail', args=[self.ensemble.pk]))
        self.assertFalse(Score.objects.filter(pk=self.shared.pk).exists())
        self.leader.refresh_from_db()
        self.assertEqual(self.leader.used_quota_mb, 30)


class UploadTest(WebTestBase):

    def test_upload_personal_pdf(self):
        self.as_user(self.member)
        response = self.client.post(reverse('web:score_upload'), {'files': pdf_file('La Gazza Ladra.pdf'), 'title': ''})
        score = Score.objects.get(user=self.member)
        self.assertRedirects(response, reverse('web:score_detail', args=[score.pk]))
        self.assertEqual(score.title, 'La Gazza Ladra')
        self.assertIsNone(score.ensemble)
        self.assertGreater(score.pages or 0, 0)                     # 요청 안에서 처리됐다
        self.assertTrue((self.files_root / score.s3_key).is_file())
        self.assertTrue((self.files_root / score.thumbnail_key).is_file())
        self.member.refresh_from_db()
        self.assertEqual(self.member.used_quota_mb, len(PDF) // (1024 * 1024))

    def test_upload_parts_into_ensemble(self):
        self.as_user(self.leader)
        response = self.client.post(reverse('web:score_upload'), {
            'files': [pdf_file('Guitar 1.pdf'), pdf_file('Guitar 2.pdf')], 'title': '블타바',
            'ensemble': self.ensemble.pk, 'tags': '연주회'})
        self.assertRedirects(response, reverse('web:ensemble_detail', args=[self.ensemble.pk]))
        parts = Score.objects.filter(ensemble=self.ensemble, title='블타바').order_by('part_name')
        self.assertEqual([s.part_name for s in parts], ['Guitar 1', 'Guitar 2'])
        self.assertEqual(parts[0].tags, ['연주회'])

    def test_member_cannot_upload_to_ensemble(self):
        self.as_user(self.member)
        response = self.client.get(reverse('web:score_upload'))
        self.assertNotContains(response, 'Guitar Ensemble')
        response = self.client.post(reverse('web:score_upload'), {'files': pdf_file(), 'ensemble': self.ensemble.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Score.objects.filter(user=self.member).exists())

    def test_rejects_non_pdf_and_quota(self):
        self.as_user(self.member)
        response = self.client.post(reverse('web:score_upload'), {'files': pdf_file('x.pdf', b'hello, not a pdf')})
        self.assertContains(response, 'PDF 파일이 아닙니다')
        self.member.total_quota_mb = 1
        self.member.save()
        response = self.client.post(reverse('web:score_upload'), {'files': pdf_file()})
        self.assertContains(response, '저장 공간이 부족합니다')
        self.assertFalse(any(self.files_root.rglob('*.pdf')))


class EnsemblePagesTest(WebTestBase):

    def test_create_and_list(self):
        self.as_user(self.outsider)
        response = self.client.post(reverse('web:ensembles'), {'name': 'String Quartet', 'description': ''})
        ensemble = Ensemble.objects.get(name='String Quartet')
        self.assertRedirects(response, reverse('web:ensemble_detail', args=[ensemble.pk]))
        self.assertTrue(ensemble.is_owner(self.outsider))
        self.assertContains(self.client.get(reverse('web:ensembles')), 'String Quartet')

    def test_detail_is_members_only(self):
        self.as_user(self.outsider)
        self.assertEqual(self.client.get(reverse('web:ensemble_detail', args=[self.ensemble.pk])).status_code, 404)
        self.as_user(self.member)
        response = self.client.get(reverse('web:ensemble_detail', args=[self.ensemble.pk]))
        self.assertContains(response, 'Moldau')
        self.assertNotContains(response, 'id="invites"')           # 멤버에게는 초대 칸이 없다

    def test_invites(self):
        self.as_user(self.member)
        self.assertEqual(self.client.post(reverse('web:invite_create', args=[self.ensemble.pk])).status_code, 403)
        self.as_user(self.leader)
        self.client.post(reverse('web:invite_create', args=[self.ensemble.pk]), {'expires_in_days': '', 'max_uses': '2'})
        invite = Invite.objects.get(ensemble=self.ensemble)
        self.assertIsNone(invite.expires_at)
        self.assertEqual(invite.max_uses, 2)
        response = self.client.get(reverse('web:ensemble_detail', args=[self.ensemble.pk]))
        self.assertContains(response, f'http://testserver/join/{invite.code}/')
        self.client.post(reverse('web:invite_revoke', args=[self.ensemble.pk, invite.pk]))
        invite.refresh_from_db()
        self.assertFalse(invite.is_usable)

    def test_join_flow(self):
        invite = Invite.objects.create(ensemble=self.ensemble, created_by=self.owner)
        url = reverse('web:join', args=[invite.code])
        self.assertRedirects(self.client.get(url), f"{reverse('web:login')}?next={url}", fetch_redirect_response=False)

        self.as_user(self.outsider)
        self.assertContains(self.client.get(url), 'Guitar Ensemble')
        response = self.client.post(url)
        self.assertRedirects(response, reverse('web:ensemble_detail', args=[self.ensemble.pk]))
        self.assertEqual(self.ensemble.role_of(self.outsider), 'member')
        invite.refresh_from_db()
        self.assertEqual(invite.uses, 1)
        # 다시 열면 이미 멤버
        self.assertRedirects(self.client.get(url), reverse('web:ensemble_detail', args=[self.ensemble.pk]))

    def test_join_by_typed_code_and_bad_code(self):
        invite = Invite.objects.create(ensemble=self.ensemble, created_by=self.owner)
        self.as_user(self.outsider)
        typed = f'{invite.code[:5].lower()}-{invite.code[5:]}'
        self.assertRedirects(self.client.get(reverse('web:join_form'), {'code': typed}),
                             reverse('web:join', args=[invite.code]), fetch_redirect_response=False)
        response = self.client.get(reverse('web:join', args=['NOSUCHCODE']))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, '만료된 초대 코드', status_code=404)

    def test_member_role_and_part(self):
        self.as_user(self.owner)
        self.client.post(reverse('web:member_update', args=[self.ensemble.pk, self.member.pk]),
                         {'role': 'leader', 'part': 'Guitar 2'})
        m = Membership.objects.get(ensemble=self.ensemble, user=self.member)
        self.assertEqual((m.role, m.part), ('leader', 'Guitar 2'))

        # leader 는 역할을 못 바꾼다
        self.as_user(self.leader)
        response = self.client.post(reverse('web:member_update', args=[self.ensemble.pk, self.member.pk]), {'role': 'member'})
        self.assertEqual(response.status_code, 403)

    def test_last_owner_protected(self):
        self.as_user(self.owner)
        response = self.client.post(reverse('web:member_remove', args=[self.ensemble.pk, self.owner.pk]), follow=True)
        self.assertContains(response, '소유자는 적어도 한 명')
        self.assertTrue(self.ensemble.is_owner(self.owner))

    def test_leave(self):
        self.as_user(self.member)
        response = self.client.post(reverse('web:member_remove', args=[self.ensemble.pk, self.member.pk]))
        self.assertRedirects(response, reverse('web:ensembles'))
        self.assertFalse(self.ensemble.is_member(self.member))
        self.assertEqual(self.client.get(reverse('web:score_detail', args=[self.shared.pk])).status_code, 404)

    def test_delete_ensemble(self):
        self.as_user(self.leader)
        self.assertEqual(self.client.post(reverse('web:ensemble_delete', args=[self.ensemble.pk])).status_code, 403)
        self.as_user(self.owner)
        self.assertRedirects(self.client.post(reverse('web:ensemble_delete', args=[self.ensemble.pk])), reverse('web:ensembles'))
        self.shared.refresh_from_db()
        self.assertIsNone(self.shared.ensemble)


class CsrfTest(WebTestBase):

    def test_forms_carry_csrf_token(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for name, args in (('web:scores', []), ('web:score_upload', []), ('web:ensembles', []),
                           ('web:ensemble_detail', [self.ensemble.pk]), ('web:account', [])):
            self.assertContains(client.get(reverse(name, args=args)), 'csrfmiddlewaretoken', msg_prefix=name)
        # 토큰 없는 POST 는 막힌다
        self.assertEqual(client.post(reverse('web:ensembles'), {'name': 'x'}).status_code, 403)
