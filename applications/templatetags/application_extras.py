from django import template
from applications.models import FileReviewStatus

register = template.Library()

@register.filter
def is_file_reviewed_by(file_obj, username):
    """ファイルが指定された承認者によって確認済みかチェック"""
    if not file_obj or not username:
        return False
    
    try:
        return FileReviewStatus.objects.filter(
            file=file_obj,
            approver=username
        ).exists()
    except (ValueError, AttributeError):
        return False

@register.filter
def is_legacy_file_reviewed_by(application, username):
    """旧形式のファイルが確認済みかチェック"""
    if not application or not username:
        return False
    
    try:
        return FileReviewStatus.objects.filter(
            application=application,
            file__isnull=True,
            approver=username
        ).exists()
    except (ValueError, AttributeError):
        return False

@register.filter
def all_files_reviewed_by(application, username):
    """すべてのファイルが承認者によって確認済みかチェック"""
    if not username:
        return False
    
    try:
        return application.get_all_files_reviewed_by(username)
    except AttributeError:
        return False
