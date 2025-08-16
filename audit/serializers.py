from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """監査ログシリアライザー"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    application_id = serializers.IntegerField(source='application.id', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user_name', 'application_id', 
            'action', 'details', 'created_at'
        ]
        read_only_fields = ['created_at']
