import pytest
from django.contrib.auth import get_user_model
from applications.models import Application, ApprovalStatus
from applications import state_machine
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

@pytest.mark.django_db
def test_approve_and_revert_flow():
    applicant = User.objects.create_user(username='app1', password='pw')
    approver = User.objects.create_user(username='appr1', password='pw')
    upload = SimpleUploadedFile('a.txt', b'x', content_type='text/plain')
    app = Application.objects.create(
        applicant=applicant.username,
        approver=approver.username,
        file=upload,
        original_filename='a.txt',
        file_size=1,
        content_type='text/plain',
        comment='c'
    )

    assert app.status == ApprovalStatus.PENDING
    assert app.approved_at is None

    with patch('applications.state_machine.broadcast_application_state') as mock_broadcast:
        # Approve
        res1 = state_machine.change_status(app, ApprovalStatus.APPROVED, approver, comment='ok')
        app.refresh_from_db()
        assert res1.changed is True
        assert app.status == ApprovalStatus.APPROVED
        assert app.approved_at is not None  # タイムスタンプ付与
        assert mock_broadcast.call_count == 1

        # Revert to pending (差し戻し)
        res2 = state_machine.change_status(app, ApprovalStatus.PENDING, approver, comment='back')
        app.refresh_from_db()
        assert res2.changed is True
        assert app.status == ApprovalStatus.PENDING
        # approved_at は保持方針 (None にしない)
        assert app.approved_at is not None
        assert mock_broadcast.call_count == 2

        # No-op (同一ステータス)
        res3 = state_machine.change_status(app, ApprovalStatus.PENDING, approver)
        assert res3.changed is False
        # ブロードキャストは増えない
        assert mock_broadcast.call_count == 2

@pytest.mark.django_db
def test_invalid_transition():
    applicant = User.objects.create_user(username='app2', password='pw')
    approver = User.objects.create_user(username='appr2', password='pw')
    upload = SimpleUploadedFile('b.txt', b'y', content_type='text/plain')
    app = Application.objects.create(
        applicant=applicant.username,
        approver=approver.username,
        file=upload,
        original_filename='b.txt',
        file_size=1,
        content_type='text/plain',
        comment='c'
    )

    # 直接 rejected → approved は現在の定義では許可されていない (一旦 rejected へ遷移後 pending に戻し再承認する想定)
    # まず pending -> rejected
    state_machine.change_status(app, ApprovalStatus.REJECTED, approver, comment='ng')
    app.refresh_from_db()
    assert app.status == ApprovalStatus.REJECTED

    # rejected -> approved (不許可) => InvalidTransition
    with pytest.raises(state_machine.InvalidTransition):
        state_machine.change_status(app, ApprovalStatus.APPROVED, approver)
