from .models import Notification, NotificationType
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
import json

User = get_user_model()


def _resolve_user(maybe_user_or_username):
    """文字列(ユーザ名)が渡された場合は User を取得。既に User ならそのまま返す。
    見つからない場合は None を返し、呼び出し側でスキップ判断。
    """
    if maybe_user_or_username is None:
        return None
    if hasattr(maybe_user_or_username, 'pk'):
        return maybe_user_or_username  # User インスタンス想定
    # 文字列としてユーザ名が来たケース
    username = str(maybe_user_or_username).strip()
    if not username:
        return None
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


class NotificationService:
    """通知サービス"""
    
    @staticmethod
    def create_notification(recipient, notification_type, title, message, sender=None, related_application=None):
        """通知を作成する
        recipient / sender は User または ユーザ名(str) を受け付ける。
        ユーザ名がローカルDBに存在しない場合は通知をスキップ(将来: 自動作成検討)。
        """
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return None
        resolved_recipient = _resolve_user(recipient)
        resolved_sender = _resolve_user(sender)
        if not resolved_recipient:
            # 受信者が特定できないので作成せず終了
            return None
        notification = Notification.objects.create(
            recipient=resolved_recipient,
            sender=resolved_sender,
            notification_type=notification_type,
            title=title,
            message=message,
            related_application=related_application
        )

        # WebSocketで即座に通知を送信
        NotificationService.send_real_time_notification(notification)

        return notification
    
    @staticmethod
    def send_real_time_notification(notification):
        """WebSocketでリアルタイム通知を送信"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        from .serializers import NotificationSerializer
        
        channel_layer = get_channel_layer()
        if channel_layer:
            notification_data = NotificationSerializer(notification).data
            
            # ユーザー固有のグループに送信
            group_name = f"user_{notification.recipient.id}"
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_message',
                    'notification': notification_data
                }
            )
    
    @staticmethod
    def send_kanban_update_notification(user, action, application):
        """カンバンボード更新通知を送信"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        from applications.serializers import ApplicationSerializer
        
        channel_layer = get_channel_layer()
        if channel_layer:
            application_data = ApplicationSerializer(application).data
            
            # ユーザー固有のグループに送信
            group_name = f"user_{user.id}"
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'kanban_update',
                    'action': action,
                    'application': application_data
                }
            )
    
    @staticmethod
    def notify_new_application(application):
        """新規申請の通知"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        title = "新しい申請が提出されました"
        applicant_name = getattr(application.applicant, 'username', str(application.applicant))
        message = f"{applicant_name}さんから新しい申請「{application.original_filename}」が提出されました。"
        NotificationService.create_notification(
            recipient=application.approver,
            notification_type=NotificationType.NEW_APPLICATION,
            title=title,
            message=message,
            sender=application.applicant,
            related_application=application
        )
        NotificationService.send_kanban_update_notification(
            user=application.approver,
            action='new_application',
            application=application
        )
    
    @staticmethod
    def notify_application_approved(application):
        """申請承認の通知"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        title = "申請が承認されました"
        approver_name = getattr(application.approver, 'username', str(application.approver))
        message = f"申請「{application.original_filename}」が{approver_name}さんによって承認されました。"
        NotificationService.create_notification(
            recipient=application.applicant,
            notification_type=NotificationType.APPLICATION_APPROVED,
            title=title,
            message=message,
            sender=application.approver,
            related_application=application
        )
        NotificationService.send_kanban_update_notification(
            user=application.approver,
            action='application_approved',
            application=application
        )
        NotificationService.send_kanban_update_notification(
            user=application.applicant,
            action='application_approved',
            application=application
        )
    
    @staticmethod
    def notify_application_rejected(application):
        """申請却下の通知"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        title = "申請が却下されました"
        approver_name = getattr(application.approver, 'username', str(application.approver))
        message = f"申請「{application.original_filename}」が{approver_name}さんによって却下されました。"
        NotificationService.create_notification(
            recipient=application.applicant,
            notification_type=NotificationType.APPLICATION_REJECTED,
            title=title,
            message=message,
            sender=application.approver,
            related_application=application
        )
        NotificationService.send_kanban_update_notification(
            user=application.approver,
            action='application_rejected',
            application=application
        )
        NotificationService.send_kanban_update_notification(
            user=application.applicant,
            action='application_rejected',
            application=application
        )
