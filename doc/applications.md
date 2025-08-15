## 7. アプリ最初の画面判定 (`applications.views.kanban_board`)

`/applications/` は `kanban_board` にマッピング。

```python
has_approvals = Application.objects.filter(approver=request.user.username).exists()
has_applications = Application.objects.filter(applicant=request.user.username).exists()
view_mode = request.GET.get('view')
if view_mode == 'approval' or (has_approvals and not has_applications):
	redirect('applications:approval-board')
else:
	redirect('applications:my-applications-board')
```

- 役割状況に応じて申請者 / 承認者向けボードへ再リダイレクト。
- 最終 200 応答で HTML を返す。

---
