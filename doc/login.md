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

`request` はおそらくブラウザから渡ってきた何かだと想像がつくのですが、 `user` という属性が使えるのは
何か Django のフレームワークなのだろうということにして、いったん置いておきます。

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

`login.html` は Django 用のテンプレートエンジンで処理されます。

https://docs.djangoproject.com/ja/5.2/topics/templates/#module-django.template

制御文とデータへの参照が含まれています。気になる点がいくつかあります。

### 外部への参照がある

```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ログイン - 持出承認システム</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
```

インターネットにつながらない環境で動かそうとした場合、この CDN への参照を何とかする必要があります。

### 知らない変数を見ている。

```html
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endif %}
```

おそらく、何かのオブジェクトの属性に `messages` という名前の配列があることが想像できます。
オブジェクトがあれば、という書き方に見えるので「何かのオブジェクト」の正体はあとで調べるとして
いまはこのブロックを無視します。

### FORM の POST 先がわからない

```html
        <form method="post">
            {% csrf_token %}
            <div class="form-floating mb-3">
                <input type="text" class="form-control" id="username" name="username" placeholder="ユーザー名" required>
                <label for="username"><i class="fas fa-user me-2"></i>ユーザー名</label>
            </div>
            
            <div class="form-floating mb-4">
                <input type="password" class="form-control" id="password" name="password" placeholder="パスワード" required>
                <label for="password"><i class="fas fa-lock me-2"></i>パスワード</label>
            </div>

            <div class="d-grid">
                <button type="submit" class="btn btn-primary btn-login">
                    <i class="fas fa-sign-in-alt me-2"></i>ログイン
                </button>
            </div>
        </form>
```

`form` タグに `action` の指定がありません。この場合、この HTML を表示した URL と全く同じ URL に POST されるようです。
ところで、この HTML のテンプレートは `django\users\templates\users\login.html` にありました。ブラウザに表示される
URL は `http://localhost:8000/users/login/` です。もし、 `http://localhost:8000/users/login/login.html` を
最初にアクセスしたらどうなるのでしょう。Django の 開発モードでは エラー画面が表示されます。

```
Using the URLconf defined in carry_out_approval.urls, Django tried these URL patterns, in this order:

[name='root']
  admin/
  users/ login/ [name='login']
  users/ logout/ [name='logout']
  users/ sessions/ [name='session-management']
  users/ me/ [name='current-user']
  users/ search/ [name='user-search']
  applications/
  api/audit/
  api/notifications/
  websocket-test/ [name='websocket-test']
  ^media/(?P<path>.*)$
  static/<path:path>
The current path, users/login/login.html, didn’t match any of these.
```

どこかで見たような気がします。以下の二つのファイルを確認しましょう。

- `django\carry_out_approval\urls.py` の `urlpatterns`

```python
urlpatterns = [
    path('', root_redirect, name='root'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),   ## ★
    path('applications/', include('applications.urls')),
    path('api/audit/', include('audit.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('websocket-test/', websocket_test, name='websocket-test'),
]
```

- `django\users\urls.py` の `urlpatterns`

```python
urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('sessions/', views.SessionManagementView.as_view(), name='session-management'),
    path('me/', views.CurrentUserView.as_view(), name='current-user'),
    path('search/', views.UserSearchView.as_view(), name='user-search'),
]
```

上記 ★ の部分が展開されて順にチェックした様子が見て取れます。最後のほうのパターンマッチ付きの部分は
Django のフレームワークが用意してくれているものでしょう。

パターンマッチではないので `login/` の最後のスラッシュまで厳密に比較しています。
でもアクセス先を `login` までにして、最後のスラッシュを抜いてもエラーは出ず、ログイン画面が出ます。

https://docs.djangoproject.com/ja/5.2/ref/settings/#append-slash

にある `APPEND_SLASH` が効いているようです。

> True に設定すると、リクエスト URL が URLconf 内のどのパターンにもマッチせず、/ で終わっていなかった場合に、末尾に / を追加した URL への HTTP リダイレクトを発行します。ただし、リダイレクトすると POST リクエストで送信するデータが失われることがあるので注意が必要です。


「注意が必要です」とあるので、なにかおかしくなったら思い出せるようにしておいて、次のステップは
 `http://localhost:8000/users/login/` への `POST` だということがわかりました。

先ほどの `django\users\urls.py` の `urlpatterns`

```python
    path('login/', views.LoginView.as_view(), name='login'),
```

にあるとおり、`views.LoginView` の `post` メソッドを見ます。

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
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_active:
                # Django標準のlogin関数を使用（自動的にセッションが作成される）
                login(request, user)
                
                next_url = request.GET.get('next', 'applications:kanban-board')
                return redirect(next_url)
            else:
                messages.error(request, 'ユーザー名またはパスワードが間違っています。')
        else:
            messages.error(request, 'ユーザー名とパスワードを入力してください。')
        
        return render(request, 'users/login.html')
```

ユーザ名とパスワードが想定したものでない場合、 `messages` オブジェクトに何かしています。
先ほどテンプレート内で見たものと関係あるのでしょうか。

`django\users\views.py` を純粋に Python のコードとしてみると、この名前自体は先頭で
`import` されています。

```python
from django.contrib import messages
```

これは
[メッセージフレームワーク](https://docs.djangoproject.com/ja/5.2/ref/contrib/messages/#module-django.contrib.messages)
で、 `django\carry_out_approval\settings.py` の `INSTALLED_APPS` と `MIDDLEWARE` の中で設定されているのが確認できます。

```python
INSTALLED_APPS = [
    ...
    'django.contrib.messages',
    ...
]

MIDDLEWARE = [
    ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    ...
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',   ## ★
            ],
        },
    },
]
```

そろそろ覚えることが多くなってきましたが、

> django-admin startproject によって生成されたデフォルトの settings.py は、メッセージ機能を有効にするために必要な設定を全て含んでいます

とあるので、設定のしかたは暗記しなくて良さそうです。「何かのオブジェクト」の正体がここで分かりました。

## 5. 認証処理 (`LoginView.post` → `authenticate()`)

まだ `django\users\views.py` の中から出ていけません。

```python
from django.contrib.auth import get_user_model, authenticate, login, logout
...
class LoginView(View):
    ...
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_active:
                # Django標準のlogin関数を使用（自動的にセッションが作成される）
                login(request, user)
```

とあるとおり、 `authenticate()` と `login()` もフレームワークの関数のようです。

ついにここで認証フレームワークについてドキュメントを確認する時が来ました。

[Django でのユーザー認証](https://docs.djangoproject.com/ja/5.2/topics/auth/#user-authentication-in-django)

> 認証関連をサポートする仕組みは、 django.contrib.auth 内の Django contrib モジュールとしてバンドルされています。デフォルトでは、必要な設定は django-admin startproject で生成される settings.py にすでに記述されています。

例によってセットアップ済みとのことですが、確認します。また `django\carry_out_approval\settings.py` です。

```python
INSTALLED_APPS = [
    ...
    'django.contrib.auth',
    'django.contrib.contenttypes',
    ...
]

MIDDLEWARE = [
    ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    ...
]
```

確かにあります。では、AI に作らせた LDAP で AD DS を参照する機能はどうやって呼び出すのでしょうか。

[認証バックエンドを指定する](https://docs.djangoproject.com/ja/5.2/topics/auth/customizing/#specifying-authentication-backends)

を見ると、定義はここです。また `django\carry_out_approval\settings.py` です。

```python
# Authentication backends (LDAP専用)
AUTHENTICATION_BACKENDS = [
    'users.backends.WindowsLDAPBackend',  # 優先
    'django.contrib.auth.backends.ModelBackend',  # Djangoデフォルト
]
```

**先頭が django じゃないものが来ました！**

`django\users\backends.py` を少しだけ見てみましょう。

```python
class WindowsLDAPBackend(ModelBackend):
    """
    Windows対応のLDAP認証バックエンド（ldap3使用）
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
            
        # まずDjangoデフォルトのユーザーを確認
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(username=username)
            if user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            pass
        
        # Djangoにユーザーが存在しない場合、LDAP認証を実行
        return self._authenticate_ldap3(username, password)
    
    def _authenticate_ldap3(self, username, password):
        """利用者資格情報のみで Active Directory に直接バインドして認証。

        ポリシー: 管理用サービスアカウントを保持しない。ユーザ入力の ID/パスワードで安全チャネル( LDAPS / StartTLS ) を優先的に使用。
        試行順序:
          1. ユーザが \\ もしくは @ を含めて入力した場合はその形式を最優先
          2. NTLM (DOMAIN\\username)
          3. UPN (username@upn_suffix)
        いずれも失敗したら認証失敗。
        """
```

LDAP の処理が始まりそうです。 LDAP の処理は別稿で確認することにして、
AI がまとめた処理のサマリをのこし、同じく AI がまとめた今後の拡張余地を見て
世の中のアプリケーションではどのような考慮が必要となっているのか覚えておきましょう。

## 典型的リクエスト遷移例 (未認証ユーザー)

1. GET `/` → 302 `/users/login/`
2. GET `/users/login/` → 200 (フォーム)
3. POST `/users/login/` (資格情報) → 302 `/applications/`
4. GET `/applications/` → 302 `/applications/my/board/` 例
5. GET `/applications/my/board/` → 200 (初期画面)

## 今後の拡張余地

- CSRF 対応強化（AJAX ログイン導入時）
- 連続失敗回数によるロック / reCAPTCHA
- MFA (TOTP / WebAuthn) 差し込み: `LoginView.post` の認証後 login() 直前に 2FA チェック
- Redis ChannelLayer 導入によるリアルタイム更新高速化

以上。

