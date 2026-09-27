"""
Views for ensembles app

멤버가 아닌 사람에게 앙상블은 없는 것과 같다 (404).
"""
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from . import services
from .models import Ensemble, Membership, Invite
from .serializers import (
    EnsembleSerializer,
    EnsembleDetailSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    InviteSerializer,
    InvitePreviewSerializer,
    JoinSerializer,
)


class EnsembleViewSet(viewsets.ModelViewSet):
    """
    /ensembles/                          내가 멤버인 앙상블 · 만들기(만든 사람이 owner)
    /ensembles/{id}/                     상세(멤버 포함) · 수정(owner · leader) · 삭제(owner)
    /ensembles/{id}/members/             멤버 목록
    /ensembles/{id}/members/{user_id}/   역할(owner) · 파트(owner · leader · 본인) 변경, 내보내기 · 나가기
    /ensembles/{id}/invites/             초대 목록 · 만들기 (owner · leader)
    /ensembles/{id}/invites/{invite_id}/ 초대 취소 (owner · leader)
    /ensembles/invite/{code}/            초대 미리 보기 (로그인한 누구나)
    /ensembles/join/                     초대 코드로 가입
    """
    permission_classes = [IsAuthenticated]
    pagination_class = None  # 한 사람이 속한 앙상블은 많지 않다

    def get_queryset(self):
        return Ensemble.objects.filter(memberships__user=self.request.user).prefetch_related('memberships__user')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EnsembleDetailSerializer
        return EnsembleSerializer

    def get_throttles(self):
        if self.action in ('join', 'invite_preview'):
            self.throttle_scope = 'invite'
            return [ScopedRateThrottle()]
        return super().get_throttles()

    # --- 앙상블 (규칙은 ensembles/services.py — 웹과 같다) ---

    @staticmethod
    def _rule(exc):
        return ValidationError({exc.field: exc.message})

    def perform_create(self, serializer):
        try:
            ensemble = services.create_ensemble(
                self.request.user, serializer.validated_data['name'], serializer.validated_data.get('description', ''))
        except services.RuleError as exc:
            raise self._rule(exc)
        serializer.instance = ensemble

    def perform_update(self, serializer):
        services.require_manager(serializer.instance, self.request.user, 'Only owners and leaders can edit the ensemble.')
        serializer.save()

    def perform_destroy(self, instance):
        services.delete_ensemble(instance, self.request.user)

    # --- 멤버 ---

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        ensemble = self.get_object()
        return Response(MembershipSerializer(ensemble.memberships.select_related('user'), many=True).data)

    @action(detail=True, methods=['patch', 'delete'], url_path=r'members/(?P<user_id>\d+)')
    def member(self, request, pk=None, user_id=None):
        ensemble = self.get_object()
        target = get_object_or_404(Membership, ensemble=ensemble, user_id=user_id)
        try:
            if request.method == 'DELETE':
                services.remove_member(ensemble, request.user, target)
                return Response(status=status.HTTP_204_NO_CONTENT)
            serializer = MembershipUpdateSerializer(target, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            services.update_member(ensemble, request.user, target,
                                   role=serializer.validated_data.get('role'),
                                   part=serializer.validated_data.get('part'))
        except services.RuleError as exc:
            raise self._rule(exc)
        return Response(MembershipSerializer(target).data)

    # --- 초대 ---

    @action(detail=True, methods=['get', 'post'])
    def invites(self, request, pk=None):
        ensemble = self.get_object()
        services.require_manager(ensemble, request.user, 'Only owners and leaders can manage invites.')
        if request.method == 'GET':
            return Response(InviteSerializer(ensemble.invites.all(), many=True).data)

        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        days = data['expires_in_days'] if 'expires_in_days' in data else Invite.DEFAULT_EXPIRY_DAYS
        invite = services.create_invite(ensemble, request.user, expires_in_days=days, max_uses=data.get('max_uses'))
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'invites/(?P<invite_id>\d+)')
    def revoke_invite(self, request, pk=None, invite_id=None):
        ensemble = self.get_object()
        services.require_manager(ensemble, request.user, 'Only owners and leaders can manage invites.')
        invite = get_object_or_404(Invite, ensemble=ensemble, pk=invite_id)
        services.revoke_invite(ensemble, request.user, invite)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path=r'invite/(?P<code>[A-Za-z0-9-]+)')
    def invite_preview(self, request, code=None):
        try:
            invite = services.find_usable_invite(code)
        except services.RuleError as exc:
            raise self._rule(exc)
        return Response(InvitePreviewSerializer(invite).data)

    @action(detail=False, methods=['post'])
    def join(self, request):
        serializer = JoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ensemble, created = services.join(request.user, serializer.validated_data['code'])
        except services.RuleError as exc:
            raise self._rule(exc)
        data = EnsembleSerializer(ensemble, context={'request': request}).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
