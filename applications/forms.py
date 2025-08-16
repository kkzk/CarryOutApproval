from django import forms
from .models import Application, ApprovalStatus

class ApplicationCreateForm(forms.ModelForm):
    """申請作成フォーム"""
    approver = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'required': True,
            'placeholder': '承認者のユーザ名（LDAP）を入力'
        }),
        label="承認者ユーザ名（LDAP）"
    )
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '*/*',
            'required': True
        }),
        label="申請ファイル"
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': '申請の詳細や背景を記入してください...'
        }),
        label="申請コメント",
        required=False
    )
    class Meta:
        model = Application
        fields = ['approver', 'file', 'comment']
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    def save(self, commit=True):
        application = super().save(commit=False)
        if self.user:
            application.applicant = self.user.username
        # ファイル情報を自動設定
        if application.file:
            application.original_filename = application.file.name
            application.file_size = application.file.size
            application.content_type = getattr(
                application.file.file, 
                'content_type', 
                'application/octet-stream'
            )
        if commit:
            application.save()
        return application

class ApplicationFilterForm(forms.Form):
    """申請フィルタフォーム"""
    status = forms.ChoiceField(
        choices=[('', 'すべて')] + list(ApprovalStatus.choices),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'this.form.submit();'
        }),
        label="ステータス"
    )
    applicant = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '申請者ユーザ名（LDAP）'
        }),
        label="申請者ユーザ名（LDAP）"
    )
    approver = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '承認者ユーザ名（LDAP）'
        }),
        label="承認者ユーザ名（LDAP）"
    )
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
