from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Application, ApprovalStatus

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """ユーザー + プロファイル フィールド (読み取り専用)"""
    full_name = serializers.SerializerMethodField()
    department_code = serializers.CharField(source='profile.department_code', read_only=True)
    department_name = serializers.CharField(source='profile.department_name', read_only=True)
    title = serializers.CharField(source='profile.title', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'full_name',
            'department_code', 'department_name', 'title'
        )

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class ApplicationSerializer(serializers.ModelSerializer):
    """申請シリアライザー（読み取り用）
    applicant / approver は現在 CharField (ユーザ名) なので、互換性確保のため
    以前のネスト構造に近い dict を返す SerializerMethodField にする。
    """
    applicant = serializers.SerializerMethodField()
    approver = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'applicant', 'approver', 'file', 'original_filename',
            'file_size', 'content_type', 'comment', 'approval_comment',
            'status', 'status_display', 'created_at', 'updated_at', 'approved_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'approved_at')

    def _user_dict(self, username):
        if not username:
            return None
        try:
            user = User.objects.get(username=username)
            serialized = UserSerializer(user).data
            return serialized
        except User.DoesNotExist:
            # 最低限の情報だけ返す
            return {
                'id': None,
                'username': username,
                'first_name': '',
                'last_name': '',
                'full_name': username,
                'department_code': '',
                'department_name': '',
                'title': ''
            }

    def get_applicant(self, obj):
        return self._user_dict(obj.applicant)

    def get_approver(self, obj):
        return self._user_dict(obj.approver)


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """申請作成シリアライザー (approver はユーザ名)"""
    class Meta:
        model = Application
        fields = [
            'approver', 'file', 'original_filename',
            'file_size', 'content_type', 'comment'
        ]

    def create(self, validated_data):
        # ファイル情報自動補完
        file = validated_data['file']
        validated_data.setdefault('original_filename', file.name)
        validated_data.setdefault('file_size', file.size)
        validated_data.setdefault('content_type', getattr(file, 'content_type', 'application/octet-stream'))
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
