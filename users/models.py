from django.db import models
from django.contrib.auth.models import AbstractUser


class UserSource(models.TextChoices):
    LOCAL = 'local', 'ローカル'
    LDAP = 'ldap', 'LDAP'


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
    department_code = models.CharField(
        max_length=20,
        verbose_name="所属コード",
        blank=True
    )
    department_name = models.CharField(
        max_length=100,
        verbose_name="所属名",
        blank=True
    )
    title = models.CharField(
        max_length=100,
        verbose_name="役職",
        blank=True
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
