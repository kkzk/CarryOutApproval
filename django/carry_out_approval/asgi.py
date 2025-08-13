"""
ASGI config for carry_out_approval project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carry_out_approval.settings')

# Djangoの初期化（staticfiles設定を含む）
django_asgi_app = get_asgi_application()

# WebSocketルーティングのインポート
from notifications import routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,  # WhiteNoiseミドルウェアで静的ファイルも配信
    "websocket": AuthMiddlewareStack(
        URLRouter(
            routing.websocket_urlpatterns
        )
    ),
})
