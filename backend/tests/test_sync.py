"""
S4 — TV 동기화: GET /api/v1/sync/scores (scores/sync.py), 받기 리다이렉트, 기기 heartbeat
"""
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from devices import services as device_services
from devices.models import Device
from ensembles import services as ensemble_services
from ensembles.models import Membership
from files.utils import LocalStorageHandler, generate_upload_s3_key, load_blob_token
from scores.models import Score
from setlists.models import Setlist, SetlistItem
from scores.services import add_version, create_score, delete_score
from .factories import EnsembleFactory, MembershipFactory, UserFactory

PDF = (Path(__file__).parent / 'LaGazzaLadra.pdf').read_bytes()


@override_settings(SYNC_LAG_SECONDS=0)
class SyncTestBase(TestCase):

    def setUp(self):
        self.files_root = Path(tempfile.mkdtemp(prefix='scoremate-sync-'))
        self.addCleanup(shutil.rmtree, self.files_root, ignore_errors=True)
        overrides = override_settings(STORAGE_BACKEND='local', FILES_ROOT=self.files_root, FILES_X_ACCEL_PREFIX='')
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.storage = LocalStorageHandler()

        self.me = UserFactory(username='me', total_quota_mb=1000)
        self.leader = UserFactory(username='leader', total_quota_mb=1000)
        self.stranger = UserFactory(username='stranger', total_quota_mb=1000)
        self.ensemble = EnsembleFactory(name='Guitar Ensemble')
        MembershipFactory(ensemble=self.ensemble, user=self.leader, role=Membership.ROLE_OWNER)
        MembershipFactory(ensemble=self.ensemble, user=self.me, role=Membership.ROLE_MEMBER)
        self.client = APIClient()
        self.client.force_authenticate(user=self.me)

    def put(self, user):
        key = generate_upload_s3_key(user.id, 'x.pdf')
        self.storage.write_bytes(key, PDF)
        return key

    def score(self, user, title, ensemble=None, part=''):
        return create_score(user=user, s3_key=self.put(user), size_bytes=len(PDF), title=title,
                            ensemble=ensemble, part_name=part, original_filename=f'{title}.pdf')

    def sync(self, cursor=None, client=None, **params):
        if cursor:
            params['cursor'] = cursor
        response = (client or self.client).get('/api/v1/sync/scores/', params)
        self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        return response.data

    def titles(self, data):
        return [s['title'] for s in data['scores']]


class SyncBasicsTest(SyncTestBase):

    def test_first_sync_then_nothing(self):
        mine = self.score(self.me, 'Mine')
        shared = self.score(self.leader, 'Moldau', self.ensemble, '총보')
        self.score(self.stranger, 'Secret')

        first = self.sync()
        self.assertEqual(sorted(self.titles(first)), ['Mine', 'Moldau'])
        self.assertEqual(first['ids'], sorted([mine.pk, shared.pk]))
        self.assertFalse(first['has_more'])
        self.assertTrue(first['cursor'])

        item = next(s for s in first['scores'] if s['title'] == 'Moldau')
        self.assertEqual(item['ensemble'], {'id': self.ensemble.pk, 'name': 'Guitar Ensemble'})
        self.assertEqual(item['part_name'], '총보')
        self.assertEqual(item['version']['number'], 1)
        self.assertEqual(len(item['version']['sha256']), 64)
        self.assertGreater(item['version']['pages'], 0)
        self.assertEqual(item['download_url'], f'http://testserver/api/v1/scores/{shared.pk}/download/')

        second = self.sync(first['cursor'])
        self.assertEqual(second['scores'], [])
        self.assertEqual(second['cursor'], first['cursor'])
        self.assertEqual(second['ids'], first['ids'])

    def test_empty_library(self):
        data = self.sync()
        self.assertEqual((data['scores'], data['ids'], data['cursor'], data['has_more']), ([], [], None, False))

    def test_bad_cursor(self):
        for bad in ('garbage', 'eyJ0IjoieCJ9', 'eyJ0IjoiMjAyNi0wOS0yN1QwMDowMDowMCIsImkiOjF9'):   # 깨진 · 필드 없음 · naive 시각
            response = self.client.get('/api/v1/sync/scores/', {'cursor': bad})
            self.assertEqual(response.status_code, 400, bad)
        self.assertEqual(self.client.get('/api/v1/sync/scores/', {'limit': '0'}).status_code, 400)

    def test_needs_auth(self):
        self.assertEqual(APIClient().get('/api/v1/sync/scores/').status_code, 401)


class SyncChangesTest(SyncTestBase):

    def test_metadata_change_and_new_version_come_back(self):
        shared = self.score(self.leader, 'Moldau', self.ensemble)
        cursor = self.sync()['cursor']

        Score.objects.filter(pk=shared.pk).update(title='Moldau', updated_at=timezone.now())
        shared.refresh_from_db()
        shared.part_name = 'Guitar 1'
        shared.save()
        data = self.sync(cursor)
        self.assertEqual([s['part_name'] for s in data['scores']], ['Guitar 1'])
        cursor = data['cursor']

        add_version(shared, user=self.leader, s3_key=self.put(self.leader), size_bytes=len(PDF),
                    original_filename='Moldau_0829.pdf', note='42쪽까지')
        data = self.sync(cursor)
        self.assertEqual(len(data['scores']), 1)
        version = data['scores'][0]['version']
        self.assertEqual((version['number'], version['note'], version['filename']), (2, '42쪽까지', 'Moldau_0829.pdf'))
        self.assertEqual(len(version['sha256']), 64)

    def test_joining_ensemble_brings_old_scores(self):
        other = EnsembleFactory(name='Quartet')
        MembershipFactory(ensemble=other, user=self.leader, role=Membership.ROLE_OWNER)
        old = self.score(self.leader, 'Old quartet piece', other)
        Score.objects.filter(pk=old.pk).update(updated_at=timezone.now() - timedelta(days=30))
        self.score(self.me, 'Mine')              # 커서가 옛 악보보다 뒤에 있게
        cursor = self.sync()['cursor']
        self.assertIsNotNone(cursor)
        self.assertNotIn(old.pk, self.sync(cursor)['ids'])

        invite = ensemble_services.create_invite(other, self.leader)
        ensemble_services.join(self.me, invite.code)
        data = self.sync(cursor)
        self.assertEqual(self.titles(data), ['Old quartet piece'])   # 옛 악보지만 새로 보이게 됐다
        self.assertIn(old.pk, data['ids'])

    def test_losing_access_drops_ids(self):
        shared = self.score(self.leader, 'Moldau', self.ensemble)
        mine = self.score(self.me, 'Mine')
        cursor = self.sync()['cursor']

        ensemble_services.remove_member(self.ensemble, self.me, self.ensemble.membership_of(self.me))   # 나가기
        data = self.sync(cursor)
        self.assertEqual(data['ids'], [mine.pk])
        self.assertNotIn(shared.pk, data['ids'])

        delete_score(Score.objects.get(pk=mine.pk))
        self.assertEqual(self.sync(data['cursor'])['ids'], [])

    def test_deleted_ensemble_scores_return_to_uploader(self):
        """앙상블을 지우면 악보가 올린 사람의 개인 악보로 — 멤버가 아닌 올린 사람의 TV 도 받는다"""
        uploader = UserFactory(username='uploader', total_quota_mb=1000)
        MembershipFactory(ensemble=self.ensemble, user=uploader, role=Membership.ROLE_LEADER)
        piece = self.score(uploader, 'Piece', self.ensemble)
        ensemble_services.remove_member(self.ensemble, uploader, self.ensemble.membership_of(uploader))
        uploader_client = APIClient()
        uploader_client.force_authenticate(user=uploader)
        cursor = self.sync(client=uploader_client)['cursor']
        self.assertNotIn(piece.pk, self.sync(cursor, client=uploader_client)['ids'])

        ensemble_services.delete_ensemble(self.ensemble, self.leader)
        data = self.sync(cursor, client=uploader_client)
        self.assertEqual(self.titles(data), ['Piece'])
        self.assertIsNone(data['scores'][0]['ensemble'])
        self.assertNotIn(piece.pk, self.sync()['ids'])   # 나에게서는 사라진다

    def test_pagination_with_ties(self):
        scores = [self.score(self.me, f'S{i}') for i in range(5)]
        same = timezone.now() - timedelta(minutes=1)
        Score.objects.filter(pk__in=[s.pk for s in scores]).update(updated_at=same)   # 같은 시각 — id 로 가른다
        seen, cursor, pages = [], None, 0
        while True:
            data = self.sync(cursor, limit=2)
            seen += [s['id'] for s in data['scores']]
            cursor, pages = data['cursor'], pages + 1
            if not data['has_more']:
                break
        self.assertEqual(seen, sorted(s.pk for s in scores))
        self.assertEqual(pages, 3)
        self.assertEqual(self.sync(cursor)['scores'], [])

    @override_settings(SYNC_LAG_SECONDS=60)
    def test_recent_changes_wait_for_lag(self):
        """방금 바뀐 것은 다음 번으로 — 늦게 커밋되는 변경을 커서가 건너뛰지 않게"""
        fresh = self.score(self.me, 'Fresh')
        data = self.sync()
        self.assertEqual(data['scores'], [])
        self.assertIn(fresh.pk, data['ids'])
        Score.objects.filter(pk=fresh.pk).update(updated_at=timezone.now() - timedelta(minutes=2))
        self.assertEqual(self.titles(self.sync(data['cursor'])), ['Fresh'])


class DownloadRedirectTest(SyncTestBase):

    def test_member_downloads_current_and_old_version(self):
        shared = self.score(self.leader, 'Moldau', self.ensemble)
        v1_key = shared.s3_key
        add_version(shared, user=self.leader, s3_key=self.put(self.leader), size_bytes=len(PDF),
                    original_filename='Moldau_v2.pdf')
        shared.refresh_from_db()

        response = self.client.get(f'/api/v1/scores/{shared.pk}/download/')
        self.assertEqual(response.status_code, 302)
        payload = load_blob_token(response['Location'].rstrip('/').rsplit('/', 1)[-1])
        self.assertEqual((payload['k'], payload['fn']), (shared.s3_key, 'Moldau_v2.pdf'))
        # 리다이렉트를 따라가면 파일
        file_response = self.client.get(response['Location'])
        self.assertEqual(b''.join(file_response.streaming_content), PDF)

        response = self.client.get(f'/api/v1/scores/{shared.pk}/download/', {'version': 1})
        self.assertEqual(load_blob_token(response['Location'].rstrip('/').rsplit('/', 1)[-1])['k'], v1_key)
        self.assertEqual(self.client.get(f'/api/v1/scores/{shared.pk}/download/', {'version': 9}).status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/scores/{shared.pk}/download/', {'version': 'x'}).status_code, 400)

    def test_outsider_404(self):
        shared = self.score(self.leader, 'Moldau', self.ensemble)
        outsider = APIClient()
        outsider.force_authenticate(user=self.stranger)
        self.assertEqual(outsider.get(f'/api/v1/scores/{shared.pk}/download/').status_code, 404)


class DeviceSyncTest(SyncTestBase):

    def device_client(self):
        authorization, device_code = device_services.start_authorization('거실 TV', 'Chromecast', '1.0')
        device = device_services.approve(authorization, self.me)
        # 기기는 고른 세트리스트의 곡만 받는다 — 여기서는 지금 있는 악보를 모두 담은 곡목 하나를 고른다(곡목 범위 규칙은 test_device_setlist_sync.py)
        everything = Setlist.objects.create(user=self.me, title='전부')
        for index, score in enumerate(Score.objects.readable_by(self.me)):
            SetlistItem.objects.create(setlist=everything, score=score, order_index=index)
        device_services.set_sync(device, [everything.pk])
        tokens = device_services.issue_tokens(device)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
        return client, device

    def test_tv_sync_download_and_last_synced(self):
        shared = self.score(self.leader, 'Moldau', self.ensemble)
        tv, device = self.device_client()
        data = self.sync(client=tv)
        self.assertEqual(data['ids'], [shared.pk])
        device.refresh_from_db()
        self.assertIsNotNone(device.last_synced_at)

        redirect = tv.get(data['scores'][0]['download_url'])
        self.assertEqual(redirect.status_code, 302)
        blob = APIClient().get(redirect['Location'])   # 토큰 없이 — 서명 URL 이 권한
        self.assertEqual(b''.join(blob.streaming_content), PDF)

        self.client.force_login(self.me)
        self.assertContains(self.client.get(reverse('web:devices')), '동기화')

    def test_heartbeat(self):
        tv, device = self.device_client()
        response = tv.post('/api/v1/devices/me/heartbeat/', {'app_version': '1.1', 'model': 'Chromecast HD'}, format='json')
        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertEqual((device.app_version, device.model), ('1.1', 'Chromecast HD'))
        self.assertEqual(self.client.post('/api/v1/devices/me/heartbeat/', {}, format='json').status_code, 404)
        # 목록 경로로 기기를 만들 수는 없다
        self.assertEqual(self.client.post('/api/v1/devices/', {'name': 'x'}, format='json').status_code, 405)

    def test_revoked_tv_cannot_sync(self):
        tv, device = self.device_client()
        device_services.revoke(device)
        self.assertEqual(tv.get('/api/v1/sync/scores/').status_code, 401)
        self.assertFalse(Device.objects.get().is_active)


class EnsembleRenameSyncTest(SyncTestBase):
    """TV P06 §1 — 앙상블 이름을 바꾸면(API · 웹 어느 쪽이든) 그 앙상블 악보가 새 이름으로 다시 온다"""

    def leader_client(self):
        client = APIClient()
        client.force_authenticate(user=self.leader)
        return client

    def test_rename_via_api_resends_that_ensembles_scores(self):
        self.score(self.leader, 'Moldau', self.ensemble)
        self.score(self.me, 'Mine')                      # 다른 악보는 다시 오지 않는다
        first = self.sync()

        response = self.leader_client().patch(f'/api/v1/ensembles/{self.ensemble.pk}/',
                                              {'name': 'Guitar Quartet'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Guitar Quartet')

        second = self.sync(first['cursor'])
        self.assertEqual(self.titles(second), ['Moldau'])
        self.assertEqual(second['scores'][0]['ensemble']['name'], 'Guitar Quartet')

    def test_rename_via_web_resends_too(self):
        self.score(self.leader, 'Moldau', self.ensemble)
        first = self.sync()
        web = Client()
        web.force_login(self.leader)
        web.post(reverse('web:ensemble_edit', args=[self.ensemble.pk]), {'name': 'Guitar Quartet', 'description': ''})
        self.ensemble.refresh_from_db()
        self.assertEqual(self.ensemble.name, 'Guitar Quartet')
        second = self.sync(first['cursor'])
        self.assertEqual(self.titles(second), ['Moldau'])
        self.assertEqual(second['scores'][0]['ensemble']['name'], 'Guitar Quartet')

    def test_description_only_does_not_resend(self):
        self.score(self.leader, 'Moldau', self.ensemble)
        first = self.sync()
        self.assertEqual(self.leader_client().patch(f'/api/v1/ensembles/{self.ensemble.pk}/', {'description': 'Tue'},
                                                    format='json').status_code, 200)
        web = Client()
        web.force_login(self.leader)
        web.post(reverse('web:ensemble_edit', args=[self.ensemble.pk]), {'name': 'Guitar Ensemble', 'description': 'Wed'})
        self.assertEqual(self.sync(first['cursor'])['scores'], [])

    def test_member_cannot_rename(self):
        client = APIClient()
        client.force_authenticate(user=self.me)
        self.assertEqual(client.patch(f'/api/v1/ensembles/{self.ensemble.pk}/', {'name': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.leader_client().patch(f'/api/v1/ensembles/{self.ensemble.pk}/', {'name': '  '},
                                                    format='json').status_code, 400)
