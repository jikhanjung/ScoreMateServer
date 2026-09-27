from django.conf import settings

from scoremateserver.version import VERSION


def site(request):
    from . import google
    return {'app_version': VERSION, 'registration_open': settings.REGISTRATION_OPEN,
            'google_login': google.enabled()}
