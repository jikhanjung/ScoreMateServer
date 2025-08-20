"""
Views for setlists app
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, models
from django.db.models import F
from django.shortcuts import get_object_or_404

from .models import Setlist, SetlistItem
from scores.models import Score
from .serializers import (
    SetlistSerializer, 
    SetlistListSerializer, 
    SetlistCreateUpdateSerializer,
    SetlistItemSerializer,
    SetlistItemCreateSerializer,
    SetlistItemUpdateSerializer
)


class SetlistViewSet(viewsets.ModelViewSet):
    """ViewSet for managing setlists"""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return setlists for the current user only"""
        return Setlist.objects.filter(user=self.request.user).prefetch_related('items__score')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return SetlistListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return SetlistCreateUpdateSerializer
        return SetlistSerializer
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Get all items in a setlist"""
        setlist = self.get_object()
        items = setlist.items.all()
        serializer = SetlistItemSerializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """Add an item to the setlist"""
        setlist = self.get_object()
        
        serializer = SetlistItemCreateSerializer(
            data=request.data,
            context={'request': request, 'setlist': setlist}
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                # If order_index is provided, adjust other items
                order_index = serializer.validated_data.get('order_index')
                if order_index:
                    # Shift existing items with same or higher order_index
                    SetlistItem.objects.filter(
                        setlist=setlist,
                        order_index__gte=order_index
                    ).update(order_index=F('order_index') + 1)
                
                # Create the new item
                item = serializer.save(
                    setlist=setlist,
                    score_id=serializer.validated_data['score_id']
                )
                
                # Return the created item with full details
                return_serializer = SetlistItemSerializer(item)
                return Response(return_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_items(self, request, pk=None):
        """Add multiple items to the setlist"""
        setlist = self.get_object()
        
        score_ids = request.data.get('score_ids', [])
        if not score_ids or not isinstance(score_ids, list):
            return Response(
                {'error': 'score_ids must be a non-empty list'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                created_items = []
                current_max_order = SetlistItem.objects.filter(
                    setlist=setlist
                ).aggregate(
                    max_order=models.Max('order_index')
                )['max_order'] or 0
                
                for i, score_id in enumerate(score_ids):
                    # Validate score exists and belongs to user
                    try:
                        score = Score.objects.get(id=score_id, user=request.user)
                    except Score.DoesNotExist:
                        return Response(
                            {'error': f'Score {score_id} not found'}, 
                            status=status.HTTP_404_NOT_FOUND
                        )
                    
                    # Check if score already in setlist
                    if SetlistItem.objects.filter(setlist=setlist, score=score).exists():
                        continue  # Skip duplicates
                    
                    # Create item
                    item = SetlistItem.objects.create(
                        setlist=setlist,
                        score=score,
                        order_index=current_max_order + i + 1
                    )
                    created_items.append(item)
                
                # Return created items
                serializer = SetlistItemSerializer(created_items, many=True)
                return Response({
                    'created_count': len(created_items),
                    'items': serializer.data
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {'error': f'Failed to add items: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['put', 'patch'], url_path='items/(?P<item_id>[^/.]+)')
    def update_item(self, request, pk=None, item_id=None):
        """Update a setlist item"""
        setlist = self.get_object()
        item = get_object_or_404(SetlistItem, id=item_id, setlist=setlist)
        
        serializer = SetlistItemUpdateSerializer(
            item,
            data=request.data,
            partial=request.method == 'PATCH'
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                old_order = item.order_index
                new_order = serializer.validated_data.get('order_index', old_order)
                
                # If order changed, reorder items
                if old_order != new_order and new_order:
                    if new_order > old_order:
                        # Moving down: shift items between old and new position up
                        SetlistItem.objects.filter(
                            setlist=setlist,
                            order_index__gt=old_order,
                            order_index__lte=new_order
                        ).update(order_index=F('order_index') - 1)
                    else:
                        # Moving up: shift items between new and old position down
                        SetlistItem.objects.filter(
                            setlist=setlist,
                            order_index__gte=new_order,
                            order_index__lt=old_order
                        ).update(order_index=F('order_index') + 1)
                
                serializer.save()
                return Response(SetlistItemSerializer(item).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'], url_path='items/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        """Remove an item from the setlist"""
        setlist = self.get_object()
        item = get_object_or_404(SetlistItem, id=item_id, setlist=setlist)
        
        with transaction.atomic():
            # Get the order index before deletion
            order_index = item.order_index
            
            # Delete the item
            item.delete()
            
            # Shift remaining items down
            if order_index:
                SetlistItem.objects.filter(
                    setlist=setlist,
                    order_index__gt=order_index
                ).update(order_index=F('order_index') - 1)
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def reorder_items(self, request, pk=None):
        """Reorder all items in the setlist"""
        setlist = self.get_object()
        item_orders = request.data.get('items', [])
        
        if not isinstance(item_orders, list):
            return Response(
                {'error': 'items must be a list of {id, order_index} objects'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            for item_data in item_orders:
                if 'id' not in item_data or 'order_index' not in item_data:
                    return Response(
                        {'error': 'Each item must have id and order_index'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                try:
                    item = SetlistItem.objects.get(
                        id=item_data['id'], 
                        setlist=setlist
                    )
                    item.order_index = item_data['order_index']
                    item.save(update_fields=['order_index'])
                except SetlistItem.DoesNotExist:
                    return Response(
                        {'error': f'Item {item_data["id"]} not found in setlist'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        # Return updated setlist
        serializer = SetlistSerializer(setlist)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Create a copy of the setlist"""
        original_setlist = self.get_object()
        
        # Create new setlist
        new_title = f"{original_setlist.title} (Copy)"
        new_setlist = Setlist.objects.create(
            user=request.user,
            title=new_title,
            description=original_setlist.description
        )
        
        # Copy all items
        with transaction.atomic():
            original_items = original_setlist.items.all()
            for item in original_items:
                SetlistItem.objects.create(
                    setlist=new_setlist,
                    score=item.score,
                    order_index=item.order_index,
                    notes=item.notes
                )
        
        serializer = SetlistSerializer(new_setlist)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
