# Django の起動からログインまで

Django を起動してからブラウザがルートURL `/` にアクセスし、ログインフォーム表示 → 資格情報送信 → 認証 → 最初の業務画面（カンバン系ボード）表示に至るまでのコード上の流れを整理します。

学習中なので、モジュールなのか、関数なのか、呼び出し可能オブジェクトなのかなど、厳密な理解はまだあいまいです。

たびたび出てきますが、「application」は、ソフトウェアアプリケーションではなく、「申請」が英訳されたものです。

---

## Django の起動

```powershell
cd django
uv run python manage.py runserver
```

で起動します。 `django\manage.py` に以下の記載があります。

```python
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carry_out_approval.settings')
```

次に見るのは `django\carry_out_approval\settings.py` モジュールです。

## 設定の読み込み

Djangoの設定がここに集中していますが、今見るべきは以下の設定です。

```python
ROOT_URLCONF = 'carry_out_approval.urls'
```

これにより、次に見るのは `django\carry_out_approval\urls.py` だとわかります。

## URL パターンでの振り分け

モジュール変数で `urlpatterns` が定義されています。

```python
urlpatterns = [
    path('', root_redirect, name='root'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('applications/', include('applications.urls')),
    path('api/audit/', include('audit.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('websocket-test/', websocket_test, name='websocket-test'),
]
```

最初のアクセスでは '' のはずなので、 `root_redirect` を見てみます。これは同じファイル内にあります。

```python
def root_redirect(request):
    """ルートURLから適切なページにリダイレクト"""
    if request.user.is_authenticated:
        return redirect('applications:kanban-board')
    else:
        return redirect('users:login')
```

Django で request.user という属性を使えるようにしているのは、
django.contrib.auth.middleware.AuthenticationMiddleware というミドルウェアの役割です。

このミドルウェアが、リクエストごとにセッション情報からユーザーを復元し、request.user にセットしています。
settings.py の MIDDLEWARE リストに通常含まれています。

[Web リクエストにおける認証](https://docs.djangoproject.com/ja/5.2/topics/auth/default/#authentication-in-web-requests)

`redirect()` の中の `applications:kanban-board` という表記は、 [URL パターンに名前をつける](https://docs.djangoproject.com/ja/5.2/topics/http/urls/#naming-url-patterns) あたりで説明してあるようですがまだ理解及ばず。すみません。

- applications は URL名前空間（include() で指定した app_name など）
- kanban-board は URLパターンの name 属性（path(..., name='kanban-board') で定義）

ということで、リダイレクト先の URL を名前を使って指定する、つまり URL が変わっても名前が変わってなければ修正範囲が限定されるしくみ、のようです。

実際のコード見てみると、 `django\carry_out_approval\urls.py` は


```python
urlpatterns = [
    path('', root_redirect, name='root'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    ...
    path('applications/', include('applications.urls')),
    ...
]
```

`django\users\utils.py` は

```python
app_name = 'users'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('sessions/', views.SessionManagementView.as_view(), name='session-management'),
    ...
]
```

`django\applications\urls.py` は

```python
app_name = 'applications'

urlpatterns = [
    ...
    path('my/', views.my_applications, name='my-applications-list'),
    ...
    path('', views.kanban_board, name='kanban-board'),
]
```

となっています。 [URLの名前空間とインクルードされた URLconfs](https://docs.djangoproject.com/ja/5.2/topics/http/urls/#url-namespaces-and-included-urlconfs) を見ると他の定義方法も書かれています。

今はすべてを理解できなくても、処理が

- `django\users\` のどこかにある `views.LoginView.as_view()` （ログインしてない場合）
- `django\applications\` のどこかにある `views.kanban_board` （ログインしていた場合）

のどちらかに移りそうだというところまでわかると思います。

前者は

  users パッケージの views モジュールの LoginView クラス の as_view() メソッドで、
  GET まはは POST 用のメソッドに振り分ける。

後者は

  appications パッケージの views モジュール の kanban_board 関数を呼び出す

という動きになりそうです。ここでは初回ログインの動きから追いたいので、
`django\users\views.py` を見ていきます。

## ログイン処理をほんとに表示するか

`LoginView` クラスは次の通りです。

```python
class LoginView(View):
    """ログイン画面とログイン処理"""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('applications:kanban-board')
        return render(request, 'users/login.html')
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            ...
        else:
            messages.error(request, 'ユーザー名とパスワードを入力してください。')
        
        return render(request, 'users/login.html')
```

二重アクセス防止の機能があるようで、既にログイン済みなら先ほど見た名前空間:名前と同じ `applications:kanban-board` でURLを決定してリダイレクトします。ログインしていないなら、ついに `render()` が呼ばれて、テンプレート内のファイル `django\users\templates\users\login.html` をレンダリングします。

---

## ログイン画面の表示



## 5. 認証処理 (`LoginView.post` → `authenticate()`)

1. POST パラメータ `username`, `password` 取得
2. `authenticate(request, username, password)` 呼び出し
3. `AUTHENTICATION_BACKENDS` 順に試行
   - `users.backends.WindowsLDAPBackend`
   - `django.contrib.auth.backends.ModelBackend`

### 5.1 WindowsLDAPBackend.authenticate

簡易フロー:

```python
user = UserModel.objects.get(username=username)  # 存在すればパスワードチェック
if user.check_password(password): return user
return self._authenticate_ldap3(username, password)
```

### 5.2 LDAP 認証 `_authenticate_ldap3`

- 接続設定: `settings.LDAP_SERVER_URL` などを参照
- ユーザー入力から複数候補（`DOMAIN\user`, `user@upn`, 入力そのまま など）を生成し順次 bind
- 成功時: `(sAMAccountName=username)` で検索 → entry 属性取得
- ローカル `User` が無ければ作成 (password は unusable)
- `UserProfile` を取得/作成し `ldap_dn`, `department_name`, `title`, `last_synced_at` 更新

### 5.3 失敗時

- 全候補 bind/search 失敗 → `None` 戻り → エラーメッセージ表示

---

## 6. セッション確立とリダイレクト

認証成功時:

```python
login(request, user)
next_url = request.GET.get('next', 'applications:kanban-board')
return redirect(next_url)
```

- `login()` により `request.session` に `_auth_user_id` 等が保存され `sessionid` クッキーが発行。
- 直後のレスポンスは 302。ブラウザが指定 URL を再要求。

### 6.1 セッションメタ付与

リダイレクト後最初のリクエストで `SessionManagementMiddleware` が:

```python
if request.user.is_authenticated and request.session.get('session_created') is None:
	request.session['session_created'] = timezone.now().isoformat()
	request.session['user_agent'] = HTTP_USER_AGENT
	request.session['ip_address'] = REMOTE_ADDR
```

---

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

## 8. エラーハンドリング / UX 補足

| ケース | 挙動 |
|--------|------|
| 資格情報不正 | `messages.error()` を設定し同じフォーム再表示 |
| 既ログイン状態で `/users/login/` | 即 `/applications/` へリダイレクト |
| 未認証で保護URLアクセス | Django が 302 `/users/login/?next=...` へ | 

`messages` フレームワークによりテンプレート側でエラーや成功メッセージを表示可能。

---

## 9. 重要な設定値再掲

| 設定 | 値 | 用途 |
|------|----|------|
| `LOGIN_URL` | `/users/login/` | 未認証アクセス誘導先 |
| `LOGIN_REDIRECT_URL` | `/applications/` | 認証後デフォルト遷移先 |
| `AUTHENTICATION_BACKENDS` | WindowsLDAPBackend, ModelBackend | 認証順序 |
| `SESSION_COOKIE_AGE` | 86400 (24h) | セッション寿命 |
| `SESSION_SAVE_EVERY_REQUEST` | True | アイドル延長 |

---

## 10. 典型的リクエスト遷移例 (未認証ユーザー)

1. GET `/` → 302 `/users/login/`
2. GET `/users/login/` → 200 (フォーム)
3. POST `/users/login/` (資格情報) → 302 `/applications/`
4. GET `/applications/` → 302 `/applications/my/board/` 例
5. GET `/applications/my/board/` → 200 (初期画面)

---

## 11. 今後の拡張余地

- CSRF 対応強化（AJAX ログイン導入時）
- 連続失敗回数によるロック / reCAPTCHA
- MFA (TOTP / WebAuthn) 差し込み: `LoginView.post` の認証後 login() 直前に 2FA チェック
- Redis ChannelLayer 導入によるリアルタイム更新高速化

---

以上。

