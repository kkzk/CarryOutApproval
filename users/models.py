from django.db import models
from django.contrib.auth.models import AbstractUser


class UserSource(models.TextChoices):
    LOCAL = 'local', 'ローカル'
    LDAP = 'ldap', 'LDAP'


class Department(models.Model):
    """所属（部署）モデル"""
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="所属コード"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="所属名称"
    )
    parent_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="上位所属コード",
        help_text="上位階層の所属コード"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="有効"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作成日時"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新日時"
    )
    
    class Meta:
        verbose_name = "所属"
        verbose_name_plural = "所属"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class User(AbstractUser):
    """カスタムユーザモデル (旧 UserProfile を統合)

    注意: 既存 DB / マイグレーションを破棄して初期化する前提。
    """
    source = models.CharField(
        max_length=20,
        choices=UserSource.choices,
        default=UserSource.LOCAL,
        db_index=True,
        verbose_name="出所"
    )
    ldap_dn = models.TextField(
        verbose_name="LDAP DN",
        blank=True,
        help_text="Active DirectoryのDistinguished Name"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="所属",
        related_name="users"
    )
    # 下位互換性のため残す（データ移行後に削除予定）
    department_code = models.CharField(
        max_length=20,
        verbose_name="所属コード（旧）",
        blank=True
    )
    parent_department_code = models.CharField(
        max_length=20,
        verbose_name="上位所属コード",
        blank=True,
        help_text="所属の上位階層コード (手動設定)"
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="LDAP最終同期時刻"
    )

    class Meta:
        verbose_name = "ユーザー"
        verbose_name_plural = "ユーザー"

    def __str__(self):  # noqa: D401 - シンプル表示
        return self.username
