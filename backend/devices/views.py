"""
TV 기기 연결 API (RFC 8628)

  POST /api/v1/device/code    TV: 코드 받기 (인증 없음)
  POST /api/v1/device/token   TV: 토큰 묻기 (인증 없음) — 오류는 RFC 8628 §3.5 모양 {"error": "..."} 400
  GET  /api/v1/devices/       내 기기 · PATCH {name} · DELETE = 해제
  GET  /api/v1/devices/me/    기기 토큰으로: 이 TV 의 정보
"""
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import services
from .auth import PerDeviceScopedRateThrottle
from .models import Device, DeviceAuthorization
from .serializers import DeviceCodeRequestSerializer, DeviceSerializer, HeartbeatSerializer

DEVICE_CODE_GRANT = 'urn:ietf:params:oauth:grant-type:device_code'


class DeviceCodeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'device_code'

    def post(self, request):
        serializer = DeviceCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        authorization, device_code = services.start_authorization(
            name=data.get('name', ''), model=data.get('model', ''), app_version=data.get('app_version', ''))
        verification_uri = request.build_absolute_uri(reverse('web:activate'))
        return Response({
            'device_code': device_code,
            'user_code': authorization.display_code,
            'verification_uri': verification_uri,
            'verification_uri_complete': f'{verification_uri}?code={authorization.display_code}',
            'expires_in': DeviceAuthorization.EXPIRES_IN,
            'interval': authorization.interval,
        })


class DeviceTokenView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'device_token'   # 5초마다 묻는다 — 익명 기본 제한(100/시간)과 따로

    def post(self, request):
        grant_type = request.data.get('grant_type')
        if grant_type and grant_type != DEVICE_CODE_GRANT:
            return Response({'error': 'unsupported_grant_type'}, status=status.HTTP_400_BAD_REQUEST)
        error, tokens = services.poll(request.data.get('device_code', ''))
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        response = Response(tokens)
        response['Cache-Control'] = 'no-store'
        return response


class DeviceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """기기는 여기서 만들지 않는다 — /device/code · /activate 로만 생긴다"""
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ['get', 'patch', 'delete', 'post']   # post 는 me/heartbeat 뿐
    throttle_scope = None   # heartbeat 만 'sync'(기기마다)

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        services.rename(serializer.instance, serializer.validated_data.get('name', ''))

    def destroy(self, request, *args, **kwargs):
        """해제 — 기록은 남기고(마지막 접속 등) 토큰만 막는다"""
        services.revoke(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _this_device(self, request):
        device_id = getattr(request.user, 'device_id', None)
        if not device_id:
            raise NotFound('Not a device token.')
        return get_object_or_404(Device, pk=device_id, user=request.user)

    @action(detail=False, methods=['get'])
    def me(self, request):
        return Response(self.get_serializer(self._this_device(request)).data)

    @action(detail=False, methods=['post'], url_path='me/heartbeat',
            throttle_classes=[PerDeviceScopedRateThrottle], throttle_scope='sync')
    def heartbeat(self, request):
        """TV 가 앱을 켤 때 · 업데이트 뒤: 앱 버전 · 모델을 알린다 (마지막 접속은 인증이 이미 남긴다)"""
        device = self._this_device(request)
        serializer = HeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = []
        for name in ('app_version', 'model'):
            value = serializer.validated_data.get(name)
            if value:
                setattr(device, name, value.strip())
                fields.append(name)
        device.last_seen_at = timezone.now()
        device.save(update_fields=fields + ['last_seen_at'])
        return Response(self.get_serializer(device).data)
