from django.conf import settings

def long_polling_flag(_request):
    return {'LONG_POLLING_ENABLED': getattr(settings, 'LONG_POLLING_ENABLED', False)}
