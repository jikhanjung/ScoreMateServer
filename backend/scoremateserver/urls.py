"""
URL configuration for scoremateserver project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def api_root(request):
    """API root endpoint"""
    return JsonResponse({
        'message': 'ScoreMate API v1',
        'endpoints': {
            'auth': '/api/v1/auth/',
            'scores': '/api/v1/scores/',
            'setlists': '/api/v1/setlists/',
            'files': '/api/v1/files/',
            'user': '/api/v1/user/',
            'dashboard': '/api/v1/dashboard/',
            'admin': '/admin/',
        }
    })


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API v1
    path('api/v1/', api_root, name='api_root'),
    path('api/v1/', include('core.urls')),
    path('api/v1/', include('scores.urls')),
    path('api/v1/', include('setlists.urls')),
    path('api/v1/', include('files.urls')),
    path('api/v1/admin/', include('scoremate_admin.urls')),
    
    # Default redirect to API
    path('', api_root, name='root'),
]
