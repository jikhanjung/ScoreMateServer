"""
Serializers for ensembles app
"""
from rest_framework import serializers

from .models import Ensemble, Membership, Invite


class MemberUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()


class MembershipSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ['user', 'role', 'part', 'joined_at']
        read_only_fields = fields


class MembershipUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ['role', 'part']
        extra_kwargs = {'role': {'required': False}, 'part': {'required': False}}


class EnsembleSerializer(serializers.ModelSerializer):
    """목록 · 만들기 · 수정 — 요청한 사람 기준의 역할과 개수를 함께 준다"""
    my_role = serializers.SerializerMethodField()
    my_part = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    score_count = serializers.SerializerMethodField()

    class Meta:
        model = Ensemble
        fields = [
            'id', 'name', 'description', 'my_role', 'my_part',
            'member_count', 'score_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _membership(self, obj):
        request = self.context.get('request')
        return obj.membership_of(request.user) if request else None

    def get_my_role(self, obj):
        membership = self._membership(obj)
        return membership.role if membership else None

    def get_my_part(self, obj):
        membership = self._membership(obj)
        return membership.part if membership else None

    def get_member_count(self, obj):
        return obj.memberships.count()

    def get_score_count(self, obj):
        return obj.scores.count()

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Name cannot be empty')
        return value.strip()


class EnsembleDetailSerializer(EnsembleSerializer):
    members = MembershipSerializer(source='memberships', many=True, read_only=True)

    class Meta(EnsembleSerializer.Meta):
        fields = EnsembleSerializer.Meta.fields + ['members']


class InviteSerializer(serializers.ModelSerializer):
    """초대 만들기 — expires_in_days 를 주지 않으면 7일, null 이면 만료 없음"""
    expires_in_days = serializers.IntegerField(
        write_only=True, required=False, allow_null=True, min_value=1, max_value=365
    )
    is_usable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invite
        fields = [
            'id', 'code', 'expires_at', 'max_uses', 'uses', 'revoked_at',
            'is_usable', 'created_at', 'expires_in_days'
        ]
        read_only_fields = ['id', 'code', 'expires_at', 'uses', 'revoked_at', 'created_at']
        extra_kwargs = {'max_uses': {'min_value': 1}}


class InvitePreviewSerializer(serializers.Serializer):
    """초대 링크를 연 사람에게 보여 줄 것 — 멤버 목록 · 악보는 가입 전에는 보이지 않는다"""
    ensemble_id = serializers.IntegerField(source='ensemble.id')
    ensemble_name = serializers.CharField(source='ensemble.name')
    member_count = serializers.SerializerMethodField()
    expires_at = serializers.DateTimeField()

    def get_member_count(self, obj):
        return obj.ensemble.memberships.count()


class JoinSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)

    def validate_code(self, value):
        from .services import normalize_code
        return normalize_code(value)
