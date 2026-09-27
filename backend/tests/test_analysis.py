"""
S6 — 악보 분석 공유: TV 가 만든 분석(마디 · 보표 시스템 · 박자표)을 판마다 서버에 두고 멤버 TV 가 나눈다
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from devices import services as device_services
from ensembles.models import Membership
from scores.models import Score, ScoreAnalysis, ScoreVersion, version_key
from .factories import EnsembleFactory, MembershipFactory, ScoreFactory, UserFactory

SHA = 'ab' * 32
MEASURES = {'schema': 1, 'measures': [
    {'number': 1, 'page': 0, 'system': 0, 'time_signature': [3, 4]},
    {'number': 2, 'page': 0, 'system': 0},
]}


@override_settings(SYNC_LAG_SECONDS=0)
class AnalysisTestBase(TestCase):

    def setUp(self):
        self.leader = UserFactory(username='leader')
        self.member = UserFactory(username='member')
        self.other_member = UserFactory(username='other')
        self.outsider = UserFactory(username='outsider')
        self.ensemble = EnsembleFactory()
        MembershipFactory(ensemble=self.ensemble, user=self.leader, role=Membership.ROLE_LEADER)
        MembershipFactory(ensemble=self.ensemble, user=self.member)
        MembershipFactory(ensemble=self.ensemble, user=self.other_member)
        self.score = ScoreFactory(user=self.leader, ensemble=self.ensemble, content_hash=SHA)
        ScoreVersion.objects.filter(score=self.score).update(content_hash=SHA)
        self.score.refresh_from_db()

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def tv(self, user):
        authorization, _ = device_services.start_authorization('TV', 'Chromecast', '1.0')
        device = device_services.approve(authorization, user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {device_services.issue_tokens(device)['access_token']}")
        return client, device

    def put(self, client, analyzer_version='12', sha=SHA, data=MEASURES, analyzer='mrgq-measures'):
        return client.put(f'/api/v1/scores/{self.score.pk}/analysis/', {
            'analyzer': analyzer, 'analyzer_version': analyzer_version, 'sha256': sha, 'data': data}, format='json')


class AnalysisShareTest(AnalysisTestBase):

    def test_tv_uploads_and_members_receive(self):
        tv, device = self.tv(self.member)
        cursor = self.api(self.other_member).get('/api/v1/sync/scores/').data['cursor']
        Score.objects.filter(pk=self.score.pk).update(updated_at=timezone.now() - timedelta(minutes=5))

        response = self.put(tv)
        self.assertEqual(response.status_code, 201, response.data)
        analysis = ScoreAnalysis.objects.get()
        self.assertEqual((analysis.uploaded_by, analysis.device_id, analysis.version.number), (self.member, device.pk, 1))

        # 다른 멤버의 TV: 동기화에 분석이 있다고 오고(악보가 바뀐 것으로), 받아 간다
        other = self.api(self.other_member)
        sync = other.get('/api/v1/sync/scores/', {'cursor': cursor}).data
        self.assertEqual([s['id'] for s in sync['scores']], [self.score.pk])
        self.assertEqual([(a['analyzer'], a['analyzer_version']) for a in sync['scores'][0]['version']['analyses']],
                         [('mrgq-measures', '12')])
        got = other.get(f'/api/v1/scores/{self.score.pk}/analysis/', {'analyzer': 'mrgq-measures'}).data
        self.assertEqual(got['version'], 1)
        self.assertEqual(got['analyses'][0]['data'], MEASURES)
        self.assertEqual(got['analyses'][0]['sha256'], SHA)

    def test_mismatch_processing_and_size(self):
        client = self.api(self.member)
        response = self.put(client, sha='cd' * 32)
        self.assertEqual((response.status_code, response.data['error']), (409, 'mismatch'))
        ScoreVersion.objects.filter(score=self.score).update(content_hash='')
        response = self.put(client)
        self.assertEqual((response.status_code, response.data['error']), (409, 'processing'))
        ScoreVersion.objects.filter(score=self.score).update(content_hash=SHA)
        with patch.object(ScoreAnalysis, 'MAX_BYTES', 20):
            self.assertEqual(self.put(client).status_code, 413)
        self.assertEqual(self.put(client, analyzer='Bad Name!').status_code, 400)
        self.assertFalse(ScoreAnalysis.objects.exists())

    def test_members_only_replace_with_newer_analyzer(self):
        self.assertEqual(self.put(self.api(self.member), analyzer_version='12').status_code, 201)
        response = self.put(self.api(self.other_member), analyzer_version='12')
        self.assertEqual((response.status_code, response.data['error']), (409, 'not_newer'))
        self.assertEqual(self.put(self.api(self.other_member), analyzer_version='11.9').status_code, 409)
        response = self.put(self.api(self.other_member), analyzer_version='12.1', data={'schema': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ScoreAnalysis.objects.get().data, {'schema': 2})
        # 리더는 언제나 (잘못된 분석을 바로잡는다)
        self.assertEqual(self.put(self.api(self.leader), analyzer_version='12', data=MEASURES).status_code, 200)
        self.assertEqual(ScoreAnalysis.objects.get().analyzer_version, '12')

    def test_new_version_starts_without_analysis(self):
        self.put(self.api(self.member))
        from scores.services import add_version
        v2 = add_version(self.score, user=self.leader, s3_key=f'{self.leader.id}/uploads/x/original.pdf', size_bytes=10)
        ScoreVersion.objects.filter(pk=v2.pk).update(content_hash='ef' * 32)
        client = self.api(self.member)
        self.assertEqual(client.get(f'/api/v1/scores/{self.score.pk}/analysis/').data['analyses'], [])
        self.assertEqual(len(client.get(f'/api/v1/scores/{self.score.pk}/analysis/', {'version': 1}).data['analyses']), 1)
        self.assertEqual(self.put(client).data['error'], 'mismatch')      # 옛 판의 해시로는 새 판에 못 붙인다
        self.assertEqual(client.get(f'/api/v1/scores/{self.score.pk}/analysis/', {'analyzer': 'x'}).status_code, 404)

    def test_outsider(self):
        self.assertEqual(self.put(self.api(self.outsider)).status_code, 404)
        self.assertEqual(self.api(self.outsider).get(f'/api/v1/scores/{self.score.pk}/analysis/').status_code, 404)


class VersionKeyTest(TestCase):

    def test_ordering(self):
        self.assertGreater(version_key('2.10'), version_key('2.9'))
        self.assertGreater(version_key('12.1'), version_key('12'))
        self.assertEqual(version_key('12'), version_key('12'))
        self.assertGreater(version_key('1.0.1'), version_key('1.0'))
