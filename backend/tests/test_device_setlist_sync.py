"""
TV 마다 받을 것 — 고른 세트리스트의 곡만(기본) / 모든 악보. 고르는 곳은 웹(서버)뿐, TV 는 API 로 보기만
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from devices import services as device_services
from devices.models import Device, DeviceSetlist
from scores.models import Score
from setlists.models import Setlist, SetlistItem
from .factories import ScoreFactory, UserFactory


@override_settings(SYNC_LAG_SECONDS=0)
class DeviceSetlistSyncTest(TestCase):

    def setUp(self):
        self.user = UserFactory(username='jikhan')
        self.old = timezone.now() - timedelta(days=30)
        self.moldau, self.gazza, self.etude = (ScoreFactory(user=self.user, title=t) for t in ('Moldau', 'Gazza', 'Etude'))
        Score.objects.update(updated_at=self.old)                   # 모두 옛 악보
        self.concert = Setlist.objects.create(user=self.user, title='가을 연주회')
        SetlistItem.objects.create(setlist=self.concert, score=self.moldau, order_index=1)
        SetlistItem.objects.create(setlist=self.concert, score=self.gazza, order_index=2)
        SetlistItem.objects.filter(setlist=self.concert).update(created_at=self.old)
        self.practice = Setlist.objects.create(user=self.user, title='연습')
        self.tv, self.device = self.link()

    def link(self, **approve):
        authorization, _ = device_services.start_authorization('TV')
        device = device_services.approve(authorization, self.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {device_services.issue_tokens(device)['access_token']}")
        return client, device

    def sync(self, cursor=None, client=None):
        params = {'cursor': cursor} if cursor else {}
        return (client or self.tv).get('/api/v1/sync/scores/', params).data

    def choose(self, *setlists, mode=Device.SYNC_SETLISTS):
        device_services.set_sync(self.device, mode, [s.pk for s in setlists])
        DeviceSetlist.objects.filter(device=self.device).update(added_at=self.old)   # 고른 지 오래됐다고 치고

    def test_new_device_defaults_to_selected_setlists_and_gets_nothing(self):
        self.assertEqual(self.device.sync_mode, Device.SYNC_SETLISTS)
        data = self.sync()
        self.assertEqual((data['scores'], data['ids']), ([], []))
        self.assertEqual(self.tv.get('/api/v1/sync/setlists/').data['setlists'], [])

    def test_only_scores_of_chosen_setlists(self):
        self.choose(self.concert)
        data = self.sync()
        self.assertEqual(sorted(s['title'] for s in data['scores']), ['Gazza', 'Moldau'])
        self.assertEqual(data['ids'], sorted([self.moldau.pk, self.gazza.pk]))
        self.assertEqual([s['title'] for s in self.tv.get('/api/v1/sync/setlists/').data['setlists']], ['가을 연주회'])

    def test_adding_to_setlist_or_choosing_one_brings_old_scores(self):
        self.choose(self.concert)
        cursor = self.sync()['cursor']
        # 곡목에 옛 악보를 넣으면 — 악보 updated_at 은 커서보다 옛날이지만 온다
        # (커서와 같은 시각이면 id 동률 규칙으로 우연히 통과하므로 확실히 더 옛날로)
        Score.objects.filter(pk=self.etude.pk).update(updated_at=self.old - timedelta(days=1))
        SetlistItem.objects.create(setlist=self.concert, score=self.etude, order_index=3)
        data = self.sync(cursor)
        self.assertEqual([s['title'] for s in data['scores']], ['Etude'])
        cursor = data['cursor']
        # 다른 곡목을 새로 고르면 그 곡들이 온다
        other = ScoreFactory(user=self.user, title='Arpeggione')
        Score.objects.filter(pk=other.pk).update(updated_at=self.old - timedelta(days=1))
        SetlistItem.objects.create(setlist=self.practice, score=other)
        SetlistItem.objects.filter(setlist=self.practice).update(created_at=self.old - timedelta(days=1))
        device_services.toggle_setlist(self.device, self.practice, True)
        data = self.sync(cursor)
        self.assertEqual([s['title'] for s in data['scores']], ['Arpeggione'])

    def test_removing_or_unchoosing_drops_from_ids(self):
        self.choose(self.concert)
        cursor = self.sync()['cursor']
        SetlistItem.objects.filter(setlist=self.concert, score=self.gazza).delete()
        self.assertEqual(self.sync(cursor)['ids'], [self.moldau.pk])
        device_services.toggle_setlist(self.device, self.concert, False)
        self.assertEqual(self.sync(cursor)['ids'], [])
        self.assertTrue(Score.objects.filter(pk=self.moldau.pk).exists())   # 악보는 그대로 — TV 에서만 정리

    def test_other_devices_choice_does_not_leak(self):
        """다른 TV 가 나중에 고른 시각이 이 TV 의 기준 시각에 섞이지 않는다"""
        self.choose(self.concert)
        cursor = self.sync()['cursor']
        other_tv, other_device = self.link()
        device_services.set_sync(other_device, Device.SYNC_SETLISTS, [self.concert.pk])   # 방금 고름
        self.assertEqual(self.sync(cursor)['scores'], [])
        self.assertEqual(len(self.sync(client=other_tv)['scores']), 2)

    def test_all_mode(self):
        self.choose(mode=Device.SYNC_ALL)
        self.assertEqual(len(self.sync()['ids']), 3)
        self.assertEqual(len(self.tv.get('/api/v1/sync/setlists/').data['setlists']), 2)

    def test_web_user_token_still_sees_everything(self):
        web = APIClient()
        web.force_authenticate(user=self.user)
        self.assertEqual(len(web.get('/api/v1/sync/scores/').data['ids']), 3)

    def test_choice_is_read_only_via_api(self):
        me = self.tv.get('/api/v1/devices/me/').data
        self.assertEqual((me['sync_mode'], me['sync_setlists']), ('setlists', []))
        self.tv.patch(f'/api/v1/devices/{self.device.pk}/', {'sync_mode': 'all', 'sync_setlists': [self.concert.pk]},
                      format='json')
        self.device.refresh_from_db()
        self.assertEqual((self.device.sync_mode, self.device.setlist_links.count()), ('setlists', 0))

    def test_web_choices(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse('web:devices'))
        self.assertContains(page, '고른 세트리스트의 곡만')
        self.client.post(reverse('web:device_sync', args=[self.device.pk]),
                         {'sync_mode': 'setlists', 'setlists': [self.concert.pk, self.practice.pk]})
        self.assertEqual(set(self.device.setlist_links.values_list('setlist_id', flat=True)), {self.concert.pk, self.practice.pk})
        # 세트리스트 화면의 '보낼 TV'
        self.assertContains(self.client.get(reverse('web:setlist_detail', args=[self.concert.pk])), '보낼 TV')
        self.client.post(reverse('web:setlist_devices', args=[self.concert.pk]), {})
        self.assertEqual(list(self.device.setlist_links.values_list('setlist_id', flat=True)), [self.practice.pk])
        self.client.post(reverse('web:device_sync', args=[self.device.pk]), {'sync_mode': 'all'})
        self.device.refresh_from_db()
        self.assertEqual(self.device.sync_mode, 'all')
        # 남의 세트리스트는 고를 수 없다
        other = Setlist.objects.create(user=UserFactory(), title='남의 것')
        self.client.post(reverse('web:device_sync', args=[self.device.pk]), {'sync_mode': 'setlists', 'setlists': [other.pk]})
        self.assertFalse(self.device.setlist_links.filter(setlist=other).exists())

    def test_activate_with_choice(self):
        codes_client = APIClient()
        codes = codes_client.post('/api/v1/device/code', {'name': '합주실 TV'}, format='json').data
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('web:activate'), {'code': codes['user_code']}), '가을 연주회')
        self.client.post(reverse('web:activate'), {'code': codes['user_code'], 'decision': 'approve',
                                                   'sync_mode': 'setlists', 'setlists': [self.concert.pk]})
        device = Device.objects.get(name='합주실 TV')
        self.assertEqual(list(device.setlist_links.values_list('setlist_id', flat=True)), [self.concert.pk])
