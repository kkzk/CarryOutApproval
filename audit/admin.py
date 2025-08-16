from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """監査ログ管理"""
    list_display = ('user', 'application', 'action', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'application__id', 'details')
    readonly_fields = ('created_at',)
    
    def has_add_permission(self, request):
        # 監査ログは追加できない
        return False
    
    def has_change_permission(self, request, obj=None):
        # 監査ログは変更できない
        return False
