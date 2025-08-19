"""
Views for core app (authentication, user management)
"""
from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .models import User
from .serializers import (
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    UserProfileSerializer
)


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Create a new user and return JWT tokens"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens for the new user
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class UserLoginView(generics.GenericAPIView):
    """User login endpoint"""
    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        """Authenticate user and return JWT tokens"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile endpoint"""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Return the current user"""
        return self.request.user


class DashboardViewSet(viewsets.ViewSet):
    """Dashboard data and statistics"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get dashboard overview data"""
        user = request.user
        
        # Get related data counts
        from scores.models import Score
        from setlists.models import Setlist
        
        scores_qs = Score.objects.filter(user=user)
        setlists_qs = Setlist.objects.filter(user=user)
        
        # Basic counts
        total_scores = scores_qs.count()
        total_setlists = setlists_qs.count()
        
        # Score statistics
        score_stats = scores_qs.aggregate(
            total_size_mb=Sum('size_bytes') / (1024 * 1024) if scores_qs.exists() else 0,
            total_pages=Sum('pages'),
            scores_with_thumbnails=Count('id', filter=Q(thumbnail_key__isnull=False) & ~Q(thumbnail_key=''))
        )
        
        # Quota information
        quota_used_mb = user.used_quota_mb
        quota_total_mb = user.total_quota_mb
        quota_percentage = (quota_used_mb / quota_total_mb * 100) if quota_total_mb > 0 else 0
        quota_available_mb = user.available_quota_mb
        
        # Recent activity (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_scores = scores_qs.filter(created_at__gte=week_ago).count()
        recent_setlists = setlists_qs.filter(created_at__gte=week_ago).count()
        
        # Get latest scores
        latest_scores = scores_qs.order_by('-created_at')[:5].values(
            'id', 'title', 'composer', 'created_at', 'pages', 'thumbnail_key'
        )
        
        # Get latest setlists with item counts
        latest_setlists = []
        for setlist in setlists_qs.order_by('-created_at')[:5]:
            latest_setlists.append({
                'id': setlist.id,
                'title': setlist.title,
                'description': setlist.description,
                'created_at': setlist.created_at,
                'item_count': setlist.item_count,
                'total_pages': setlist.total_pages
            })
        
        return Response({
            'user': {
                'username': user.username,
                'email': user.email,
                'plan': user.plan,
                'created_at': user.date_joined
            },
            'counts': {
                'total_scores': total_scores,
                'total_setlists': total_setlists,
                'scores_with_thumbnails': score_stats['scores_with_thumbnails'],
            },
            'quota': {
                'used_mb': round(quota_used_mb, 2),
                'total_mb': quota_total_mb,
                'available_mb': round(quota_available_mb, 2),
                'percentage_used': round(quota_percentage, 1),
            },
            'statistics': {
                'total_file_size_mb': round(score_stats['total_size_mb'] or 0, 2),
                'total_pages': score_stats['total_pages'] or 0,
            },
            'recent_activity': {
                'scores_this_week': recent_scores,
                'setlists_this_week': recent_setlists,
            },
            'latest_content': {
                'scores': list(latest_scores),
                'setlists': latest_setlists,
            }
        })
    
    @action(detail=False, methods=['get'])
    def quota_details(self, request):
        """Get detailed quota information"""
        user = request.user
        
        # Calculate quota breakdown by file sizes
        from scores.models import Score
        scores_qs = Score.objects.filter(user=user)
        
        # Size distribution
        size_ranges = [
            ('0-1MB', 0, 1 * 1024 * 1024),
            ('1-5MB', 1 * 1024 * 1024, 5 * 1024 * 1024),
            ('5-20MB', 5 * 1024 * 1024, 20 * 1024 * 1024),
            ('20MB+', 20 * 1024 * 1024, float('inf')),
        ]
        
        size_breakdown = []
        for range_name, min_size, max_size in size_ranges:
            if max_size == float('inf'):
                count = scores_qs.filter(size_bytes__gte=min_size).count()
                total_size = scores_qs.filter(size_bytes__gte=min_size).aggregate(
                    total=Sum('size_bytes'))['total'] or 0
            else:
                count = scores_qs.filter(size_bytes__gte=min_size, size_bytes__lt=max_size).count()
                total_size = scores_qs.filter(size_bytes__gte=min_size, size_bytes__lt=max_size).aggregate(
                    total=Sum('size_bytes'))['total'] or 0
            
            size_breakdown.append({
                'range': range_name,
                'count': count,
                'total_size_mb': round(total_size / (1024 * 1024), 2) if total_size else 0
            })
        
        # Monthly usage trend (last 6 months)
        monthly_usage = []
        for i in range(6):
            month_start = timezone.now().replace(day=1) - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=32)
            month_end = month_end.replace(day=1) - timedelta(days=1)
            
            monthly_scores = scores_qs.filter(
                created_at__gte=month_start,
                created_at__lte=month_end
            )
            
            monthly_usage.append({
                'month': month_start.strftime('%Y-%m'),
                'scores_added': monthly_scores.count(),
                'size_added_mb': round((monthly_scores.aggregate(
                    total=Sum('size_bytes'))['total'] or 0) / (1024 * 1024), 2)
            })
        
        return Response({
            'quota_summary': {
                'used_mb': round(user.used_quota_mb, 2),
                'total_mb': user.total_quota_mb,
                'available_mb': round(user.available_quota_mb, 2),
                'percentage_used': round((user.used_quota_mb / user.total_quota_mb * 100), 1) if user.total_quota_mb > 0 else 0,
            },
            'size_breakdown': size_breakdown,
            'monthly_usage': list(reversed(monthly_usage)),  # Most recent first
            'recommendations': self._get_quota_recommendations(user, scores_qs)
        })
    
    def _get_quota_recommendations(self, user, scores_qs):
        """Generate quota usage recommendations"""
        recommendations = []
        
        # Check for large files
        large_files = scores_qs.filter(size_bytes__gt=20 * 1024 * 1024).count()
        if large_files > 0:
            recommendations.append({
                'type': 'large_files',
                'message': f'You have {large_files} files larger than 20MB. Consider optimizing these PDFs.',
                'action': 'Review large files'
            })
        
        # Check for files without thumbnails
        no_thumbnails = scores_qs.filter(Q(thumbnail_key__isnull=True) | Q(thumbnail_key='')).count()
        if no_thumbnails > 0:
            recommendations.append({
                'type': 'missing_thumbnails',
                'message': f'{no_thumbnails} scores are missing thumbnails. Generate them for better performance.',
                'action': 'Generate thumbnails'
            })
        
        # Check quota usage
        quota_percentage = (user.used_quota_mb / user.total_quota_mb * 100) if user.total_quota_mb > 0 else 0
        if quota_percentage > 80:
            recommendations.append({
                'type': 'high_usage',
                'message': f'You\'re using {quota_percentage:.1f}% of your quota. Consider upgrading your plan.',
                'action': 'Upgrade plan'
            })
        elif quota_percentage > 90:
            recommendations.append({
                'type': 'critical_usage',
                'message': 'Your quota is almost full. Clean up unused files or upgrade your plan.',
                'action': 'Clean up or upgrade'
            })
        
        return recommendations
