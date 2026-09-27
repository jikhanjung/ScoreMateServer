"""
GET /api/v1/sync/scores?cursor=&limit=  — TV 동기화 (scores/sync.py 에 규칙)
"""
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.models import Device
from .serializers import SyncScoreSerializer
from .sync import BadCursor, changes


class ScoreSyncView(APIView):
    permission_classes = [IsAuthenticated]

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
