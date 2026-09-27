from django.conf import settings

from scoremateserver.version import VERSION


def site(request):
    return {'app_version': VERSION, 'registration_open': settings.REGISTRATION_OPEN}
