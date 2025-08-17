"""RQ タスク定義: 通知とカンバン更新をバックグラウンドで処理

責務:
- DB に Notification を作成 (必要なら)
- 対象ユーザの WebSocket グループへイベント送信

WebSocket 送信は channels.layers.get_channel_layer を利用。
RQ ワーカーは同期コンテキストなので async_to_sync で実行。
"""
from __future__ import annotations
from typing import Any
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


def _serialize_application(application) -> Any:  # Serializer は ReturnDict を返す
    from applications.serializers import ApplicationSerializer
    return ApplicationSerializer(application).data


def send_notification_ws(*args, **kwargs):
    """後方互換ダミー (永続通知機能削除済)"""
    return


def create_and_dispatch_notification(*args, **kwargs):
    """後方互換ダミー (永続通知機能削除済)"""
    return


def send_kanban_update(user_id: int | None, action: str, application_id: int, username: str | None = None):
    """カンバン更新イベントをWebSocket送信

    user_id が取得できない (まだ Django User として存在しない) 場合は username グループへフォールバック送信。
    """
    if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
        return
    from applications.models import Application
    application = Application.objects.filter(id=application_id).first()
    if not application:
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    payload = {
        'type': 'kanban_update',
        'action': action,
        'application': _serialize_application(application),
    }
    # 二重通知防止: user_id が取れた場合は ID グループのみ。取れない場合のみ username フォールバック。
    if user_id is not None:
        async_to_sync(channel_layer.group_send)(f"user_{user_id}", payload)
    elif username and username.strip():
        async_to_sync(channel_layer.group_send)(f"user_{username}", payload)
