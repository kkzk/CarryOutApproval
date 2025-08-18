from django.db import models
from django.contrib.auth import get_user_model
import os
import uuid
from datetime import datetime

User = get_user_model()


class ApprovalStatus(models.TextChoices):
    """承認ステータス"""
    PENDING = 'pending', '申請中'
    APPROVED = 'approved', '承認済み'
    REJECTED = 'rejected', '却下'


def get_upload_path(instance, filename):
    """アップロードパスを生成する関数"""
    ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join('uploads', unique_filename)


class ApplicationFile(models.Model):
    """申請ファイルモデル"""
    application = models.ForeignKey(
        'Application',
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name="申請"
    )
    file = models.FileField(
        upload_to=get_upload_path,
        verbose_name="ファイル"
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name="元ファイル名"
    )
    file_size = models.IntegerField(
        verbose_name="ファイルサイズ"
    )
    content_type = models.CharField(
        max_length=100,
        verbose_name="コンテンツタイプ"
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="アップロード日時"
    )
    
    class Meta:
        verbose_name = "申請ファイル"
        verbose_name_plural = "申請ファイル"
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"{self.original_filename} ({self.application.id})"


class Application(models.Model):
    """申請モデル"""
    id = models.AutoField(
        primary_key=True,
        verbose_name="ID"
    )
    applicant = models.CharField(
        max_length=150,
        verbose_name="申請者ユーザ名（LDAP）"
    )
    approver = models.CharField(
        max_length=150,
        verbose_name="承認者ユーザ名（LDAP）"
    )
    # 下位互換性のため一時的に残すが、今後は files リレーションを使用
    file = models.FileField(
        upload_to=get_upload_path,
        verbose_name="ファイル",
        blank=True,
        null=True
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name="元ファイル名",
        blank=True
    )
    file_size = models.IntegerField(
        verbose_name="ファイルサイズ",
        blank=True,
        null=True
    )
    content_type = models.CharField(
        max_length=100,
        verbose_name="コンテンツタイプ",
        blank=True
    )
    comment = models.TextField(
        blank=True,
        verbose_name="申請コメント"
    )
    approval_comment = models.TextField(
        blank=True,
        verbose_name="承認コメント"
    )
    status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        verbose_name="ステータス"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作成日時"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新日時"
    )
    approved_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="承認日時"
    )
    
    class Meta:
        verbose_name = "申請"
        verbose_name_plural = "申請"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.applicant}の申請 ({self.id})"
    
    @property
    def primary_file(self):
        """メインファイルを取得（下位互換性のため）"""
        if self.file:
            return self.file
        files = self.files.first()
        return files.file if files else None
    
    @property
    def primary_filename(self):
        """メインファイル名を取得（下位互換性のため）"""
        if self.original_filename:
            return self.original_filename
        files = self.files.first()
        return files.original_filename if files else None
    
    @property
    def total_file_size(self):
        """全ファイルの合計サイズを取得"""
        if self.file_size:
            return self.file_size
        return sum(f.file_size for f in self.files.all())
    
    @property
    def file_count(self):
        """ファイル数を取得"""
        if self.file:
            return 1
        return self.files.count()


"""以前は post_save シグナルで通知処理を行っていたが、
明示的な View/API 層での呼び出しに移行したため削除。
モデルは純粋なデータ構造のみを保持し副作用を避ける。"""
