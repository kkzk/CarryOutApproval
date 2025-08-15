from django.db import models
from django.contrib.auth.models import User


class UserSource(models.TextChoices):
    LOCAL = 'local', 'ローカル'
    LDAP = 'ldap', 'LDAP'


class UserProfile(models.Model):
    """ユーザープロファイル - LDAP関連情報を保存"""
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='profile'
    )
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
        verbose_name = "ユーザープロファイル"
        verbose_name_plural = "ユーザープロファイル"
    
    def __str__(self):
        return f"{self.user.username}のプロファイル"


# Djangoデフォルトユーザーモデルを拡張するためのシグナル
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """ユーザー作成時にプロファイルも作成"""
    if created:
        UserProfile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            UserProfile.objects.create(user=instance)
