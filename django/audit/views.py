from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogListView(generics.ListAPIView):
    """監査ログ一覧"""
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            # 管理者は全てのログを閲覧可能
            return AuditLog.objects.all()
        else:
            # 一般ユーザーは自分が関わった申請のログのみ
            return AuditLog.objects.filter(
                application__applicant=user
            ) | AuditLog.objects.filter(
                application__approver=user
            ).distinct()
