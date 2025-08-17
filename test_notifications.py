#!/usr/bin/env python
"""
Long Polling 移行後のカンバン更新差分取得デモスクリプト。

目的:
 1. 申請 (Application) を作成 → Poll API (/applications/poll/updates/?scope=kanban) で更新検出
 2. ステータス変更 (承認) 後に再度 Poll して差分が返ることを確認

旧 WebSocket / RQ ベースの push 通知は無効化されているため、本スクリプトは
HTTP 経由の差分取得のみを利用します。

実行方法:
    uv run python test_notifications.py

期待出力:
    - 初回 poll (since=過去) で作成直後申請がヒット
    - ステータス変更後の poll で updated_at 変化を検出し差分 1 件表示

注意:
    - 実運用ではブラウザ JS が連続的に poll します (1 リクエスト完了直後に次を送信)
    - 本デモは簡潔さのため 2 回のみ実施
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
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone
import json
from datetime import timedelta

User = get_user_model()

def create_test_data():
    """テスト用ユーザ & 申請作成"""
    print("テストデータを作成中...")

    applicant_user, _ = User.objects.get_or_create(
        username='applicant',
        defaults={'email': 'applicant@example.com', 'first_name': '申請', 'last_name': '太郎'}
    )
    if not applicant_user.has_usable_password():
        applicant_user.set_password('testpass123'); applicant_user.save()

    approver_user, _ = User.objects.get_or_create(
        username='approver',
        defaults={'email': 'approver@example.com', 'first_name': '承認', 'last_name': '花子'}
    )
    if not approver_user.has_usable_password():
        approver_user.set_password('testpass123'); approver_user.save()

    test_file_content = b"This is a test file for approval system."
    test_file = SimpleUploadedFile("test_document.txt", test_file_content, content_type="text/plain")

    application = Application.objects.create(
        applicant=applicant_user,
        approver=approver_user,
        file=test_file,
        original_filename="test_document.txt",
        file_size=len(test_file_content),
        content_type="text/plain",
        comment="Long Polling 動作検証用申請"
    )

    print(f"申請作成: ID={application.id} status={application.status}")
    return applicant_user, approver_user, application

def approve_application(application):
    """申請を承認し updated_at を変化させる"""
    application.status = ApprovalStatus.APPROVED
    application.approval_comment = "承認 (Long Polling テスト)"
    application.save(update_fields=["status", "approval_comment", "updated_at"])
    print(f"申請承認完了: ID={application.id} new_status={application.status}")


def poll(client: Client, since_iso: str | None, scope: str = 'kanban'):
    params = {'scope': scope}
    if since_iso:
        params['since'] = since_iso
    resp = client.get('/applications/poll/updates/', params)
    try:
        data = json.loads(resp.content.decode('utf-8'))
    except json.JSONDecodeError:
        print('Poll 応答 JSON 解析失敗:', resp.content[:200])
        return None
    return data

def main():
    print("=== Long Polling 差分取得デモ ===\n")
    applicant, approver, application = create_test_data()

    # Poll 用クライアント (承認者視点で差分取得)
    client = Client()
    client.force_login(approver)

    # 過去時刻を since に設定 (全件取得トリガ)
    since = (timezone.now() - timedelta(minutes=10)).isoformat()
    first = poll(client, since, scope='kanban')
    print("初回 Poll 応答:", json.dumps(first, ensure_ascii=False, indent=2)[:400])
    latest = first.get('latest') if first else None

    # ステータス変更
    approve_application(application)

    # 2回目 poll (最新 since=latest)
    second = poll(client, latest, scope='kanban')
    print("\n承認後 Poll 応答:", json.dumps(second, ensure_ascii=False, indent=2)[:400])

    print("\n=== 完了: 差分 (applications 長) 初回={0} / 2回目={1} ===".format(
        len(first.get('applications', [])) if first else 'N/A',
        len(second.get('applications', [])) if second else 'N/A'
    ))

if __name__ == '__main__':
    main()
