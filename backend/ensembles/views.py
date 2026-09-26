"""
Views for ensembles app

멤버가 아닌 사람에게 앙상블은 없는 것과 같다 (404).
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

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

User = get_user_model()


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

    # --- 앙상블 ---

    def perform_create(self, serializer):
        with transaction.atomic():
            ensemble = serializer.save(created_by=self.request.user)
            Membership.objects.create(ensemble=ensemble, user=self.request.user, role=Membership.ROLE_OWNER)

    def perform_update(self, serializer):
        if not serializer.instance.can_manage(self.request.user):
            raise PermissionDenied('Only owners and leaders can edit the ensemble.')
        serializer.save()

    def perform_destroy(self, instance):
        # 악보는 지우지 않는다 — Score.ensemble 이 SET_NULL 이라 올린 사람의 개인 악보로 돌아간다
        if not instance.is_owner(self.request.user):
            raise PermissionDenied('Only owners can delete the ensemble.')
        instance.delete()

    # --- 멤버 ---

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        ensemble = self.get_object()
        return Response(MembershipSerializer(ensemble.memberships.select_related('user'), many=True).data)

    @action(detail=True, methods=['patch', 'delete'], url_path=r'members/(?P<user_id>\d+)')
    def member(self, request, pk=None, user_id=None):
        ensemble = self.get_object()
        target = get_object_or_404(Membership, ensemble=ensemble, user_id=user_id)
        mine = ensemble.membership_of(request.user)

        if request.method == 'DELETE':
            return self._remove_member(ensemble, mine, target)

        serializer = MembershipUpdateSerializer(target, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data.get('role')
        if new_role is not None and new_role != target.role:
            if mine.role != Membership.ROLE_OWNER:
                raise PermissionDenied('Only owners can change roles.')
            if target.role == Membership.ROLE_OWNER:
                self._ensure_another_owner(ensemble, target)
        if 'part' in serializer.validated_data and not (mine.is_manager or mine.pk == target.pk):
            raise PermissionDenied('Only owners, leaders or the member themself can set the part.')
        serializer.save()
        return Response(MembershipSerializer(target).data)

    def _remove_member(self, ensemble, mine, target):
        if mine.pk == target.pk:
            # 나가기
            if target.role == Membership.ROLE_OWNER:
                self._ensure_another_owner(ensemble, target)
        elif mine.role == Membership.ROLE_OWNER:
            pass
        elif mine.role == Membership.ROLE_LEADER and target.role == Membership.ROLE_MEMBER:
            pass
        else:
            raise PermissionDenied('You cannot remove this member.')
        target.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _ensure_another_owner(ensemble, leaving):
        others = ensemble.memberships.filter(role=Membership.ROLE_OWNER).exclude(pk=leaving.pk)
        if not others.exists():
            raise ValidationError({'role': 'An ensemble must keep at least one owner. Make someone else owner first.'})

    # --- 초대 ---

    def _get_managed_ensemble(self):
        ensemble = self.get_object()
        if not ensemble.can_manage(self.request.user):
            raise PermissionDenied('Only owners and leaders can manage invites.')
        return ensemble

    @action(detail=True, methods=['get', 'post'])
    def invites(self, request, pk=None):
        ensemble = self._get_managed_ensemble()
        if request.method == 'GET':
            return Response(InviteSerializer(ensemble.invites.all(), many=True).data)

        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(ensemble=ensemble, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'invites/(?P<invite_id>\d+)')
    def revoke_invite(self, request, pk=None, invite_id=None):
        ensemble = self._get_managed_ensemble()
        invite = get_object_or_404(Invite, ensemble=ensemble, pk=invite_id)
        if invite.revoked_at is None:
            invite.revoked_at = timezone.now()
            invite.save(update_fields=['revoked_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path=r'invite/(?P<code>[A-Za-z0-9-]+)')
    def invite_preview(self, request, code=None):
        invite = self._find_usable_invite(code)
        return Response(InvitePreviewSerializer(invite).data)

    @action(detail=False, methods=['post'])
    def join(self, request):
        serializer = JoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']

        with transaction.atomic():
            invite = self._find_usable_invite(code, for_update=True)
            ensemble = invite.ensemble
            membership = ensemble.membership_of(request.user)
            created = membership is None
            if created:
                membership = Membership.objects.create(ensemble=ensemble, user=request.user)
                Invite.objects.filter(pk=invite.pk).update(uses=F('uses') + 1)

        data = EnsembleSerializer(ensemble, context={'request': request}).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @staticmethod
    def _find_usable_invite(code, for_update=False):
        code = (code or '').strip().upper().replace('-', '')
        queryset = Invite.objects.select_related('ensemble')
        if for_update:
            queryset = queryset.select_for_update()
        invite = queryset.filter(code=code).first()
        # 없는 코드와 쓸 수 없는 코드를 구별해 알려 주지 않는다
        if invite is None or not invite.is_usable:
            raise ValidationError({'code': 'Invalid or expired invite code.'})
        return invite
