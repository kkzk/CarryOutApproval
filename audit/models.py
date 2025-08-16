from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AuditLog(models.Model):
    """監査ログモデル"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="実行ユーザー"
    )
    application = models.ForeignKey(
        'applications.Application',
        on_delete=models.CASCADE,
        verbose_name="対象申請"
    )
    action = models.CharField(
        max_length=50,
        verbose_name="アクション"
    )
    details = models.TextField(
        verbose_name="詳細"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="実行日時"
    )
    
    class Meta:
        verbose_name = "監査ログ"
        verbose_name_plural = "監査ログ"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.created_at}"
