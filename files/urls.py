"""
URL configuration for files app
"""
from django.urls import path

from .views import (
    FileUploadURLView,
    FileDownloadURLView,
    UploadConfirmationView,
    UploadCancellationView
)

app_name = 'files'

urlpatterns = [
    # File upload/download URLs
    path('files/upload-url/', FileUploadURLView.as_view(), name='upload_url'),
    path('files/download-url/', FileDownloadURLView.as_view(), name='download_url'),
    
    # Upload management
    path('files/upload-confirm/', UploadConfirmationView.as_view(), name='upload_confirm'),
    path('files/upload-cancel/', UploadCancellationView.as_view(), name='upload_cancel'),
]