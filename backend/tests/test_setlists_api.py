"""
API integration tests for Setlists (current API: order_index, DELETE items/<id>/, reorder_items {items:[{id, order_index}]})
"""
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from setlists.models import Setlist, SetlistItem
from .factories import UserFactory, ScoreFactory


class SetlistAPIIntegrationTest(APITestCase):
    """Integration tests for Setlist API with complex scenarios"""

    def setUp(self):
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.scores = ScoreFactory.create_batch(5, user=self.user1)

        self.setlist = Setlist.objects.create(
            user=self.user1,
            title='Concert Setlist',
            description='Main concert program'
        )
        for i, score in enumerate(self.scores[:3]):
            SetlistItem.objects.create(
                setlist=self.setlist,
                score=score,
                order_index=i + 1,
                notes=f'Notes for position {i + 1}'
            )

        self.client = APIClient()

    def authenticate_user(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_complete_setlist_workflow(self):
        """Create → add items → reorder → remove → duplicate → update"""
        self.authenticate_user(self.user1)

        # 1. Create (response must carry the id — the web client adds items to it right away)
        response = self.client.post('/api/v1/setlists/', {
            'title': 'Evening Concert',
            'description': 'Special evening performance'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        setlist_id = response.data['id']

        # 2. Add items (appended in order)
        for i, score in enumerate(self.scores[:3]):
            response = self.client.post(f'/api/v1/setlists/{setlist_id}/add_item/', {
                'score_id': score.id,
                'notes': f'Performance note {i + 1}'
            })
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data['order_index'], i + 1)

        # 3. Retrieve
        response = self.client.get(f'/api/v1/setlists/{setlist_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 3)
        self.assertEqual(response.data['item_count'], 3)

        # 4. Reorder: third item first
        items = response.data['items']
        response = self.client.post(f'/api/v1/setlists/{setlist_id}/reorder_items/', {
            'items': [
                {'id': items[2]['id'], 'order_index': 1},
                {'id': items[0]['id'], 'order_index': 2},
                {'id': items[1]['id'], 'order_index': 3},
            ]
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f'/api/v1/setlists/{setlist_id}/')
        new_items = response.data['items']
        self.assertEqual(new_items[0]['id'], items[2]['id'])

        # 5. Remove the middle item → remaining items are renumbered
        response = self.client.delete(f'/api/v1/setlists/{setlist_id}/items/{new_items[1]["id"]}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(f'/api/v1/setlists/{setlist_id}/')
        final_items = response.data['items']
        self.assertEqual(len(final_items), 2)
        self.assertEqual([it['order_index'] for it in final_items], [1, 2])

        # 6. Duplicate
        response = self.client.post(f'/api/v1/setlists/{setlist_id}/duplicate/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Evening Concert (Copy)')
        self.assertEqual(response.data['item_count'], 2)

        # 7. Update
        response = self.client.patch(f'/api/v1/setlists/{setlist_id}/', {
            'title': 'Evening Concert - Updated',
            'description': 'Updated description'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Evening Concert - Updated')
        self.assertEqual(response.data['id'], setlist_id)

    def test_setlist_statistics(self):
        self.authenticate_user(self.user1)

        response = self.client.get(f'/api/v1/setlists/{self.setlist.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data['item_count'], 3)
        expected_pages = sum(score.pages or 0 for score in self.scores[:3])
        self.assertEqual(data['total_pages'], expected_pages)

        self.assertEqual(len(data['items']), 3)
        for item in data['items']:
            self.assertIn('score', item)
            self.assertIn('title', item['score'])
            self.assertIn('order_index', item)
            self.assertIn('notes', item)

    def test_setlist_filtering_and_ordering(self):
        self.authenticate_user(self.user1)

        Setlist.objects.create(user=self.user1, title='Old Concert', description='Archived setlist')
        recent_setlist = Setlist.objects.create(user=self.user1, title='Recent Concert', description='New setlist')

        response = self.client.get('/api/v1/setlists/?ordering=-created_at')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], recent_setlist.id)

        response = self.client.get('/api/v1/setlists/?ordering=title')
        titles = [item['title'] for item in response.data['results']]
        self.assertEqual(titles, sorted(titles))

        response = self.client.get('/api/v1/setlists/?search=Concert')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_setlist_pagination(self):
        self.authenticate_user(self.user1)

        for i in range(25):
            Setlist.objects.create(user=self.user1, title=f'Concert {i:02d}', description=f'Concert number {i}')

        response = self.client.get('/api/v1/setlists/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, response.data)
        self.assertEqual(len(response.data['results']), 20)
        self.assertEqual(response.data['count'], 26)

        response = self.client.get('/api/v1/setlists/?page=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 6)

    def test_insert_item_at_position(self):
        """add_item with order_index shifts the following items"""
        self.authenticate_user(self.user1)

        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', {
            'score_id': self.scores[3].id,
            'order_index': 2,
            'notes': 'Inserted piece'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['order_index'], 2)

        response = self.client.get(f'/api/v1/setlists/{self.setlist.id}/')
        items = response.data['items']
        self.assertEqual(len(items), 4)
        self.assertEqual([it['order_index'] for it in items], [1, 2, 3, 4])
        self.assertEqual(items[1]['notes'], 'Inserted piece')

    def test_duplicate_score_rejected(self):
        """The same score cannot appear twice in one setlist"""
        self.authenticate_user(self.user1)

        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', {
            'score_id': self.scores[0].id,
            'notes': 'Encore performance'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.setlist.items.count(), 3)

    def test_error_handling(self):
        self.authenticate_user(self.user1)

        # Non-existent score
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', {'score_id': 99999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('score_id', response.data)

        # Another user's score
        other_score = ScoreFactory(user=self.user2)
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', {'score_id': other_score.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-existent item
        response = self.client.delete(f'/api/v1/setlists/{self.setlist.id}/items/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Reorder with invalid item id
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/reorder_items/', {
            'items': [{'id': 99999, 'order_index': 1}]
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Reorder with malformed payload
        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/reorder_items/', {
            'items': [{'id': self.setlist.items.first().id}]
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Another user's setlist
        self.authenticate_user(self.user2)
        response = self.client.get(f'/api/v1/setlists/{self.setlist.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_setlist_with_many_items(self):
        self.authenticate_user(self.user1)

        scores = ScoreFactory.create_batch(50, user=self.user1)
        large_setlist = Setlist.objects.create(user=self.user1, title='Large Concert')
        for i, score in enumerate(scores):
            SetlistItem.objects.create(setlist=large_setlist, score=score, order_index=i + 1, notes=f'Piece {i + 1}')

        response = self.client.get(f'/api/v1/setlists/{large_setlist.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 50)
        self.assertEqual(response.data['item_count'], 50)
        for item in response.data['items']:
            self.assertIn('id', item['score'])
            self.assertIn('title', item['score'])

    def test_setlist_data_consistency(self):
        self.authenticate_user(self.user1)

        initial_count = self.setlist.item_count
        initial_pages = self.setlist.total_pages

        response = self.client.post(f'/api/v1/setlists/{self.setlist.id}/add_item/', {
            'score_id': self.scores[4].id,
            'notes': 'Additional piece'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.setlist.item_count, initial_count + 1)
        self.assertEqual(self.setlist.total_pages, initial_pages + (self.scores[4].pages or 0))

        response = self.client.delete(f'/api/v1/setlists/{self.setlist.id}/items/{response.data["id"]}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.setlist.item_count, initial_count)
        self.assertEqual(self.setlist.total_pages, initial_pages)
