"""
SQLite 전환(054)으로 바꾼 부분 — 태그 필터 · 검색 · 태그 통계가 Postgres 전용 기능 없이 같게 동작하는지.
"""
import pytest

from scores.filters import ScoreFilter
from scores.models import Score
from .factories import ScoreFactory, UserFactory


def _filter(**params):
    return set(ScoreFilter(params, queryset=Score.objects.all()).qs.values_list('title', flat=True))


@pytest.mark.django_db
class TestTagFilter:
    def test_태그_하나(self):
        ScoreFactory(title='몰다우', tags=['오케스트라', '6/8'])
        ScoreFactory(title='달빛', tags=['기타'])
        assert _filter(tags='기타') == {'달빛'}

    def test_여러_태그는_모두_가진_것만(self):
        ScoreFactory(title='A', tags=['기타', '2중주'])
        ScoreFactory(title='B', tags=['기타'])
        assert _filter(tags='기타, 2중주') == {'A'}

    def test_다른_태그의_일부와_섞이지_않는다(self):
        # "기타" 로 찾을 때 "기타리스트" 태그만 가진 악보는 나오면 안 된다
        ScoreFactory(title='A', tags=['기타리스트'])
        ScoreFactory(title='B', tags=['기타'])
        assert _filter(tags='기타') == {'B'}

    def test_태그_유무(self):
        ScoreFactory(title='있음', tags=['x'])
        ScoreFactory(title='없음', tags=[])
        assert _filter(has_tags=True) == {'있음'}
        assert _filter(has_tags=False) == {'없음'}


@pytest.mark.django_db
class TestSearch:
    def test_제목_작곡가_편성_어디든(self):
        ScoreFactory(title='Clair de Lune', composer='Debussy', instrumentation='Guitar duo')
        ScoreFactory(title='Vltava', composer='Smetana', instrumentation='Orchestra')
        assert _filter(search='debussy') == {'Clair de Lune'}
        assert _filter(search='guitar') == {'Clair de Lune'}
        assert _filter(search='vltava') == {'Vltava'}

    def test_단어마다_모두_맞아야(self):
        ScoreFactory(title='Clair de Lune', composer='Debussy', instrumentation='Guitar duo')
        ScoreFactory(title='Arabesque', composer='Debussy', instrumentation='Piano')
        assert _filter(search='debussy guitar') == {'Clair de Lune'}

    def test_한글(self):
        ScoreFactory(title='블타바', composer='스메타나', instrumentation='관현악')
        assert _filter(search='스메타나') == {'블타바'}


@pytest.mark.django_db
def test_태그_통계(client):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    user = UserFactory()
    ScoreFactory(user=user, tags=['기타', '2중주'])
    ScoreFactory(user=user, tags=['기타'])
    ScoreFactory(user=user, tags=[])
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    response = api.get('/api/v1/scores/statistics/')
    assert response.status_code == 200
    body = response.json()
    text = str(body)
    assert '기타' in text and '2중주' in text
