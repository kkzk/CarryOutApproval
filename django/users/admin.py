from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserProfile, UserSource


class UserProfileInline(admin.StackedInline):
    """ユーザープロファイルのインライン編集"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'プロファイル'


class UserAdmin(BaseUserAdmin):
    """拡張ユーザー管理"""
    inlines = (UserProfileInline,)


# デフォルトのUserAdminを再登録
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """ユーザープロファイル管理"""
    list_display = ('user', 'source', 'department_name', 'title', 'ldap_dn')
    list_filter = ('source', 'department_name', 'title')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'department_name', 'ldap_dn')
    readonly_fields = ('ldap_dn', 'source')
