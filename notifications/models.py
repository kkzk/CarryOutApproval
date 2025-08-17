"""(削除予定) 永続通知モデルはリファクタで廃止。
マイグレーション後このファイルは空のまま維持し、循環インポート防止用のダミー。"""
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
