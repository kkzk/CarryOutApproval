from django import forms
from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
import json


class SearchableCheckboxSelectMultiple(Widget):
    """検索機能付きチェックボックス選択ウィジェット"""
    
    def __init__(self, choices=(), attrs=None):
        if attrs is None:
            attrs = {}
        attrs.setdefault('class', 'searchable-checkbox-widget')
        super().__init__(attrs)
        self.choices = choices
    
    def format_value(self, value):
        """値をフォーマット"""
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        return [str(v) for v in value]
    
    def render(self, name, value, attrs=None, renderer=None):
        """ウィジェットを描画"""
        if attrs is None:
            attrs = {}
        
        # 選択肢を準備
        choices = []
        for choice_value, choice_label in self.choices:
            choices.append({
                'value': str(choice_value),
                'label': str(choice_label),
                'selected': str(choice_value) in self.format_value(value)
            })
        
        # HTMLを直接生成
        widget_id = attrs.get('id', f'id_{name}')
        search_id = f'{widget_id}_search'
        container_id = f'{widget_id}_container'
        
        html = f'''
        <div class="searchable-checkbox-container" id="{container_id}">
            <div class="search-box mb-3">
                <input type="text" 
                       class="form-control" 
                       id="{search_id}"
                       placeholder="所属名で検索..."
                       autocomplete="off">
                <small class="form-text text-muted">いずれかの単語を含む所属を検索できます</small>
            </div>
            <div class="choices-container" style="max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 5px;">
        '''
        
        for choice in choices:
            checked = 'checked' if choice['selected'] else ''
            html += f'''
                <div class="form-check choice-item" data-search-text="{choice['label'].lower()}">
                    <input class="form-check-input" 
                           type="checkbox" 
                           name="{name}" 
                           value="{choice['value']}" 
                           id="{widget_id}_{choice['value']}"
                           {checked}>
                    <label class="form-check-label" for="{widget_id}_{choice['value']}">
                        {choice['label']}
                    </label>
                </div>
            '''
        
        html += '''
            </div>
        </div>
        <script>
        (function() {
            const searchInput = document.getElementById("''' + search_id + '''");
            const container = document.getElementById("''' + container_id + '''");
            const choiceItems = container.querySelectorAll('.choice-item');
            
            searchInput.addEventListener('input', function() {
                const searchQuery = this.value.toLowerCase().trim();
                
                if (searchQuery === '') {
                    // 検索語が空の場合は全て表示
                    choiceItems.forEach(function(item) {
                        item.style.display = 'block';
                    });
                    return;
                }
                
                // スペースで区切って複数キーワードに分割
                const searchTerms = searchQuery.split(/\\s+/).filter(term => term.length > 0);
                
                choiceItems.forEach(function(item) {
                    const searchText = item.getAttribute('data-search-text');
                    
                    // いずれかのキーワードが含まれていれば表示（OR検索）
                    const isVisible = searchTerms.some(term => searchText.includes(term));
                    
                    item.style.display = isVisible ? 'block' : 'none';
                });
            });
            
            // 全選択/全解除のための機能（オプション）
            const selectAllBtn = document.createElement('button');
            selectAllBtn.type = 'button';
            selectAllBtn.className = 'btn btn-sm btn-outline-secondary me-2';
            selectAllBtn.textContent = '全選択';
            selectAllBtn.addEventListener('click', function() {
                const visibleCheckboxes = container.querySelectorAll('.choice-item:not([style*="display: none"]) input[type="checkbox"]');
                visibleCheckboxes.forEach(cb => cb.checked = true);
            });
            
            const deselectAllBtn = document.createElement('button');
            deselectAllBtn.type = 'button';
            deselectAllBtn.className = 'btn btn-sm btn-outline-secondary';
            deselectAllBtn.textContent = '全解除';
            deselectAllBtn.addEventListener('click', function() {
                const visibleCheckboxes = container.querySelectorAll('.choice-item:not([style*="display: none"]) input[type="checkbox"]');
                visibleCheckboxes.forEach(cb => cb.checked = false);
            });
            
            const searchBox = container.querySelector('.search-box');
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'mt-2';
            buttonContainer.appendChild(selectAllBtn);
            buttonContainer.appendChild(deselectAllBtn);
            searchBox.appendChild(buttonContainer);
        })();
        </script>
        '''
        
        return mark_safe(html)
    
    def value_from_datadict(self, data, files, name):
        """フォームデータから値を取得"""
        if hasattr(data, 'getlist'):
            # type: ignore because mypy doesn't know about QueryDict's getlist method
            return data.getlist(name)  # type: ignore
        else:
            # fallback for dict-like objects
            values = data.get(name)
            if values is None:
                return []
            if not isinstance(values, (list, tuple)):
                return [values]
            return list(values)


class SearchableModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    """検索機能付きモデル複数選択フィールド"""
    
    widget = SearchableCheckboxSelectMultiple
    
    def __init__(self, queryset, **kwargs):
        # ウィジェットの引数を分離
        widget_attrs = kwargs.pop('widget_attrs', {})
        super().__init__(queryset, **kwargs)
        
        # 選択肢をウィジェットに設定
        if queryset is not None:
            choices = [(obj.pk, str(obj)) for obj in queryset.all()]
        else:
            choices = []
        self.widget = SearchableCheckboxSelectMultiple(choices=choices, attrs=widget_attrs)
