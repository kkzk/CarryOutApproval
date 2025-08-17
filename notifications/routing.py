"""[deprecated] WebSocket ルーティング (Long Polling 移行で無効)

保持理由: 完全削除前の参照漏れ検証用。`asgi.py` では既に利用していない。
"""

websocket_urlpatterns: list = []  # type: ignore
