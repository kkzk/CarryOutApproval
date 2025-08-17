from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from applications.models import Application, ApprovalStatus
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

class BroadcastAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_applicant = User.objects.create_user(username='applicant1', password='pw')
        self.user_approver = User.objects.create_user(username='approver1', password='pw')
        self.client.login(username='applicant1', password='pw')
        dummy_content = b'dummy'
        upload = SimpleUploadedFile('dummy.txt', dummy_content, content_type='text/plain')
        self.application = Application.objects.create(
            applicant=self.user_applicant.username,
            approver=self.user_approver.username,
            file_size=len(dummy_content),
            file=upload,
            original_filename='dummy.txt',
            content_type='text/plain',
            comment='test'
        )

    def tearDown(self):
        pass

    def test_broadcast_application_state(self):
        resp = self.client.post(f'/notifications/broadcast/application/{self.application.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('application_id'), self.application.id)
