import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

# User モデルをインポートレベルでなく関数内で取得するように変更


class NotificationConsumer(AsyncWebsocketConsumer):
    """通知WebSocketコンシューマー"""
    
    async def connect(self):
        """WebSocket接続時の処理"""
        self.user = self.scope["user"]
        
        if self.user.is_authenticated:
            self.group_name = f"user_{self.user.id}"
            
            # ユーザーグループに参加
            await self.channel_layer.group_add(
                self.group_name,
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
    
    async def receive(self, text_data):
        """メッセージ受信時の処理"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'ping':
                # ピング応答
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
            elif message_type == 'mark_read':
                # 通知既読処理
                notification_id = text_data_json.get('notification_id')
                if notification_id:
                    await self.mark_notification_as_read(notification_id)
        except json.JSONDecodeError:
            pass
    
    async def notification_message(self, event):
        """通知メッセージを送信"""
        notification = event['notification']
        
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': notification
        }))
    
    async def kanban_update(self, event):
        """カンバンボード更新メッセージを送信"""
        await self.send(text_data=json.dumps({
            'type': 'kanban_update',
            'action': event['action'],
            'application': event['application']
        }))
    
    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """通知を既読にする（非同期対応）"""
        from .models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=self.user
            )
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
