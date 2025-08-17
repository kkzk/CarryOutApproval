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

    with patch('applications.state_machine.NotificationService.broadcast_application_state') as mock_broadcast:
        res1 = state_machine.change_status(app, ApprovalStatus.APPROVED, approver, comment='ok')
        app.refresh_from_db()
        assert res1.changed is True
        assert app.status == ApprovalStatus.APPROVED
        assert app.approved_at is not None
        assert mock_broadcast.call_count == 1

        res2 = state_machine.change_status(app, ApprovalStatus.PENDING, approver, comment='back')
        app.refresh_from_db()
        assert res2.changed is True
        assert app.status == ApprovalStatus.PENDING
        assert app.approved_at is not None
        assert mock_broadcast.call_count == 2

        res3 = state_machine.change_status(app, ApprovalStatus.PENDING, approver)
        assert res3.changed is False
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

    state_machine.change_status(app, ApprovalStatus.REJECTED, approver, comment='ng')
    app.refresh_from_db()
    assert app.status == ApprovalStatus.REJECTED

    with pytest.raises(state_machine.InvalidTransition):
        state_machine.change_status(app, ApprovalStatus.APPROVED, approver)
