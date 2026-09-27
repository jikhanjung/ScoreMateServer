"""
S2 — 악보 판(ScoreVersion): 새 판 · 되돌리기 · 판 지우기 · 쿼터 · 파일 · API · 웹 · 데이터 마이그레이션 (devlog 054 §2)
"""
import hashlib
import shutil
import tempfile
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from ensembles.models import Membership
from files.utils import LocalStorageHandler, generate_upload_s3_key, load_blob_token
from scores.models import Score, ScoreVersion
from scores.services import VersionError, add_version, create_score, delete_score, delete_version, make_current
from .factories import EnsembleFactory, MembershipFactory, UserFactory

PDF = (Path(__file__).parent / 'LaGazzaLadra.pdf').read_bytes()
MB = 1024 * 1024


class VersionTestBase(TestCase):

    def setUp(self):
        self.files_root = Path(tempfile.mkdtemp(prefix='scoremate-versions-'))
        self.addCleanup(shutil.rmtree, self.files_root, ignore_errors=True)
        overrides = override_settings(STORAGE_BACKEND='local', FILES_ROOT=self.files_root, FILES_X_ACCEL_PREFIX='')
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.storage = LocalStorageHandler()

        self.owner = UserFactory(username='owner', total_quota_mb=1000)
        self.leader = UserFactory(username='leader', total_quota_mb=1000)
        self.member = UserFactory(username='member')
        self.outsider = UserFactory(username='outsider')
        self.ensemble = EnsembleFactory()
        MembershipFactory(ensemble=self.ensemble, user=self.owner, role=Membership.ROLE_OWNER)
        MembershipFactory(ensemble=self.ensemble, user=self.leader, role=Membership.ROLE_LEADER)
        MembershipFactory(ensemble=self.ensemble, user=self.member, role=Membership.ROLE_MEMBER)
        self.score = self.upload_score(self.leader, 'Moldau')

    def put_file(self, user, data=PDF, name='x.pdf'):
        key = generate_upload_s3_key(user.id, name)
        self.storage.write_bytes(key, data)
        return key

    def upload_score(self, user, title, size_mb=3):
        key = self.put_file(user)
        return create_score(user=user, s3_key=key, size_bytes=size_mb * MB, title=title, ensemble=self.ensemble,
                            original_filename=f'{title}.pdf')

    def new_version(self, user, size_mb=2, note='42쪽까지'):
        key = self.put_file(user, name='v.pdf')
        return add_version(self.score, user=user, s3_key=key, size_bytes=size_mb * MB, original_filename='Moldau_0829.pdf',
                           note=note)

    def reload(self, *objs):
        for obj in objs:
            obj.refresh_from_db()


class VersionServiceTest(VersionTestBase):

    def test_new_score_starts_at_version_1(self):
        v1 = self.score.current_version
        self.assertEqual((v1.number, v1.uploaded_by, v1.s3_key), (1, self.leader, self.score.s3_key))
        self.assertEqual(Score.objects.get(pk=self.score.pk).last_version_number, 1)
        self.assertEqual(self.score.versions.count(), 1)
        # 처리 작업이 판에도 쪽수 · 해시를 채웠다
        v1.refresh_from_db()
        self.assertGreater(v1.pages or 0, 0)
        self.assertEqual(v1.content_hash, hashlib.sha256(PDF).hexdigest())

    def test_factory_scores_also_get_version_1(self):
        score = Score.objects.create(user=self.member, title='x', s3_key='1/scores/9/original.pdf', size_bytes=10)
        self.assertEqual(score.current_version.number, 1)
        self.assertEqual(ScoreVersion.objects.filter(score=score).count(), 1)

    def test_add_version_becomes_current_and_charges_uploader(self):
        self.reload(self.score)
        before_updated = self.score.updated_at
        self.reload(self.owner)
        owner_used = self.owner.used_quota_mb

        v2 = self.new_version(self.owner, size_mb=2)
        self.reload(self.score, self.owner, self.leader)
        self.assertEqual(v2.number, 2)
        self.assertEqual(self.score.current_version, v2)
        self.assertEqual((self.score.s3_key, self.score.original_filename, self.score.size_bytes),
                         (v2.s3_key, 'Moldau_0829.pdf', 2 * MB))
        self.assertGreater(self.score.pages or 0, 0)              # 새 판도 처리됐다
        self.assertGreater(self.score.updated_at, before_updated)  # 동기화가 알아챈다
        self.assertEqual(self.owner.used_quota_mb, owner_used + 2)  # 이 판을 올린 사람
        self.assertEqual(self.score.user, self.leader)             # 악보를 올린 사람은 그대로

    def test_make_current_goes_back_without_deleting(self):
        v1 = self.score.current_version
        v2 = self.new_version(self.owner)
        make_current(self.score, v1)
        self.reload(self.score)
        self.assertEqual(self.score.current_version, v1)
        self.assertEqual(self.score.s3_key, v1.s3_key)
        self.assertEqual(self.score.versions.count(), 2)
        self.assertTrue(self.storage.check_file_exists(v2.s3_key))

    def test_delete_current_falls_back_to_latest_remaining(self):
        v1 = self.score.current_version
        v2 = self.new_version(self.owner, size_mb=2)
        v3 = self.new_version(self.leader, size_mb=4)
        self.reload(self.owner, self.leader)
        owner_used, leader_used = self.owner.used_quota_mb, self.leader.used_quota_mb

        delete_version(self.score, v3)
        self.reload(self.score, self.leader)
        self.assertEqual(self.score.current_version, v2)
        self.assertEqual(self.score.s3_key, v2.s3_key)
        self.assertEqual(self.leader.used_quota_mb, leader_used - 4)
        self.assertFalse(self.storage.check_file_exists(v3.s3_key))

        # 지금 쓰는 판이 아닌 것을 지우면 지금 판은 그대로
        delete_version(self.score, v1)
        self.reload(self.score)
        self.assertEqual(self.score.current_version, v2)
        self.assertEqual(list(self.score.versions.values_list('number', flat=True)), [2])

        # 하나뿐이면 못 지운다
        with self.assertRaises(VersionError):
            delete_version(self.score, v2)
        self.reload(self.owner)
        self.assertEqual(self.owner.used_quota_mb, owner_used)

    def test_numbers_are_never_reused(self):
        v2 = self.new_version(self.owner)
        delete_version(self.score, v2)
        self.assertEqual(self.new_version(self.owner).number, 3)

    def test_version_of_other_score_rejected(self):
        other = self.upload_score(self.leader, 'Other')
        with self.assertRaises(VersionError):
            make_current(self.score, other.current_version)
        with self.assertRaises(VersionError):
            delete_version(self.score, other.current_version)

    def test_delete_score_refunds_every_uploader_and_removes_files(self):
        v2 = self.new_version(self.owner, size_mb=2)
        self.reload(self.owner, self.leader)
        owner_used, leader_used = self.owner.used_quota_mb, self.leader.used_quota_mb
        keys = [self.score.current_version.s3_key, v2.s3_key] + list(self.score.versions.values_list('s3_key', flat=True))
        self.reload(self.score)
        thumb = self.score.thumbnail_key

        delete_score(self.score)
        self.reload(self.owner, self.leader)
        self.assertEqual(self.owner.used_quota_mb, owner_used - 2)
        self.assertEqual(self.leader.used_quota_mb, leader_used - 3)
        for key in set(keys) | {thumb}:
            self.assertFalse(self.storage.check_file_exists(key), key)
        self.assertFalse(ScoreVersion.objects.filter(score_id=self.score.pk).exists())


class VersionAPITest(VersionTestBase):

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def upload_new_version(self, user, note='도돌이 풀기'):
        client = self.api(user)
        up = client.post('/api/v1/files/upload-url/', {'filename': 'Moldau_v2.pdf', 'size_bytes': len(PDF),
                                                       'mime_type': 'application/pdf'}, format='json')
        self.assertEqual(up.status_code, 201)
        put = client.generic('PUT', up.data['upload_url'], PDF, content_type='application/pdf')
        self.assertEqual(put.status_code, 201)
        return client.post(f'/api/v1/scores/{self.score.pk}/versions/', {'upload_id': up.data['upload_id'], 'note': note},
                           format='json')

    def test_list_versions(self):
        self.new_version(self.owner)
        response = self.api(self.member).get(f'/api/v1/scores/{self.score.pk}/versions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([v['number'] for v in response.data], [2, 1])
        self.assertTrue(response.data[0]['is_current'])
        self.assertEqual(response.data[0]['uploaded_by']['id'], self.owner.id)
        self.assertEqual(self.api(self.outsider).get(f'/api/v1/scores/{self.score.pk}/versions/').status_code, 404)

    def test_upload_new_version(self):
        response = self.upload_new_version(self.leader)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['number'], 2)
        self.assertEqual(response.data['note'], '도돌이 풀기')
        self.assertEqual(response.data['original_filename'], 'Moldau_v2.pdf')
        self.assertGreater(response.data['pages'] or 0, 0)

        detail = self.api(self.member).get(f'/api/v1/scores/{self.score.pk}/').data
        self.assertEqual((detail['version'], detail['version_count']), (2, 2))
        listing = self.api(self.member).get('/api/v1/scores/').data['results'][0]
        self.assertEqual((listing['version'], listing['version_count']), (2, 2))

    def test_member_cannot_add_version(self):
        self.assertEqual(self.upload_new_version(self.member).status_code, 403)
        self.assertEqual(self.score.versions.count(), 1)

    def test_make_current_and_delete(self):
        self.new_version(self.owner)
        client = self.api(self.leader)
        response = client.post(f'/api/v1/scores/{self.score.pk}/versions/1/make_current/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['version'], 1)
        self.assertEqual(client.delete(f'/api/v1/scores/{self.score.pk}/versions/2/').status_code, 204)
        response = client.delete(f'/api/v1/scores/{self.score.pk}/versions/1/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('version', response.data['error']['details'])
        self.assertEqual(client.delete(f'/api/v1/scores/{self.score.pk}/versions/9/').status_code, 404)
        self.assertEqual(self.api(self.member).post(f'/api/v1/scores/{self.score.pk}/versions/1/make_current/').status_code, 403)


class VersionWebTest(VersionTestBase):

    def test_detail_shows_versions_and_form_by_role(self):
        self.new_version(self.owner, note='42쪽까지')
        self.client.force_login(self.member)
        response = self.client.get(reverse('web:score_detail', args=[self.score.pk]))
        self.assertContains(response, '판 2')
        self.assertContains(response, '42쪽까지')
        self.assertNotContains(response, '새 판 올리기')
        self.assertNotContains(response, reverse('web:version_delete', args=[self.score.pk, 1]))
        self.client.force_login(self.leader)
        self.assertContains(self.client.get(reverse('web:score_detail', args=[self.score.pk])), '새 판 올리기')

    def test_upload_make_current_delete_via_web(self):
        self.client.force_login(self.leader)
        response = self.client.post(reverse('web:version_upload', args=[self.score.pk]), {
            'file': SimpleUploadedFile('Moldau_0829.pdf', PDF, content_type='application/pdf'), 'note': '42쪽까지'})
        self.assertRedirects(response, reverse('web:score_detail', args=[self.score.pk]) + '#versions')
        self.reload(self.score)
        self.assertEqual(self.score.current_version.number, 2)

        download = self.client.get(reverse('web:version_download', args=[self.score.pk, 1]))
        token = download['Location'].rstrip('/').rsplit('/', 1)[-1]
        self.assertEqual(load_blob_token(token)['fn'], 'Moldau (v1).pdf')

        self.client.post(reverse('web:version_make_current', args=[self.score.pk, 1]))
        self.reload(self.score)
        self.assertEqual(self.score.current_version.number, 1)
        self.client.post(reverse('web:version_delete', args=[self.score.pk, 2]))
        self.assertEqual(list(self.score.versions.values_list('number', flat=True)), [1])
        response = self.client.post(reverse('web:version_delete', args=[self.score.pk, 1]), follow=True)
        self.assertContains(response, '판이 하나뿐이면')

    def test_member_and_outsider_blocked(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('web:version_upload', args=[self.score.pk]), {
            'file': SimpleUploadedFile('a.pdf', PDF, content_type='application/pdf')})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(reverse('web:version_view', args=[self.score.pk, 1])).status_code, 302)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('web:version_view', args=[self.score.pk, 1])).status_code, 404)

    def test_non_pdf_new_version_rejected(self):
        self.client.force_login(self.leader)
        response = self.client.post(reverse('web:version_upload', args=[self.score.pk]), {
            'file': SimpleUploadedFile('a.pdf', b'not a pdf', content_type='application/pdf')}, follow=True)
        self.assertContains(response, 'PDF 파일이 아닙니다')
        self.assertEqual(self.score.versions.count(), 1)


@pytest.mark.django_db(transaction=True)
class BackfillMigrationTest(TransactionTestCase):
    """0003 까지의 악보(판 없음)가 0004 를 지나면 판 1 을 가진다"""

    migrate_from = [('scores', '0003_score_ensemble')]
    migrate_to = [('scores', '0004_score_versions')]

    def test_backfill(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        User = old_apps.get_model('core', 'User')
        Score = old_apps.get_model('scores', 'Score')
        user = User.objects.create(email='old@example.com', username='old', password='x')
        score = Score.objects.create(user=user, title='Old', s3_key='1/scores/1/original.pdf', size_bytes=5 * MB,
                                     pages=12, content_hash='ab' * 32, original_filename='old.pdf')

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        Score = new_apps.get_model('scores', 'Score')
        ScoreVersion = new_apps.get_model('scores', 'ScoreVersion')
        migrated = Score.objects.get(pk=score.pk)
        version = ScoreVersion.objects.get(score_id=score.pk)
        self.assertEqual(migrated.current_version_id, version.pk)
        self.assertEqual((version.number, version.s3_key, version.pages, version.size_bytes, version.uploaded_by_id,
                          version.original_filename), (1, score.s3_key, 12, 5 * MB, user.pk, 'old.pdf'))
        self.assertEqual(version.created_at, migrated.created_at)
        self.assertEqual(migrated.last_version_number, 1)

        # 끝으로 최신까지 되돌려 둔다
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
