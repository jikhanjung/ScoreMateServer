"""
S6 — 앙상블 세트리스트(연주회 곡목): 권한 · 넣을 수 있는 곡 · TV 동기화 · 웹
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from ensembles import services as ensemble_services
from ensembles.models import Membership
from setlists.models import Setlist, SetlistItem
from .factories import EnsembleFactory, MembershipFactory, ScoreFactory, UserFactory


class SetlistEnsembleBase(TestCase):

    def setUp(self):
        self.owner = UserFactory(username='owner')
        self.leader = UserFactory(username='leader')
        self.member = UserFactory(username='member')
        self.outsider = UserFactory(username='outsider')
        self.ensemble = EnsembleFactory(name='Guitar Ensemble')
        MembershipFactory(ensemble=self.ensemble, user=self.owner, role=Membership.ROLE_OWNER)
        MembershipFactory(ensemble=self.ensemble, user=self.leader, role=Membership.ROLE_LEADER)
        MembershipFactory(ensemble=self.ensemble, user=self.member, role=Membership.ROLE_MEMBER)
        self.moldau = ScoreFactory(user=self.leader, ensemble=self.ensemble, title='Moldau', pages=10)
        self.gazza = ScoreFactory(user=self.owner, ensemble=self.ensemble, title='La Gazza Ladra', pages=20)
        self.personal = ScoreFactory(user=self.leader, title='Leader practice')
        self.program = Setlist.objects.create(user=self.leader, ensemble=self.ensemble, title='가을 연주회')
        SetlistItem.objects.create(setlist=self.program, score=self.moldau, order_index=1)
        SetlistItem.objects.create(setlist=self.program, score=self.gazza, order_index=2, notes='앙코르')

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client


class SetlistPermissionAPITest(SetlistEnsembleBase):

    def test_members_read_outsiders_404(self):
        response = self.api(self.member).get(f'/api/v1/setlists/{self.program.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i['score']['title'] for i in response.data['items']], ['Moldau', 'La Gazza Ladra'])
        self.assertEqual((response.data['ensemble'], response.data['ensemble_name'], response.data['can_edit']),
                         (self.ensemble.pk, 'Guitar Ensemble', False))
        self.assertIn(self.program.pk, [s['id'] for s in self.api(self.member).get('/api/v1/setlists/').data['results']])
        self.assertEqual(self.api(self.outsider).get(f'/api/v1/setlists/{self.program.pk}/').status_code, 404)

    def test_member_cannot_write(self):
        client = self.api(self.member)
        url = f'/api/v1/setlists/{self.program.pk}/'
        self.assertEqual(client.patch(url, {'title': 'x'}, format='json').status_code, 403)
        self.assertEqual(client.delete(url).status_code, 403)
        self.assertEqual(client.post(url + 'add_item/', {'score_id': self.moldau.pk}, format='json').status_code, 403)
        self.assertEqual(client.post(url + 'reorder_items/', {'items': []}, format='json').status_code, 403)

    def test_owner_edits_leaders_setlist_keeps_creator(self):
        response = self.api(self.owner).patch(f'/api/v1/setlists/{self.program.pk}/', {'title': '가을 연주회 (최종)'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.program.refresh_from_db()
        self.assertEqual((self.program.title, self.program.user), ('가을 연주회 (최종)', self.leader))

    def test_create_ensemble_setlist_by_role(self):
        response = self.api(self.leader).post('/api/v1/setlists/', {'title': '봄', 'ensemble': self.ensemble.pk}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Setlist.objects.get(pk=response.data['id']).ensemble, self.ensemble)
        response = self.api(self.member).post('/api/v1/setlists/', {'title': '봄', 'ensemble': self.ensemble.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.api(self.outsider).post('/api/v1/setlists/', {'title': '봄', 'ensemble': self.ensemble.pk}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_cannot_move_between_ensembles(self):
        other = EnsembleFactory()
        MembershipFactory(ensemble=other, user=self.leader, role=Membership.ROLE_OWNER)
        response = self.api(self.leader).patch(f'/api/v1/setlists/{self.program.pk}/', {'ensemble': other.pk}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_only_ensemble_scores_in_ensemble_setlist(self):
        client = self.api(self.leader)
        response = client.post(f'/api/v1/setlists/{self.program.pk}/add_item/', {'score_id': self.personal.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        response = client.post(f'/api/v1/setlists/{self.program.pk}/add_items/', {'score_ids': [self.personal.pk]}, format='json')
        self.assertEqual(response.status_code, 404)
        # 내 세트리스트에는 남(리더)이 올린 앙상블 악보를 넣지 않는다
        mine = Setlist.objects.create(user=self.member, title='mine')
        response = self.api(self.member).post(f'/api/v1/setlists/{mine.pk}/add_item/', {'score_id': self.moldau.pk}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_unreadable_items_are_hidden(self):
        """악보가 앙상블 밖으로 옮겨지면 멤버에게 그 항목이 보이지 않는다 (제목이 새지 않게)"""
        self.moldau.ensemble = None
        self.moldau.save()
        response = self.api(self.member).get(f'/api/v1/setlists/{self.program.pk}/')
        self.assertEqual([i['score']['title'] for i in response.data['items']], ['La Gazza Ladra'])

    def test_ensemble_delete_removes_its_setlists(self):
        mine = Setlist.objects.create(user=self.owner, title='mine')
        ensemble_services.delete_ensemble(self.ensemble, self.owner)
        self.assertFalse(Setlist.objects.filter(pk=self.program.pk).exists())
        self.assertTrue(Setlist.objects.filter(pk=mine.pk).exists())


class SetlistSyncTest(SetlistEnsembleBase):

    def test_member_gets_ensemble_and_own_setlists(self):
        mine = Setlist.objects.create(user=self.member, title='내 연습')
        SetlistItem.objects.create(setlist=mine, score=ScoreFactory(user=self.member, title='Etude'), order_index=5)
        Setlist.objects.create(user=self.outsider, title='남의 것')
        data = self.api(self.member).get('/api/v1/sync/setlists/').data['setlists']
        by_title = {s['title']: s for s in data}
        self.assertEqual(set(by_title), {'가을 연주회', '내 연습'})
        program = by_title['가을 연주회']
        self.assertEqual(program['ensemble'], {'id': self.ensemble.pk, 'name': 'Guitar Ensemble'})
        self.assertEqual([(i['score_id'], i['position'], i['notes']) for i in program['items']],
                         [(self.moldau.pk, 1, ''), (self.gazza.pk, 2, '앙코르')])
        self.assertEqual(by_title['내 연습']['items'][0]['position'], 1)   # order_index 가 아니라 1부터

    def test_unreadable_items_dropped_and_outsider_empty(self):
        self.moldau.ensemble = None
        self.moldau.save()
        data = self.api(self.member).get('/api/v1/sync/setlists/').data['setlists']
        self.assertEqual([i['score_id'] for i in data[0]['items']], [self.gazza.pk])
        self.assertEqual(self.api(self.outsider).get('/api/v1/sync/setlists/').data['setlists'], [])


class SetlistWebTest(SetlistEnsembleBase):

    def test_member_sees_but_cannot_edit(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('web:setlist_detail', args=[self.program.pk]))
        self.assertContains(response, 'Moldau')
        self.assertContains(response, '앙코르')
        self.assertNotContains(response, '곡 넣기')
        item = self.program.items.first()
        self.assertEqual(self.client.post(reverse('web:setlist_item', args=[self.program.pk, item.pk]),
                                          {'action': 'remove'}).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('web:setlist_detail', args=[self.program.pk])).status_code, 404)

    def test_leader_builds_program(self):
        self.client.force_login(self.leader)
        response = self.client.post(reverse('web:setlists'), {'title': '봄 연주회', 'ensemble': self.ensemble.pk})
        setlist = Setlist.objects.get(title='봄 연주회')
        self.assertRedirects(response, reverse('web:setlist_detail', args=[setlist.pk]))
        self.assertEqual(setlist.ensemble, self.ensemble)

        page = self.client.get(reverse('web:setlist_detail', args=[setlist.pk]))
        self.assertContains(page, 'Moldau')
        self.assertNotContains(page, 'Leader practice')          # 개인 악보는 후보가 아니다
        self.client.post(reverse('web:setlist_add', args=[setlist.pk]),
                         {'score': [self.moldau.pk, self.gazza.pk, self.personal.pk]})
        items = list(setlist.items.order_by('order_index'))
        self.assertEqual([i.score for i in items], [self.moldau, self.gazza])

        self.client.post(reverse('web:setlist_item', args=[setlist.pk, items[1].pk]), {'action': 'up'})
        self.assertEqual([i.score for i in setlist.items.order_by('order_index')], [self.gazza, self.moldau])
        self.client.post(reverse('web:setlist_item', args=[setlist.pk, items[0].pk]), {'action': 'notes', 'notes': '2절 없이'})
        self.assertEqual(SetlistItem.objects.get(pk=items[0].pk).notes, '2절 없이')
        self.client.post(reverse('web:setlist_item', args=[setlist.pk, items[1].pk]), {'action': 'remove'})
        self.assertEqual([(i.score, i.order_index) for i in setlist.items.all()], [(self.moldau, 1)])

        response = self.client.post(reverse('web:setlist_delete', args=[setlist.pk]))
        self.assertRedirects(response, reverse('web:ensemble_detail', args=[self.ensemble.pk]))
        self.assertTrue(type(self.moldau).objects.filter(pk=self.moldau.pk).exists())   # 악보는 그대로

    def test_member_cannot_create_ensemble_setlist_on_web(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('web:setlists'), {'title': 'x', 'ensemble': self.ensemble.pk})
        self.assertEqual(response.status_code, 200)   # 폼 오류 — 선택지에 없다
        self.assertFalse(Setlist.objects.filter(title='x').exists())

    def test_ensemble_page_lists_programs(self):
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse('web:ensemble_detail', args=[self.ensemble.pk])), '가을 연주회')
