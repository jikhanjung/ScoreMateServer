"""
URL configuration for core app (authentication)
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    UserRegistrationView,
    UserLoginView, 
    UserProfileView,
    DashboardViewSet
)

# Router for ViewSets
router = DefaultRouter()
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

app_name = 'core'

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', UserRegistrationView.as_view(), name='register'),
    path('auth/login/', UserLoginView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # User profile endpoints
    path('user/profile/', UserProfileView.as_view(), name='user_profile'),
    
    # ViewSet routes
    path('', include(router.urls)),
]