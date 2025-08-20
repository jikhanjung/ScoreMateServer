"""
URL configuration for files app
"""
from django.urls import path

from .views import (
    FileUploadURLView,
    FileDownloadURLView,
    FileDirectDownloadView,
    UploadConfirmationView,
    UploadCancellationView,
    get_thumbnail
)

app_name = 'files'

urlpatterns = [
    # File upload/download URLs
    path('files/upload-url/', FileUploadURLView.as_view(), name='upload_url'),
    path('files/download-url/', FileDownloadURLView.as_view(), name='download_url'),
    path('files/download/<int:score_id>/', FileDownloadURLView.as_view(), name='download_score'),
    
    # Direct file download (proxy)
    path('files/direct-download/<int:score_id>/', FileDirectDownloadView.as_view(), name='direct_download'),
    
    # Upload management
    path('files/upload-confirm/', UploadConfirmationView.as_view(), name='upload_confirm'),
    path('files/upload-cancel/', UploadCancellationView.as_view(), name='upload_cancel'),
    
    # Thumbnail serving
    path('files/thumbnail/<path:thumbnail_key>', get_thumbnail, name='thumbnail'),
]