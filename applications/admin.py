from django.contrib import admin
from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """申請管理"""
    list_display = (
        'id', 
        'applicant', 
        'approver', 
        'original_filename', 
        'status', 
        'created_at', 
        'approved_at'
    )
    list_filter = ('status', 'created_at', 'approved_at')
    search_fields = (
        'applicant__username', 
        'approver__username', 
        'original_filename',
        'comment'
    )
    readonly_fields = ('created_at', 'updated_at', 'file_size', 'content_type')
    
    fieldsets = (
        ('基本情報', {
            'fields': ('applicant', 'approver', 'status')
        }),
        ('ファイル情報', {
            'fields': ('file', 'original_filename', 'file_size', 'content_type')
        }),
        ('コメント', {
            'fields': ('comment', 'approval_comment')
        }),
        ('日時情報', {
            'fields': ('created_at', 'updated_at', 'approved_at'),
            'classes': ('collapse',)
        }),
    )
