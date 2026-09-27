from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeviceCodeView, DeviceTokenView, DeviceViewSet

app_name = 'devices'

router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')

urlpatterns = [
    path('device/code', DeviceCodeView.as_view(), name='device_code'),
    path('device/code/', DeviceCodeView.as_view()),
    path('device/token', DeviceTokenView.as_view(), name='device_token'),
    path('device/token/', DeviceTokenView.as_view()),
    path('', include(router.urls)),
]
