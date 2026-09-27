"""
Serializers for setlists app
"""
from rest_framework import serializers
from ensembles.models import Ensemble
from .models import Setlist, SetlistItem
from scores.serializers import ScoreListSerializer


class SetlistItemSerializer(serializers.ModelSerializer):
    """Serializer for SetlistItem model"""
    score = ScoreListSerializer(read_only=True)
    score_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = SetlistItem
        fields = [
            'id', 'score', 'score_id', 'order_index', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_score_id(self, value):
        """읽을 수 있고, 이 세트리스트에 넣을 수 있는 악보 (앙상블 곡목 = 그 앙상블 악보, 내 세트리스트 = 내 악보)"""
        from scores.models import Score

        user = self.context['request'].user
        setlist = self.context.get('setlist')
        score = Score.objects.readable_by(user).filter(id=value).first()
        if score is None or (setlist is not None and not setlist.can_include(score)):
            raise serializers.ValidationError("Score not found or doesn't belong to you")
        return value


class SetlistCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating setlists"""
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    ensemble = serializers.PrimaryKeyRelatedField(queryset=Ensemble.objects.all(), required=False, allow_null=True)
    
    class Meta:
        model = Setlist
        fields = [
            'id', 'user', 'title', 'description', 'ensemble'
        ]
        read_only_fields = ['id']

    def validate_ensemble(self, value):
        """앙상블 곡목은 owner · leader 가 만든다. 만든 뒤에는 옮기지 않는다(항목이 그 앙상블 악보다)"""
        if self.instance is not None:
            if value != self.instance.ensemble:
                raise serializers.ValidationError('A setlist cannot move between ensembles.')
            return value
        from scores.serializers import validate_target_ensemble
        return validate_target_ensemble(self.context['request'], value)

    def update(self, instance, validated_data):
        validated_data.pop('user', None)   # 리더가 고쳐도 만든 사람은 그대로
        return super().update(instance, validated_data)
    
    def validate_title(self, value):
        """Ensure title is not empty after stripping whitespace"""
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty")
        return value.strip()


class SetlistAccessMixin(serializers.Serializer):
    ensemble_name = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    def get_ensemble_name(self, obj):
        return obj.ensemble.name if obj.ensemble_id else None

    def get_can_edit(self, obj):
        request = self.context.get('request')
        return bool(request) and obj.can_edit(request.user)


SETLIST_ACCESS_FIELDS = ['ensemble', 'ensemble_name', 'can_edit']


class SetlistSerializer(SetlistAccessMixin, serializers.ModelSerializer):
    """Full serializer for Setlist model with statistics"""
    items = serializers.SerializerMethodField()
    item_count = serializers.ReadOnlyField()
    total_pages = serializers.ReadOnlyField()
    
    class Meta:
        model = Setlist
        fields = [
            'id', 'title', 'description', 'items', 'item_count', 'total_pages',
            'created_at', 'updated_at'
        ] + SETLIST_ACCESS_FIELDS
        read_only_fields = ['id', 'created_at', 'updated_at', 'ensemble']

    def get_items(self, obj):
        """요청한 사람이 읽을 수 있는 악보만 — 악보가 앙상블 밖으로 옮겨졌으면 그 항목은 보이지 않는다"""
        items = list(obj.items.all())
        request = self.context.get('request')
        if request is not None:
            from scores.models import Score
            readable = set(Score.objects.readable_by(request.user)
                           .filter(id__in=[i.score_id for i in items]).values_list('id', flat=True))
            items = [i for i in items if i.score_id in readable]
        return SetlistItemSerializer(items, many=True, context=self.context).data


class SetlistListSerializer(SetlistAccessMixin, serializers.ModelSerializer):
    """Lightweight serializer for setlist lists"""
    item_count = serializers.ReadOnlyField()
    total_pages = serializers.ReadOnlyField()
    
    class Meta:
        model = Setlist
        fields = [
            'id', 'title', 'description', 'item_count', 'total_pages',
            'created_at', 'updated_at'
        ] + SETLIST_ACCESS_FIELDS


class SetlistItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating setlist items"""
    score_id = serializers.IntegerField()
    
    class Meta:
        model = SetlistItem
        fields = ['score_id', 'order_index', 'notes']
    
    def validate_score_id(self, value):
        """읽을 수 있고, 이 세트리스트에 넣을 수 있는 악보 (앙상블 곡목 = 그 앙상블 악보, 내 세트리스트 = 내 악보)"""
        from scores.models import Score

        user = self.context['request'].user
        setlist = self.context.get('setlist')
        score = Score.objects.readable_by(user).filter(id=value).first()
        if score is None or (setlist is not None and not setlist.can_include(score)):
            raise serializers.ValidationError("Score not found or doesn't belong to you")
        return value
    
    def validate(self, data):
        """Validate that the score is not already in the setlist"""
        setlist = self.context.get('setlist')
        score_id = data.get('score_id')
        
        if setlist and score_id:
            if SetlistItem.objects.filter(setlist=setlist, score_id=score_id).exists():
                raise serializers.ValidationError("This score is already in the setlist")
        
        return data


class SetlistItemUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating setlist items"""
    
    class Meta:
        model = SetlistItem
        fields = ['order_index', 'notes']
    
    def validate_order_index(self, value):
        """Validate order_index is positive"""
        if value is not None and value < 1:
            raise serializers.ValidationError("Order index must be positive")
        return value