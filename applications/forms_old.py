from django import forms
from .models import Application, ApprovalStatus, ApplicationFile

class MultipleFileInput(forms.ClearableFileInput):
    """複数ファイル入力ウィジェット"""
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    """複数ファイルフィールド"""
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
    files = MultipleFileField(
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
        
    def clean_files(self):
        """ファイルのバリデーション"""
        # multipartフォームからファイルリストを取得
        files = []
        if hasattr(self, 'data') and hasattr(self.data, 'getlist'):
            files = self.data.getlist('files')
        elif 'files' in self.files:
            file_data = self.files['files']
            files = [file_data] if not isinstance(file_data, list) else file_data
            
        if not files:
            raise forms.ValidationError('最低1つのファイルを選択してください。')
        
        # ファイルサイズチェック（1ファイルあたり10MB）
        max_size = 10 * 1024 * 1024
        for file in files:
            if file and hasattr(file, 'size') and file.size and file.size > max_size:
                raise forms.ValidationError(f'ファイル "{file.name}" のサイズが大きすぎます。10MB以下のファイルを選択してください。')
        
        # 総ファイル数チェック（最大10ファイル）
        if len(files) > 10:
            raise forms.ValidationError('ファイルは最大10個まで選択できます。')
            
        return files
    
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
