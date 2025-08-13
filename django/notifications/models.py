from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class NotificationType(models.TextChoices):
    """通知タイプ"""
    NEW_APPLICATION = 'new_application', '新規申請'
    APPLICATION_APPROVED = 'application_approved', '申請承認'
    APPLICATION_REJECTED = 'application_rejected', '申請却下'
    APPLICATION_UPDATED = 'application_updated', '申請更新'


class Notification(models.Model):
    """通知モデル"""
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="受信者"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_notifications',
        null=True,
        blank=True,
        verbose_name="送信者"
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        verbose_name="通知タイプ"
    )
    title = models.CharField(
        max_length=255,
        verbose_name="タイトル"
    )
    message = models.TextField(
        verbose_name="メッセージ"
    )
    related_application = models.ForeignKey(
        'applications.Application',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name="関連申請"
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name="既読"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作成日時"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="既読日時"
    )
    
    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.recipient.username}への通知: {self.title}"
    
    def mark_as_read(self):
        """通知を既読にする"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
