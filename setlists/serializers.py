"""
Serializers for setlists app
"""
from rest_framework import serializers
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
        """Validate that the score exists and belongs to the user"""
        from scores.models import Score
        
        user = self.context['request'].user
        try:
            score = Score.objects.get(id=value, user=user)
            return value
        except Score.DoesNotExist:
            raise serializers.ValidationError("Score not found or doesn't belong to you")


class SetlistCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating setlists"""
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Setlist
        fields = [
            'user', 'title', 'description'
        ]
    
    def validate_title(self, value):
        """Ensure title is not empty after stripping whitespace"""
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty")
        return value.strip()


class SetlistSerializer(serializers.ModelSerializer):
    """Full serializer for Setlist model with statistics"""
    items = SetlistItemSerializer(many=True, read_only=True)
    item_count = serializers.ReadOnlyField()
    total_pages = serializers.ReadOnlyField()
    
    class Meta:
        model = Setlist
        fields = [
            'id', 'title', 'description', 'items', 'item_count', 'total_pages',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SetlistListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for setlist lists"""
    item_count = serializers.ReadOnlyField()
    total_pages = serializers.ReadOnlyField()
    
    class Meta:
        model = Setlist
        fields = [
            'id', 'title', 'description', 'item_count', 'total_pages',
            'created_at', 'updated_at'
        ]


class SetlistItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating setlist items"""
    score_id = serializers.IntegerField()
    
    class Meta:
        model = SetlistItem
        fields = ['score_id', 'order_index', 'notes']
    
    def validate_score_id(self, value):
        """Validate that the score exists and belongs to the user"""
        from scores.models import Score
        
        user = self.context['request'].user
        try:
            score = Score.objects.get(id=value, user=user)
            return value
        except Score.DoesNotExist:
            raise serializers.ValidationError("Score not found or doesn't belong to you")
    
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