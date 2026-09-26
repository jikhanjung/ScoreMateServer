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
    FileBlobView,
)

app_name = 'files'

urlpatterns = [
    # File upload/download URLs
    path('files/upload-url/', FileUploadURLView.as_view(), name='upload_url'),
    path('files/download-url/', FileDownloadURLView.as_view(), name='download_url'),
    path('files/download/<int:score_id>/', FileDownloadURLView.as_view(), name='download_score'),
    
    # 악보 파일로 가는 짧은 링크 (서명 URL 로 302)
    path('files/direct-download/<int:score_id>/', FileDirectDownloadView.as_view(), name='direct_download'),
    
    # Upload management
    path('files/upload-confirm/', UploadConfirmationView.as_view(), name='upload_confirm'),
    path('files/upload-cancel/', UploadCancellationView.as_view(), name='upload_cancel'),
    
    # local 저장소: 서명 토큰 URL 로 올리고 받기
    path('files/blob/<str:token>/', FileBlobView.as_view(), name='blob'),
]