from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserSource


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """カスタムユーザ管理"""
    # 既存 fieldsets はタプル。拡張分を足した新しいタプルを生成。
    fieldsets = tuple(list(BaseUserAdmin.fieldsets) + [
        ('LDAP / 拡張属性', {
            'fields': ('source', 'ldap_dn', 'department_code', 'department_name', 'title', 'last_synced_at')
        })
    ])
    list_display = ('username', 'email', 'first_name', 'last_name', 'source', 'department_name', 'title', 'is_staff')
    list_filter = tuple(list(BaseUserAdmin.list_filter) + ['source', 'department_name', 'title'])
    readonly_fields = ('ldap_dn', 'last_synced_at')
