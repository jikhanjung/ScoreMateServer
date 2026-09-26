"""
S1 — 앙상블 · 멤버 · 초대, 앙상블 악보 권한 (devlog 054)

확인할 것: 멤버 읽기 · 비멤버 404 · owner/leader 만 쓰기
"""
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ensembles.models import Ensemble, Membership, Invite, INVITE_CODE_LENGTH
from scores.models import Score
from .factories import UserFactory, ScoreFactory, EnsembleFactory, MembershipFactory


class EnsembleTestBase(APITestCase):
    """owner · leader · member · 바깥 사람 한 명씩, 앙상블 악보 하나와 각자의 개인 악보"""

    def setUp(self):
        self.owner = UserFactory()
        self.leader = UserFactory()
        self.member = UserFactory()
        self.outsider = UserFactory()

        self.ensemble = EnsembleFactory(name='Guitar Ensemble', created_by=self.owner)
        MembershipFactory(ensemble=self.ensemble, user=self.owner, role=Membership.ROLE_OWNER)
        MembershipFactory(ensemble=self.ensemble, user=self.leader, role=Membership.ROLE_LEADER)
        MembershipFactory(ensemble=self.ensemble, user=self.member, role=Membership.ROLE_MEMBER, part='Guitar 2')

        self.ensemble_score = ScoreFactory(user=self.leader, ensemble=self.ensemble, part_name='총보',
                                           size_bytes=10 * 1024 * 1024)
        self.member_personal = ScoreFactory(user=self.member)
        self.outsider_personal = ScoreFactory(user=self.outsider)

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def score_url(self, score):
        return f'/api/v1/scores/{score.id}/'

    def ensemble_url(self, ensemble=None, suffix=''):
        return f'/api/v1/ensembles/{(ensemble or self.ensemble).id}/{suffix}'


class ScoreQuerySetTest(EnsembleTestBase):

    def test_readable_by_member(self):
        ids = set(Score.objects.readable_by(self.member).values_list('id', flat=True))
        self.assertEqual(ids, {self.ensemble_score.id, self.member_personal.id})

    def test_readable_by_outsider(self):
        ids = set(Score.objects.readable_by(self.outsider).values_list('id', flat=True))
        self.assertEqual(ids, {self.outsider_personal.id})

    def test_readable_has_no_duplicates_with_many_members(self):
        # 멤버십 행이 여러 개라도 악보는 한 번만
        self.assertEqual(Score.objects.readable_by(self.owner).count(), 1)

    def test_uploader_outside_ensemble_cannot_read(self):
        # 올린 사람이라도 앙상블을 나가면 앙상블 악보는 보이지 않는다
        Membership.objects.filter(ensemble=self.ensemble, user=self.leader).delete()
        self.assertFalse(Score.objects.readable_by(self.leader).filter(id=self.ensemble_score.id).exists())

    def test_writable_by_roles(self):
        self.assertTrue(Score.objects.writable_by(self.owner).filter(id=self.ensemble_score.id).exists())
        self.assertTrue(Score.objects.writable_by(self.leader).filter(id=self.ensemble_score.id).exists())
        self.assertFalse(Score.objects.writable_by(self.member).filter(id=self.ensemble_score.id).exists())
        self.assertTrue(Score.objects.writable_by(self.member).filter(id=self.member_personal.id).exists())

    def test_leader_elsewhere_cannot_write(self):
        # 다른 앙상블의 리더라는 것이 이 앙상블의 쓰기 권한이 되지 않는다 (같은 멤버십 행 조건)
        other = EnsembleFactory()
        MembershipFactory(ensemble=other, user=self.member, role=Membership.ROLE_LEADER)
        self.assertFalse(Score.objects.writable_by(self.member).filter(id=self.ensemble_score.id).exists())

    def test_can_read_and_edit(self):
        self.assertTrue(self.ensemble_score.can_read(self.member))
        self.assertFalse(self.ensemble_score.can_edit(self.member))
        self.assertTrue(self.ensemble_score.can_edit(self.owner))
        self.assertFalse(self.ensemble_score.can_read(self.outsider))
        self.assertTrue(self.member_personal.can_edit(self.member))
        self.assertFalse(self.member_personal.can_read(self.owner))


class EnsembleAPITest(EnsembleTestBase):

    def test_create_makes_creator_owner(self):
        self.as_user(self.outsider)
        response = self.client.post('/api/v1/ensembles/', {'name': '  String Quartet ', 'description': 'Tue rehearsal'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'String Quartet')
        self.assertEqual(response.data['my_role'], 'owner')
        self.assertEqual(response.data['member_count'], 1)
        ensemble = Ensemble.objects.get(id=response.data['id'])
        self.assertEqual(ensemble.created_by, self.outsider)
        self.assertEqual(ensemble.role_of(self.outsider), Membership.ROLE_OWNER)

    def test_create_requires_name(self):
        self.as_user(self.outsider)
        response = self.client.post('/api/v1/ensembles/', {'name': '   '})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_only_my_ensembles(self):
        EnsembleFactory()  # 아무도 없는 다른 앙상블
        self.as_user(self.member)
        response = self.client.get('/api/v1/ensembles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([e['id'] for e in response.data], [self.ensemble.id])
        self.assertEqual(response.data[0]['my_role'], 'member')
        self.assertEqual(response.data[0]['my_part'], 'Guitar 2')
        self.assertEqual(response.data[0]['member_count'], 3)
        self.assertEqual(response.data[0]['score_count'], 1)

    def test_retrieve_with_members(self):
        self.as_user(self.member)
        response = self.client.get(self.ensemble_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        roles = {m['user']['id']: m['role'] for m in response.data['members']}
        self.assertEqual(roles, {self.owner.id: 'owner', self.leader.id: 'leader', self.member.id: 'member'})

    def test_outsider_gets_404(self):
        self.as_user(self.outsider)
        self.assertEqual(self.client.get(self.ensemble_url()).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(self.ensemble_url(suffix='members/')).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(self.ensemble_url(), {'name': 'x'}).status_code, status.HTTP_404_NOT_FOUND)

    def test_update_by_role(self):
        self.as_user(self.member)
        self.assertEqual(self.client.patch(self.ensemble_url(), {'name': 'Renamed'}).status_code,
                         status.HTTP_403_FORBIDDEN)
        self.as_user(self.leader)
        response = self.client.patch(self.ensemble_url(), {'name': 'Renamed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Renamed')

    def test_delete_only_owner_and_scores_become_personal(self):
        self.as_user(self.leader)
        self.assertEqual(self.client.delete(self.ensemble_url()).status_code, status.HTTP_403_FORBIDDEN)

        self.as_user(self.owner)
        self.assertEqual(self.client.delete(self.ensemble_url()).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Ensemble.objects.filter(id=self.ensemble.id).exists())
        self.ensemble_score.refresh_from_db()
        self.assertIsNone(self.ensemble_score.ensemble)
        self.assertEqual(self.ensemble_score.user, self.leader)


class MembershipAPITest(EnsembleTestBase):

    def member_url(self, user):
        return self.ensemble_url(suffix=f'members/{user.id}/')

    def test_list_members(self):
        self.as_user(self.member)
        response = self.client.get(self.ensemble_url(suffix='members/'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([m['user']['id'] for m in response.data], [self.owner.id, self.leader.id, self.member.id])
        self.assertEqual(response.data[2]['part'], 'Guitar 2')

    def test_owner_changes_role(self):
        self.as_user(self.owner)
        response = self.client.patch(self.member_url(self.member), {'role': 'leader'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ensemble.role_of(self.member), 'leader')

    def test_leader_cannot_change_role(self):
        self.as_user(self.leader)
        response = self.client.patch(self.member_url(self.member), {'role': 'leader'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_role(self):
        self.as_user(self.owner)
        response = self.client.patch(self.member_url(self.member), {'role': 'admin'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_part_assignment(self):
        self.as_user(self.leader)
        response = self.client.patch(self.member_url(self.member), {'part': 'Guitar 1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['part'], 'Guitar 1')

        # 멤버는 자기 파트만
        self.as_user(self.member)
        self.assertEqual(self.client.patch(self.member_url(self.member), {'part': 'Bass'}).status_code,
                         status.HTTP_200_OK)
        self.assertEqual(self.client.patch(self.member_url(self.leader), {'part': 'Bass'}).status_code,
                         status.HTTP_403_FORBIDDEN)
        # 멤버는 자기 역할을 올릴 수 없다
        self.assertEqual(self.client.patch(self.member_url(self.member), {'role': 'owner'}).status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_last_owner_must_stay(self):
        self.as_user(self.owner)
        self.assertEqual(self.client.patch(self.member_url(self.owner), {'role': 'leader'}).status_code,
                         status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.delete(self.member_url(self.owner)).status_code,
                         status.HTTP_400_BAD_REQUEST)

        # 다른 owner 를 세우면 나갈 수 있다
        self.client.patch(self.member_url(self.leader), {'role': 'owner'})
        self.assertEqual(self.client.delete(self.member_url(self.owner)).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.ensemble.is_member(self.owner))

    def test_remove_members_by_role(self):
        self.as_user(self.leader)
        self.assertEqual(self.client.delete(self.member_url(self.owner)).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(self.member_url(self.member)).status_code, status.HTTP_204_NO_CONTENT)

        self.as_user(self.owner)
        self.assertEqual(self.client.delete(self.member_url(self.leader)).status_code, status.HTTP_204_NO_CONTENT)

    def test_member_leaves_and_loses_access(self):
        self.as_user(self.member)
        self.assertEqual(self.client.delete(self.member_url(self.owner)).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(self.member_url(self.member)).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get(self.score_url(self.ensemble_score)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(self.ensemble_url()).status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_member(self):
        self.as_user(self.owner)
        self.assertEqual(self.client.patch(self.member_url(self.outsider), {'part': 'x'}).status_code,
                         status.HTTP_404_NOT_FOUND)


class InviteAPITest(EnsembleTestBase):

    def create_invite(self, user=None, **data):
        self.as_user(user or self.leader)
        return self.client.post(self.ensemble_url(suffix='invites/'), data)

    def join(self, user, code):
        self.as_user(user)
        return self.client.post('/api/v1/ensembles/join/', {'code': code})

    def test_member_cannot_manage_invites(self):
        self.as_user(self.member)
        self.assertEqual(self.client.get(self.ensemble_url(suffix='invites/')).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.create_invite(self.member).status_code, status.HTTP_403_FORBIDDEN)

    def test_create_invite_defaults(self):
        response = self.create_invite()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['code']), INVITE_CODE_LENGTH)
        self.assertTrue(response.data['is_usable'])
        invite = Invite.objects.get(id=response.data['id'])
        self.assertEqual(invite.created_by, self.leader)
        self.assertAlmostEqual((invite.expires_at - timezone.now()).days, Invite.DEFAULT_EXPIRY_DAYS, delta=1)

    def test_create_invite_without_expiry(self):
        response = self.create_invite(expires_in_days=None, max_uses=5)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data['expires_at'])
        self.assertEqual(response.data['max_uses'], 5)

    def test_preview_and_join(self):
        code = self.create_invite().data['code']

        self.as_user(self.outsider)
        response = self.client.get(f'/api/v1/ensembles/invite/{code}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ensemble_name'], 'Guitar Ensemble')
        self.assertEqual(response.data['member_count'], 3)
        self.assertNotIn('members', response.data)

        # 소문자 · 하이픈을 섞어 입력해도 된다
        typed = f'{code[:5].lower()}-{code[5:]}'
        response = self.join(self.outsider, typed)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['my_role'], 'member')
        self.assertTrue(self.ensemble.is_member(self.outsider))
        self.assertEqual(Invite.objects.get(code=code).uses, 1)

        # 가입하면 앙상블 악보가 보인다
        self.assertEqual(self.client.get(self.score_url(self.ensemble_score)).status_code, status.HTTP_200_OK)

    def test_join_again_is_noop(self):
        code = self.create_invite().data['code']
        response = self.join(self.member, code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ensemble.role_of(self.member), 'member')
        self.assertEqual(Invite.objects.get(code=code).uses, 0)

    def test_join_does_not_downgrade_leader(self):
        code = self.create_invite().data['code']
        self.join(self.leader, code)
        self.assertEqual(self.ensemble.role_of(self.leader), 'leader')

    def test_unusable_invites(self):
        expired = Invite.objects.create(ensemble=self.ensemble, expires_at=timezone.now() - timedelta(minutes=1))
        used_up = Invite.objects.create(ensemble=self.ensemble, max_uses=1, uses=1)
        revoked = Invite.objects.create(ensemble=self.ensemble, revoked_at=timezone.now())
        for invite in (expired, used_up, revoked):
            self.assertFalse(invite.is_usable)
            response = self.join(self.outsider, invite.code)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, invite)
            self.assertEqual(self.client.get(f'/api/v1/ensembles/invite/{invite.code}/').status_code,
                             status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.join(self.outsider, 'NOSUCHCODE').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.ensemble.is_member(self.outsider))

    def test_max_uses(self):
        code = self.create_invite(max_uses=1).data['code']
        self.assertEqual(self.join(self.outsider, code).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.join(UserFactory(), code).status_code, status.HTTP_400_BAD_REQUEST)

    def test_revoke(self):
        invite_id = self.create_invite().data['id']
        self.as_user(self.member)
        self.assertEqual(self.client.delete(self.ensemble_url(suffix=f'invites/{invite_id}/')).status_code,
                         status.HTTP_403_FORBIDDEN)
        self.as_user(self.owner)
        self.assertEqual(self.client.delete(self.ensemble_url(suffix=f'invites/{invite_id}/')).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.assertFalse(Invite.objects.get(id=invite_id).is_usable)

        response = self.client.get(self.ensemble_url(suffix='invites/'))
        self.assertEqual(len(response.data), 1)
        self.assertFalse(response.data[0]['is_usable'])

    def test_join_is_throttled(self):
        for _ in range(30):
            self.join(self.outsider, 'WRONGCODE1')
        self.assertEqual(self.join(self.outsider, 'WRONGCODE1').status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class EnsembleScoreAPITest(EnsembleTestBase):

    def test_member_lists_ensemble_scores(self):
        self.as_user(self.member)
        response = self.client.get('/api/v1/scores/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_id = {s['id']: s for s in response.data['results']}
        self.assertEqual(set(by_id), {self.ensemble_score.id, self.member_personal.id})

        shared = by_id[self.ensemble_score.id]
        self.assertEqual(shared['ensemble'], self.ensemble.id)
        self.assertEqual(shared['ensemble_name'], 'Guitar Ensemble')
        self.assertEqual(shared['part_name'], '총보')
        self.assertEqual(shared['uploader']['id'], self.leader.id)
        self.assertFalse(shared['can_edit'])
        self.assertTrue(by_id[self.member_personal.id]['can_edit'])
        self.assertIsNone(by_id[self.member_personal.id]['ensemble'])

    def test_can_edit_for_leader_in_list(self):
        self.as_user(self.owner)
        response = self.client.get('/api/v1/scores/')
        self.assertTrue(response.data['results'][0]['can_edit'])

    def test_filter_by_ensemble(self):
        self.as_user(self.member)
        response = self.client.get('/api/v1/scores/', {'ensemble': 'personal'})
        self.assertEqual([s['id'] for s in response.data['results']], [self.member_personal.id])
        response = self.client.get('/api/v1/scores/', {'ensemble': self.ensemble.id})
        self.assertEqual([s['id'] for s in response.data['results']], [self.ensemble_score.id])
        # 멤버가 아닌 앙상블로 걸러도 아무것도 새지 않는다
        other = EnsembleFactory()
        ScoreFactory(ensemble=other)
        response = self.client.get('/api/v1/scores/', {'ensemble': other.id})
        self.assertEqual(response.data['results'], [])

    def test_outsider_cannot_see_ensemble_score(self):
        self.as_user(self.outsider)
        self.assertEqual(self.client.get(self.score_url(self.ensemble_score)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(self.score_url(self.ensemble_score), {'title': 'x'}).status_code,
                         status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(self.score_url(self.ensemble_score)).status_code,
                         status.HTTP_404_NOT_FOUND)

    def test_member_reads_but_cannot_write(self):
        self.as_user(self.member)
        self.assertEqual(self.client.get(self.score_url(self.ensemble_score)).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.patch(self.score_url(self.ensemble_score), {'title': 'x'}).status_code,
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(self.score_url(self.ensemble_score)).status_code,
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post(self.score_url(self.ensemble_score) + 'regenerate_thumbnail/').status_code,
            status.HTTP_403_FORBIDDEN)
        # 일괄 작업은 쓸 수 있는 악보만 — 없으면 404
        response = self.client.post('/api/v1/scores/bulk_tag/', {
            'score_ids': [self.ensemble_score.id], 'add_tags': ['x']})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.ensemble_score.refresh_from_db()
        self.assertNotIn('x', self.ensemble_score.tags)

    def test_owner_edits_score_uploaded_by_leader(self):
        self.as_user(self.owner)
        response = self.client.patch(self.score_url(self.ensemble_score), {'title': 'Moldau v2', 'part_name': 'Guitar 1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ensemble_score.refresh_from_db()
        self.assertEqual(self.ensemble_score.title, 'Moldau v2')
        self.assertEqual(self.ensemble_score.part_name, 'Guitar 1')
        # 올린 사람은 바뀌지 않는다
        self.assertEqual(self.ensemble_score.user, self.leader)

    def test_file_fields_are_read_only(self):
        self.as_user(self.member)
        response = self.client.patch(self.score_url(self.member_personal), {
            's3_key': f'{self.outsider.id}/scores/x/original.pdf', 'size_bytes': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_personal.refresh_from_db()
        self.assertNotEqual(self.member_personal.size_bytes, 1)
        self.assertTrue(self.member_personal.s3_key.startswith(f'{self.member.id}/'))

    def test_delete_refunds_uploader_quota(self):
        self.leader.used_quota_mb = 50
        self.leader.save()
        self.owner.used_quota_mb = 5
        self.owner.save()

        self.as_user(self.owner)
        self.assertEqual(self.client.delete(self.score_url(self.ensemble_score)).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.leader.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(self.leader.used_quota_mb, 40)
        self.assertEqual(self.owner.used_quota_mb, 5)

    def create_payload(self, user, **extra):
        return {
            'title': 'Arpeggione',
            's3_key': f'{user.id}/uploads/abc/original.pdf',
            'size_bytes': 1024 * 1024,
            'mime': 'application/pdf',
            **extra,
        }

    def test_create_in_ensemble_by_role(self):
        self.as_user(self.leader)
        response = self.client.post('/api/v1/scores/', self.create_payload(
            self.leader, ensemble=self.ensemble.id, part_name='Guitar 1'))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        score = Score.objects.get(id=response.data['id'])
        self.assertEqual(score.ensemble, self.ensemble)
        self.assertEqual(score.part_name, 'Guitar 1')
        self.assertEqual(score.user, self.leader)

        self.as_user(self.member)
        response = self.client.post('/api/v1/scores/', self.create_payload(self.member, ensemble=self.ensemble.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ensemble', response.data['error']['details'])

        self.as_user(self.outsider)
        response = self.client.post('/api/v1/scores/', self.create_payload(self.outsider, ensemble=self.ensemble.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['details']['ensemble'], ['Ensemble not found.'])

    def test_move_personal_score_into_ensemble(self):
        mine = ScoreFactory(user=self.leader)
        self.as_user(self.leader)
        response = self.client.patch(self.score_url(mine), {'ensemble': self.ensemble.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ensemble'], self.ensemble.id)

        # 멤버는 자기 악보를 앙상블로 옮길 수 없다
        self.as_user(self.member)
        response = self.client.patch(self.score_url(self.member_personal), {'ensemble': self.ensemble.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_uploader_moves_score_out(self):
        self.as_user(self.owner)
        response = self.client.patch(self.score_url(self.ensemble_score), {'ensemble': None})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.as_user(self.leader)
        response = self.client.patch(self.score_url(self.ensemble_score), {'ensemble': None})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ensemble_score.refresh_from_db()
        self.assertIsNone(self.ensemble_score.ensemble)

    def test_statistics_cover_readable_scores(self):
        self.as_user(self.member)
        response = self.client.get('/api/v1/scores/statistics/')
        self.assertEqual(response.data['total_scores'], 2)


class EnsembleFilesAPITest(EnsembleTestBase):
    download_url = '/api/v1/files/download-url/'

    @patch('files.utils.S3Handler.generate_presigned_download_url')
    def test_member_downloads_ensemble_score(self, mock_s3):
        mock_s3.return_value = {'url': 'https://example.com/x', 'method': 'GET', 'expires_in': 300}
        self.as_user(self.member)
        response = self.client.get(self.download_url, {'score_id': self.ensemble_score.id, 'file_type': 'original'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_outsider_cannot_download(self):
        self.as_user(self.outsider)
        response = self.client.get(self.download_url, {'score_id': self.ensemble_score.id, 'file_type': 'original'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get(f'/api/v1/files/direct-download/{self.ensemble_score.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('files.utils.S3Handler.generate_presigned_upload_url')
    def test_upload_confirm_into_ensemble(self, mock_s3):
        mock_s3.return_value = {'url': 'https://example.com/upload', 'headers': {}, 'method': 'PUT'}

        def upload_and_confirm(user, **extra):
            self.as_user(user)
            upload = self.client.post('/api/v1/files/upload-url/', {
                'filename': 'moldau.pdf', 'size_bytes': 1024 * 1024, 'mime_type': 'application/pdf'})
            self.assertEqual(upload.status_code, status.HTTP_201_CREATED)
            return self.client.post('/api/v1/files/upload-confirm/', {
                'upload_id': upload.data['upload_id'], 'title': 'Moldau', **extra})

        response = upload_and_confirm(self.leader, ensemble=self.ensemble.id, part_name='Guitar 1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        score = Score.objects.get(id=response.data['score_id'])
        self.assertEqual(score.ensemble, self.ensemble)
        self.assertEqual(score.part_name, 'Guitar 1')
        self.assertEqual(score.original_filename, 'moldau.pdf')

        response = upload_and_confirm(self.member, ensemble=self.ensemble.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ensemble', response.data['error']['details'])
