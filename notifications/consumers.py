import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async  # (将来: 未使用なら削除可)
from django.contrib.auth import get_user_model  # noqa: F401 (互換目的)

# User モデルをインポートレベルでなく関数内で取得するように変更


class NotificationConsumer(AsyncWebsocketConsumer):
    """通知WebSocketコンシューマー"""
    
    async def connect(self):
        """WebSocket接続時の処理"""
        self.user = self.scope["user"]
        
        if self.user.is_authenticated:
            # ID グループ + ユーザ名グループ両方参加 (User レコード未解決時フォールバック用)
            self.group_name = f"user_{self.user.id}"
            self.username_group_name = f"user_{self.user.username}"  # type: ignore[attr-defined]
            
            # ユーザーグループに参加
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.channel_layer.group_add(
                self.username_group_name,
                self.channel_name
            )
            
            await self.accept()
        else:
            await self.close()
    
    async def disconnect(self, close_code):
        """WebSocket切断時の処理"""
        if hasattr(self, 'group_name'):
            # ユーザーグループから離脱
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        if hasattr(self, 'username_group_name'):
            await self.channel_layer.group_discard(
                self.username_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """クライアントからの簡易メッセージ処理 (現在は ping のみ)"""
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if payload.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
    
    async def notification_message(self, event):
        """永続通知機能を無効化したため no-op (後方互換)"""
        return
    
    async def kanban_update(self, event):
        """カンバンボード更新メッセージを送信"""
        await self.send(text_data=json.dumps({
            'type': 'kanban_update',
            'action': event['action'],
            'application': event['application']
        }))
    
    # 既読管理機能は無効化
