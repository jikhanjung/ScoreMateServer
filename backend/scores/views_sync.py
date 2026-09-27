"""
GET /api/v1/sync/scores?cursor=&limit=  — TV 동기화 (scores/sync.py 에 규칙)
"""
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.auth import PerDeviceScopedRateThrottle
from devices.models import Device
from .serializers import SyncScoreSerializer
from .sync import BadCursor, changes


class ScoreSyncView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PerDeviceScopedRateThrottle]
    throttle_scope = 'sync'

    def get(self, request):
        limit = request.query_params.get('limit')
        if limit is not None:
            if not limit.isdigit() or not 1 <= int(limit) <= settings.SYNC_PAGE_SIZE:
                raise ValidationError({'limit': f'1..{settings.SYNC_PAGE_SIZE}'})
            limit = int(limit)
        try:
            result = changes(request.user, cursor=request.query_params.get('cursor') or None, limit=limit)
        except BadCursor:
            raise ValidationError({'cursor': 'Invalid cursor. Start over without one.'})

        # 기기 토큰이면 "마지막 동기화"를 남긴다 (웹 TV 목록에 보인다)
        device_id = getattr(request.user, 'device_id', None)
        if device_id:
            Device.objects.filter(pk=device_id).update(last_synced_at=timezone.now())

        response = Response({
            'cursor': result['cursor'],
            'has_more': result['has_more'],
            'scores': SyncScoreSerializer(result['scores'], many=True, context={'request': request}).data,
            'ids': result['ids'],
        })
        response['Cache-Control'] = 'no-store'
        return response


class SetlistSyncView(APIView):
    """GET /api/v1/sync/setlists/ — 볼 수 있는 세트리스트 전부(개수가 적다 — 커서 없이 통째로, TV 는 바꿔 끼운다)

    항목은 곡 순서대로 score_id 만 — 악보 자체는 /sync/scores 로 받는다. 읽을 수 없게 된 악보의 항목은 빠진다.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PerDeviceScopedRateThrottle]
    throttle_scope = 'sync'

    def get(self, request):
        from setlists.models import Setlist
        from .models import Score

        setlists = list(Setlist.objects.readable_by(request.user).select_related('ensemble')
                        .prefetch_related('items').order_by('id'))
        readable = set(Score.objects.readable_by(request.user).values_list('id', flat=True))
        payload = []
        for setlist in setlists:
            items = sorted(setlist.items.all(), key=lambda i: (i.order_index or 0, i.id))
            payload.append({
                'id': setlist.id,
                'title': setlist.title,
                'description': setlist.description,
                'ensemble': {'id': setlist.ensemble_id, 'name': setlist.ensemble.name} if setlist.ensemble_id else None,
                'updated_at': setlist.updated_at,
                'items': [{'score_id': i.score_id, 'position': n, 'notes': i.notes}
                          for n, i in enumerate((i for i in items if i.score_id in readable), start=1)],
            })
        response = Response({'setlists': payload})
        response['Cache-Control'] = 'no-store'
        return response
