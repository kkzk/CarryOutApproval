from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """通知シリアライザー"""
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    application_id = serializers.IntegerField(source='related_application.id', read_only=True)
    application_title = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 
            'sender_name', 'application_id', 'application_title',
            'is_read', 'created_at', 'read_at', 'time_ago'
        ]
    
    def get_application_title(self, obj):
        """申請タイトルを取得"""
        if obj.related_application:
            return f"申請ID: {obj.related_application.id} ({obj.related_application.original_filename})"
        return None
    
    def get_time_ago(self, obj):
        """相対時間を取得"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days}日前"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}時間前"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}分前"
        else:
            return "たった今"
