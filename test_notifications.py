#!/usr/bin/env python
"""
リアルタイム通知システムのテスト用データ作成スクリプト
"""
import os
import sys
import django
from pathlib import Path

# Djangoプロジェクトのパスを設定
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carry_out_approval.settings')
django.setup()

from django.contrib.auth import get_user_model
from applications.models import Application, ApprovalStatus
from notifications.services import NotificationService
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

def create_test_data():
    """テスト用のデータを作成"""
    print("テストデータを作成中...")
    
    # ユーザー作成
    applicant_user, created = User.objects.get_or_create(
        username='applicant',
        defaults={
            'email': 'applicant@example.com',
            'first_name': '申請',
            'last_name': '太郎'
        }
    )
    if created:
        applicant_user.set_password('testpass123')
        applicant_user.save()
        print(f"申請者ユーザーを作成: {applicant_user.username}")
    
    approver_user, created = User.objects.get_or_create(
        username='approver',
        defaults={
            'email': 'approver@example.com',
            'first_name': '承認',
            'last_name': '花子'
        }
    )
    if created:
        approver_user.set_password('testpass123')
        approver_user.save()
        print(f"承認者ユーザーを作成: {approver_user.username}")
    
    # テスト用のファイルを作成
    test_file_content = b"This is a test file for approval system."
    test_file = SimpleUploadedFile(
        "test_document.txt",
        test_file_content,
        content_type="text/plain"
    )
    
    # 申請を作成（これで承認者に通知が送信されるはず）
    application = Application.objects.create(
        applicant=applicant_user,
        approver=approver_user,
        file=test_file,
        original_filename="test_document.txt",
        file_size=len(test_file_content),
        content_type="text/plain",
        comment="これはテスト用の申請です。リアルタイム通知のテストを行っています。"
    )
    
    print(f"テスト申請を作成: ID={application.id}")
    print(f"申請者: {applicant_user.username}")
    print(f"承認者: {approver_user.username}")
    print("承認者に新規申請の通知が送信されました。")
    
    return {
        'applicant': applicant_user,
        'approver': approver_user,
        'application': application
    }

def test_approval_notification(application):
    """承認/却下通知のテスト"""
    print("\n承認通知のテスト...")
    
    # 申請を承認
    application.status = ApprovalStatus.APPROVED
    application.approval_comment = "承認します。問題ありません。"
    application.save()
    
    print("申請が承認されました。申請者に承認通知が送信されました。")

def main():
    """メイン処理"""
    print("=== リアルタイム通知システムテスト ===\n")
    
    # テストデータ作成
    test_data = create_test_data()
    
    # 少し待ってから承認通知をテスト
    import time
    print("\n5秒後に承認通知をテストします...")
    time.sleep(5)
    
    test_approval_notification(test_data['application'])
    
    print("\n=== テスト完了 ===")
    print("ブラウザで以下のユーザーでログインして通知を確認してください:")
    print("申請者: applicant / testpass123")
    print("承認者: approver / testpass123")
    print("管理者: admin / (設定したパスワード)")

if __name__ == '__main__':
    main()
