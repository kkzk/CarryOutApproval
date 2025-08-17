from django.conf import settings

def long_polling_flag(request):
    """ロングポーリング切替フラグをテンプレートへ提供"""
    return {
        'LONG_POLLING_ENABLED': getattr(settings, 'LONG_POLLING_ENABLED', False)
    }
