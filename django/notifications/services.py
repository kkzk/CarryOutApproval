from .models import Notification, NotificationType
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import json


class NotificationService:
    """通知サービス"""
    
    @staticmethod
    def create_notification(recipient, notification_type, title, message, sender=None, related_application=None):
        """通知を作成する"""
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender,
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
        title = f"新しい申請が提出されました"
        message = f"{application.applicant.username}さんから新しい申請「{application.original_filename}」が提出されました。"
        
        NotificationService.create_notification(
            recipient=application.approver,
            notification_type=NotificationType.NEW_APPLICATION,
            title=title,
            message=message,
            sender=application.applicant,
            related_application=application
        )
        
        # カンバンボード更新通知も送信
        NotificationService.send_kanban_update_notification(
            user=application.approver,
            action='new_application',
            application=application
        )
    
    @staticmethod
    def notify_application_approved(application):
        """申請承認の通知"""
        title = f"申請が承認されました"
        message = f"申請「{application.original_filename}」が{application.approver.username}さんによって承認されました。"
        
        NotificationService.create_notification(
            recipient=application.applicant,
            notification_type=NotificationType.APPLICATION_APPROVED,
            title=title,
            message=message,
            sender=application.approver,
            related_application=application
        )
        
        # 承認者のカンバンボード更新通知も送信
        NotificationService.send_kanban_update_notification(
            user=application.approver,
            action='application_approved',
            application=application
        )
        
        # 申請者のカンバンボード更新通知も送信
        NotificationService.send_kanban_update_notification(
            user=application.applicant,
            action='application_approved',
            application=application
        )
    
    @staticmethod
    def notify_application_rejected(application):
        """申請却下の通知"""
        title = f"申請が却下されました"
        message = f"申請「{application.original_filename}」が{application.approver.username}さんによって却下されました。"
        
        NotificationService.create_notification(
            recipient=application.applicant,
            notification_type=NotificationType.APPLICATION_REJECTED,
            title=title,
            message=message,
            sender=application.approver,
            related_application=application
        )
        
        # 承認者のカンバンボード更新通知も送信
        NotificationService.send_kanban_update_notification(
            user=application.approver,
            action='application_rejected',
            application=application
        )
        
        # 申請者のカンバンボード更新通知も送信
        NotificationService.send_kanban_update_notification(
            user=application.applicant,
            action='application_rejected',
            application=application
        )
