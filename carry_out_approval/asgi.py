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
if getattr(settings, 'LONG_POLLING_ENABLED', False):
    # ロングポーリング移行中: WebSocket は正式サポート停止。誤接続時に静かに即時クローズするフォールバックを用意。
    async def _websocket_fallback(scope, receive, send):  # type: ignore[override]
        if scope["type"] != "websocket":
            return
        # 受理して即クローズ (ブラウザ側は再接続しない実装のため静かに終了)
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": 1000})

    application = ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": _websocket_fallback,
    })
else:
    from notifications import routing  # 遅延 import
    application = ProtocolTypeRouter({
        "http": django_asgi_app,  # WhiteNoiseミドルウェアで静的ファイルも配信
        "websocket": AuthMiddlewareStack(
            URLRouter(
                routing.websocket_urlpatterns
            )
        ),
    })
