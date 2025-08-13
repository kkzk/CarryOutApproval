from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Application, ApprovalStatus

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """ユーザーシリアライザー"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'full_name', 'department_code')
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class ApplicationSerializer(serializers.ModelSerializer):
    """申請シリアライザー（読み取り用）"""
    applicant = UserSerializer(read_only=True)
    approver = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Application
        fields = [
            'id', 'applicant', 'approver', 'file', 'original_filename',
            'file_size', 'content_type', 'comment', 'approval_comment',
            'status', 'status_display', 'created_at', 'updated_at', 'approved_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'approved_at')


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """申請作成シリアライザー"""
    approver_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Application
        fields = [
            'approver_id', 'file', 'original_filename', 
            'file_size', 'content_type', 'comment'
        ]
    
    def create(self, validated_data):
        approver_id = validated_data.pop('approver_id')
        validated_data['approver_id'] = approver_id
        
        # ファイルから情報を自動取得
        file = validated_data['file']
        if not validated_data.get('original_filename'):
            validated_data['original_filename'] = file.name
        if not validated_data.get('file_size'):
            validated_data['file_size'] = file.size
        if not validated_data.get('content_type'):
            validated_data['content_type'] = getattr(file, 'content_type', 'application/octet-stream')
        
        return super().create(validated_data)


class ApplicationStatusUpdateSerializer(serializers.ModelSerializer):
    """申請ステータス更新シリアライザー"""
    
    class Meta:
        model = Application
        fields = ['status', 'approval_comment']
    
    def validate_status(self, value):
        """ステータスバリデーション"""
        if value not in [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]:
            raise serializers.ValidationError("承認または却下のみ選択可能です。")
        return value
