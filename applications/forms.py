from django import forms
from django.forms.widgets import FileInput
from .models import Application, ApprovalStatus, ApplicationFile
from users.models import Department
from .widgets import SearchableModelMultipleChoiceField


class MultipleFileInput(FileInput):
    """複数ファイル選択対応のウィジェット"""
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs['multiple'] = True
        super().__init__(attrs)

    def value_from_datadict(self, data, files, name):
        """複数ファイルの取得"""
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return files.get(name)

class MultipleFileField(forms.FileField):
    """複数ファイル対応のフィールド"""
    widget = MultipleFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data and self.required:
            raise forms.ValidationError(self.error_messages['required'])
        
        if not isinstance(data, list):
            data = [data] if data else []
        
        # 各ファイルを個別にバリデーション
        result = []
        for file in data:
            if file:
                single_file_clean = super().clean
                result.append(single_file_clean(file, initial))
        
        # ファイル数チェック
        if len(result) > 10:
            raise forms.ValidationError('ファイルは最大10個まで選択できます。')
        
        # ファイルサイズチェック
        max_size = 10 * 1024 * 1024  # 10MB
        for file in result:
            if hasattr(file, 'size') and file.size > max_size:
                raise forms.ValidationError(f'ファイル "{file.name}" のサイズが大きすぎます。10MB以下のファイルを選択してください。')
        
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
    carry_out_destinations = SearchableModelMultipleChoiceField(
        queryset=Department.objects.filter(is_active=True),
        label="持出先所属",
        required=False,
        help_text="検索で絞り込んで複数選択できます"
    )
    
    class Meta:
        model = Application
        fields = ['approver', 'comment', 'carry_out_destinations']
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # ウィジェットの属性を設定
        self.fields['attachments'].widget.attrs.update({
            'class': 'form-control',
            'accept': '*/*',
            'required': True
        })
    
    def save(self, commit=True):
        application = super().save(commit=False)
        if self.user:
            application.applicant = self.user.username
        
        if commit:
            application.save()
        
        return application


class ApplicationFilterForm(forms.Form):
    """申請検索フォーム"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '申請者名、承認者名、ファイル名、コメントで検索...',
            'id': 'searchInput',
            'autocomplete': 'off'
        }),
        label="検索"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
