from django.urls import re_path
from . import consumers

# WebSocketエンドポイント
# 正式: /ws/notifications/
# 便宜上、よくあるタイプミス /ws/notification/ も受け付ける
websocket_urlpatterns = [
    re_path(r"^ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
    re_path(r"^ws/notification/$", consumers.NotificationConsumer.as_asgi()),  # エイリアス
]
