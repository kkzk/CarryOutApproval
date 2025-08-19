from django import forms
from django.forms.widgets import ClearableFileInput
from .models import Application, ApprovalStatus, ApplicationFile

class MultipleFileInput(ClearableFileInput):
    """複数ファイル対応のウィジェット"""
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    """複数ファイル対応のフィールド"""
    widget = MultipleFileInput
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

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
    attachments = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': '*/*',
            'required': True,
            'multiple': True
        }),
        label="申請ファイル",
        help_text="複数ファイルを選択できます（Ctrlキーを押しながらクリック）"
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
        fields = ['approver', 'comment']
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        application = super().save(commit=False)
        if self.user:
            application.applicant = self.user.username
        
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
