このプロジェクトは開発・学習用のサンプルアプリケーションです。

# ファイル持出承認システム

ファイルを外部に持ち出す前に上司の承認を受けるワークフローを想定したWebアプリケーションです。
バックエンドとフロントエンドが一つのDjangoアプリケーションに統合されており、HTMXを活用したモダンなユーザーインターフェースを提供します。

## システム概要

### 主な機能
- **申請者**: ドラッグ&ドロップでファイルをアップロードし、承認者を指定して持出申請を作成
- **承認者**: カンバンボードでドラッグ&ドロップによる直感的な承認・拒否操作
- **管理者**: Django管理画面での全申請管理、監査ログ確認、証跡管理

### 特徴
- **リアルタイム通知**: WebSocketによるリアルタイム通知システム
- **カンバンボード**: 申請状況を視覚的に管理（承認待ち・承認済み・拒否）
- **リアルタイム更新**: ページリロード不要のAjax通信とWebSocket連携
- **監査ログ**: 全ての操作を記録し、証跡管理を実現

## 技術スタック

### バックエンド & フロントエンド (統合型アーキテクチャ)
- **Django 5.2.5** - Pythonベースの高機能Webフレームワーク
- **Django REST Framework 3.16.1** - RESTful API開発フレームワーク
- **Django Templates** - サーバーサイドレンダリングエンジン
- **HTMX 1.8.4** - モダンなAjax通信ライブラリ（SPAライクな操作感を実現）
- **Bootstrap 5.1.3** - レスポンシブUIフレームワーク
- **Sortable.js** - ドラッグ&ドロップ機能ライブラリ
- **SQLite** (開発用) / **PostgreSQL** (本番推奨)
- **Pillow 11.3.0** - 画像・ファイル処理ライブラリ
- **python-decouple 3.8** - 設定管理ライブラリ

### リアルタイム通信・通知システム
- **Django Channels 4.2.0** - WebSocket・非同期通信フレームワーク
- **Daphne 4.1.2** - ASGI対応Webサーバー（WebSocket処理）

## 主要機能

### 申請機能
- **直感的なファイルアップロード**: ドラッグ&ドロップ対応のモダンなファイル選択
- **承認者検索・選択**: リアルタイム検索による承認者選択
- **持出理由入力**: 詳細な理由とコメントの記録
- **申請履歴管理**: 自分の申請一覧表示と進捗確認
- **カンバンボード**: 視覚的な申請状況管理

### 承認機能
- **ドラッグ&ドロップ承認**: カンバンボードでの直感的な状況変更
- **申請詳細確認**: モーダルウィンドウでの詳細情報表示
- **ファイルプレビュー**: アップロードされたファイルの確認
- **承認・拒否理由入力**: 詳細なコメント記録

### 管理・監査機能
- **Django管理画面**: 管理者向けの包括的な管理インターフェース
- **監査ログシステム**: 全操作の自動記録と追跡
- **証跡管理**: 申請から承認までの完全な履歴
- **ユーザー管理**: 組織階層に基づくユーザー管理

### ユーザーエクスペリエンス
- **リアルタイム通知**: WebSocketによる即座の通知更新
- **リアルタイム更新**: ページリロード不要のスムーズな操作
- **プログレッシブ・エンハンスメント**: JavaScript無効環境でも基本機能利用可能

## セットアップ方法

### 必要な環境
- **Python 3.8-3.13** (3.13推奨)
- **[uv](https://docs.astral.sh/uv/)** (高速パッケージマネージャー、推奨) または pip

### Windows環境での前提条件
- **Visual Studio Build Tools** または **Visual Studio Community** （Pillowライブラリのコンパイル用）
- **Redis Server** （WebSocket・リアルタイム通知用、開発時はオプション）

### 簡単セットアップ・起動（Windows PowerShell）

```powershell
# 初回セットアップ
.\setup-django.ps1

# 開発サーバー起動（通常のDjangoサーバー）
.\start-django.ps1

# WebSocket対応ASGIサーバー起動（Daphne）
.\start-daphne.ps1
```

### 手動セットアップ

```powershell
# uvプロジェクト管理を使用（推奨）
uv sync

# Djangoディレクトリに移動
cd django

# データベースマイグレーション
uv run python manage.py migrate

# スーパーユーザー作成
uv run python manage.py createsuperuser

# 静的ファイル収集
uv run python manage.py collectstatic --noinput

# サーバー起動
uv run python manage.py runserver 8000

# WebSocket対応ASGIサーバー起動（推奨）
uv run python -m daphne -p 8000 carry_out_approval.asgi:application
```

### LDAP認証環境のセットアップ

#### 1. LDAP対応ライブラリのインストール
```powershell
# LDAPライブラリを含む依存関係をインストール
uv sync --extra ldap
```

#### 2. Active Directory設定（本番環境）
`django/carry_out_approval/settings.py`を編集：

```python
# Windows対応LDAP Configuration
LDAP_SERVER = 'ldap://your-domain-controller.yourdomain.com:389'
LDAP_DOMAIN = 'yourdomain.com'  # Active Directoryドメイン名
LDAP_SEARCH_BASE = 'DC=yourdomain,DC=com'  # 検索ベースDN
LDAP_SERVICE_USER = 'serviceaccount@yourdomain.com'  # サービスアカウント
LDAP_SERVICE_PASSWORD = 'your_service_password'  # サービスアカウントパスワード
```

#### 3. LDAP認証バックエンドの選択
```python
# 本番環境（Active Directory使用）
AUTHENTICATION_BACKENDS = [
    'users.backends.WindowsLDAPBackend',  # 優先
    'django.contrib.auth.backends.ModelBackend',  # Djangoデフォルト
]
```

```
python -m daphne -p 8000 carry_out_approval.asgi:application
```

## Active Directory (Windows Server 2025) の LDAP 署名既定変更への対応

Windows Server 2025 のドメイン コントローラー (DC) では、従来のポリシー設定 (LDAPServerIntegrity / LdapEnforceChannelBinding) だけではなく、
新しいポリシー / レジストリ `ドメイン コントローラー: LDAP サーバの署名要件の適用 (ldapserverenforceintegrity)` が導入され、
既定 (値なし / 有効) 状態でも LDAP 署名 (署名 / 封印, integrity 保護) が要求される仕様になりました。

### 影響概要
- 2025 DC では平文 389/TCP の SIMPLE / NTLM バインドが、保護なし (署名 / TLS 無し) の場合 `strongerAuthRequired (resultCode=8)` を返すケースが増える
- 従来ポリシーを「なし」にしても、新ポリシーが有効 (未定義 = 1) なら平文バインドは拒否される
- 新ポリシーを「無効 (0)」に設定した場合にのみ従来ポリシーの値が再び意味を持つ
- ポリシーを一度 無効→未定義 に戻しても “既定(有効)” ではなく “無効(0)” に保持される挙動に注意 (検証時の再設定漏れ防止)

### 代表的な LDAP 応答コードと意味
| コード | AD サブコード例 | 意味 | 対処の主眼 |
|--------|----------------|------|------------|
| 8 (strongerAuthRequired) | message に "The server requires binds to turn on integrity checking" | 保護 (署名/封印 または TLS) 不足 | StartTLS / LDAPS を有効にする |
| 49 (invalidCredentials) data 52e | AcceptSecurityContext error | ユーザー/パスワード不一致 | 資格情報再確認 |
| 49 data 775 | アカウント ロックアウト | ロック解除 |
| 49 data 532 | パスワード期限切れ | パスワード更新 |

### 推奨構成
運用では (A) LDAPS 直 (636/TCP) か (B) StartTLS を必須化し、平文 fallback は限定的な検証時のみ許可。

#### 設定例 (環境変数 / settings.py)
```python
# LDAPS 利用 (証明書がバインド済みの場合)
LDAP_SERVER_URL = "ldaps://dc01.example.com:636"
LDAP_USE_SSL = True               # 直接 LDAPS
LDAP_FORCE_STARTTLS = False       # LDAPS 利用時は不要

# StartTLS 利用 (389 → TLS へ昇格)
LDAP_SERVER_URL = "ldap://dc01.example.com:389"
LDAP_USE_SSL = False
LDAP_FORCE_STARTTLS = True        # バインド前に StartTLS

# 診断用一時緩和 (本番禁止)
LDAP_ALLOW_PLAIN_FALLBACK = True  # StartTLS/LDAPS 失敗時に平文を試す (一時 / 開発のみ)
LDAP_TLS_INSECURE = True          # 証明書検証を一時的に無効 (自己署名テスト)
```
`LDAP_TLS_INSECURE` は自己署名/未信頼証明書で一時診断する際のみ。成功後は **必ず False** に戻し、CA 配布 or 正式証明書を導入する。

### 証明書 (LDAPS) 有効化の代表パス
1. AD CS (Enterprise CA) を構築 → DC が自動で正しい証明書を取得 (サブジェクト = FQDN)
2. 既存/private CA や 公開 CA から DC FQDN 用サーバ証明書 (Server Authentication) を発行し、DC の 個人/コンピュータ 証明書ストアへ配置
3. サービス再起動または数分待機後、`ldp.exe` で 636/TCP に接続確認

### トラブル発生時の診断ステップ
1. FQDN で接続しているか (IP は Kerberos/SPN 解決不可 → 署名条件未達になる要因)
2. StartTLS 成功可否 (失敗なら証明書 / ファイアウォール / 中間装置を確認)
3. アプリログで code=8 → TLS 化後に code=49 (52e) に変化したら “保護問題解消”
4. DC Event Viewer (Directory Service) で 2889 / 3039 / LDAP 署名関連イベント確認
5. GPO: 新ポリシー `ドメイン コントローラー: LDAP サーバの署名要件の適用` の状態 (無効=0 のみ平文バインド許容)

### 本アプリケーション固有の調整ポイント
- カスタム認証バックエンド `users.backends.WindowsLDAPBackend` は複数資格形式 (DOMAIN\\user / user@UPN) を順次試行
- `strongerAuthRequired` を検出したら StartTLS/LDAPS を有効にして再試行することで無駄な平文再試行を減らせる (将来自動リトライ実装余地)
- デバッグログで `code`, `desc`, `message` を出力しているため問題判別が高速 (8 → 49 への遷移を監視)
- 運用投入時は: `LDAP_ALLOW_PLAIN_FALLBACK=False`, `LDAP_TLS_INSECURE=False` に固定する

### セキュリティ留意事項
- 平文 LDAP を恒久利用しない (資格情報盗聴リスク + 署名必須化で将来再び失敗)
- `LDAP_TLS_INSECURE=True` は一時調査用。長期放置禁止
- 監査ログやアプリログにパスワードを出力しない (現在出していない設計)

### 迅速な確認チェックリスト (運用前)
| 項目 | 確認 | 備考 |
|------|------|------|
| FQDN で接続 | ✅/❌ | IP ではなく dc01.example.com |
| LDAPS or StartTLS 成功 | ✅/❌ | 証明書信頼済み |
| 平文 fallback 無効 | ✅/❌ | LDAP_ALLOW_PLAIN_FALLBACK=False |
| 証明書検証有効 | ✅/❌ | LDAP_TLS_INSECURE=False |
| バインド成功後 code=49/52e 切替確認 | ✅/❌ | 保護確立後は純粋な資格判定 |
| 新ポリシー状態把握 | ✅/❌ | 必要なら無効化 → 診断後再度有効化 |

参考: ブログ記事 *"Windows Server 2025 の Active Directory では LDAP 署名が既定で必須に"* (要旨のみ反映 / 詳細は原文参照)。

### Active Directory テストデータ (OU/ユーザ) 登録コマンド

開発/検証用に Active Directory に OU / ユーザを一括登録する管理コマンドを追加しています。

```
uv run python manage.py register_ad_data --file users/management/data/ldap_testdata.json --dry-run --debug-log
```

主なオプション:
- `--file/-f` JSON ファイル (既定: `users/management/data/ldap_testdata.json`)
- `--default-password` JSON 内で `userPassword` 未指定ユーザの既定パスワード
- `--dry-run` 変更を加えず計画のみ表示 (本番前に必須)
- `--debug-log` 詳細ログ (DEBUG)

必要設定 (settings.py または 環境変数 / .env):
- `LDAP_SERVER_URL` (例: `ldaps://dc01.example.com:636` または `ldap://dc01.example.com:389`)
- `LDAP_SEARCH_BASE` (例: `DC=example,DC=com`)
- `LDAP_SERVICE_USER` (サービスアカウント DN / UPN / DOMAIN\\user いずれか)
- `LDAP_SERVICE_PASSWORD`

後方互換で旧キーも利用可: `AD_SERVER`, `AD_BASE_DN`, `AD_ADMIN_DN`, `AD_ADMIN_PASSWORD`, `AD_USE_SSL`, `AD_STARTTLS`。

実行例 (本番反映):
```
uv run python manage.py register_ad_data -f users/management/data/ldap_testdata.json --default-password TempPassw0rd! 
```

注意:
1. OU / ユーザは既に存在する場合はスキップ (冪等)
2. `--dry-run` で差分を必ず確認
3. サービスアカウントには OU/ユーザ作成権限が必要
4. パスワードは後から期限付き変更を促す設計 (pwdLastSet=0)

旧スクリプト群は `register_testuser/` で廃止済みです。データファイルは `users/management/data/ldap_testdata.json` へ移動しました。

#### AD テストユーザ削除コマンド

登録済みテストユーザを削除する管理コマンド:

```
uv run python manage.py delete_ad_users --dry-run
uv run python manage.py delete_ad_users --users user001,user002 --debug-log
uv run python manage.py delete_ad_users --users user003 --users user004
```

オプション:
- `--users` 指定が無い場合は `user001..user005` を対象
- `--dry-run` 実行計画のみ表示 (推奨)
- `--debug-log` 詳細ログ

DN をハードコードせず `sAMAccountName` 検索で取得するため OU 移動後でも削除可能です。

## アクセス方法

- **カンバンボード**: http://localhost:8000
- **Django管理画面**: http://localhost:8000/admin
- **WebSocket接続テスト**: http://localhost:8000/websocket-test
- **REST API**: http://localhost:8000/api
- **API ドキュメント**: http://localhost:8000/api/ (DRFブラウザ表示)

**注意**: リアルタイム通知機能を使用するには、Daphne（ASGIサーバー）での起動が必要です。

## テストユーザー

開発用に以下のテストユーザーが利用できます。

**想定する OU の構造**

```
DEPT1000/
└── DEPT1000100/
```

**テストユーザ**

| ユーザーID | パスワード | 名前     | 所属コード(OU名) | 役割                           |
| ---------- | ---------- | -------- | ---------------- | ------------------------------ |
| admin      | admin123   | 管理者   |                  | スーパーユーザー(OU内には不在) |
| user001    | pass001    | 田中太郎 | DEPT1000100      | 一般ユーザー                   |
| user002    | pass002    | 佐藤花子 | DEPT1000100      | 一般ユーザー                   |
| user003    | pass003    | 鈴木一郎 | DEPT1000         | 上位ユーザー                   |

## ファイル構成

```
CarryOutApproval/
├── .venv/                   # Python仮想環境
├── django/                  # Django統合アプリケーション
│   ├── carry_out_approval/  # Django プロジェクト設定
│   │   ├── settings.py      # Django設定
│   │   ├── urls.py          # URLルーティング
│   │   ├── wsgi.py          # WSGI設定
│   │   └── asgi.py          # ASGI設定（WebSocket対応）
│   ├── applications/        # 申請管理アプリ
│   │   ├── models.py        # 申請・承認モデル
│   │   ├── views.py         # ビュー（Web + API）
│   │   ├── serializers.py   # API シリアライザー
│   │   ├── admin.py         # 管理画面設定
│   │   ├── urls.py          # URLルーティング
│   │   ├── templates/       # HTMLテンプレート
│   │   │   └── applications/
│   │   │       ├── kanban_board.html
│   │   │       ├── application_card.html
│   │   │       └── application_detail_modal.html
│   │   └── static/          # 静的ファイル
│   │       └── applications/
│   │           ├── css/
│   │           └── js/
│   ├── users/               # ユーザー管理アプリ
│   │   ├── models.py        # ユーザーモデル
│   │   ├── views.py         # ユーザーAPI
│   │   ├── serializers.py   # ユーザーシリアライザー
│   │   ├── admin.py         # ユーザー管理画面
│   │   ├── middleware.py    # カスタムセッション管理
│   │   └── management/      # 管理コマンド
│   │       └── commands/
│   │           └── create_test_users.py
│   ├── audit/               # 監査ログアプリ
│   │   ├── models.py        # 監査ログモデル
│   │   ├── views.py         # 監査ログAPI
│   │   └── admin.py         # 監査ログ管理画面
│   ├── notifications/       # リアルタイム通知アプリ
│   │   ├── models.py        # 通知モデル
│   │   ├── views.py         # 通知API
│   │   ├── consumers.py     # WebSocketコンシューマー
│   │   ├── routing.py       # WebSocketルーティング
│   │   ├── services.py      # 通知サービス
│   │   └── serializers.py   # 通知シリアライザー
│   ├── templates/           # 共通テンプレート
│   │   ├── base.html        # ベーステンプレート
│   │   └── websocket_test.html # WebSocket接続テスト
│   ├── storage/             # ファイルストレージ
│   │   ├── uploads/         # アップロードファイル
│   │   └── approved/        # 承認済みファイル
│   ├── requirements.txt     # Python依存関係
│   ├── manage.py            # Django管理スクリプト
│   ├── test_notifications.py # 通知システムテスト
│   └── db.sqlite3           # SQLiteデータベース
├── setup-django.ps1         # セットアップスクリプト
├── start-django.ps1         # Django起動スクリプト
├── start-daphne.ps1         # Daphne起動スクリプト（WebSocket対応）
└── README.md                # このファイル
```

## カンバンボードの使い方

### 基本操作
1. **ログイン**: http://localhost:8000 でテストユーザーでログイン
2. **申請状況確認**: 3つのカラムで申請状況を視覚的に管理
   - **承認待ち (Pending)**: 新規申請や承認待ちの申請
   - **承認済み (Approved)**: 承認された申請
   - **拒否 (Rejected)**: 却下された申請
3. **ドラッグ&ドロップ操作**: 申請カードをドラッグして異なるカラムに移動
4. **申請詳細確認**: カードクリックで詳細情報をモーダル表示
5. **新規申請作成**: 「新しい申請」ボタンまたはキーボードショートカット

### 高度な機能
- **フィルタリング**: 申請者、承認者、期間による絞り込み
- **検索機能**: キーワードによる申請検索
- **ソート機能**: 作成日、更新日、申請者名による並び替え
- **バッチ操作**: 複数選択による一括操作

## テスト・動作確認

### Webアプリケーションテスト

#### 1. 基本的な動作確認
```bash
# Djangoサーバー起動
uv run python manage.py runserver 8000

# ブラウザで以下にアクセス
# http://localhost:8000/users/login/
```

#### 2. WebSocket・リアルタイム通知テスト
```bash
# ASGIサーバー（WebSocket対応）で起動
uv run python -m daphne -p 8000 carry_out_approval.asgi:application

# WebSocket接続テスト
# http://localhost:8000/websocket-test/
```

#### 3. 通知システムテスト
```bash
# 通知システムの動作テスト
uv run python test_notifications.py
```

### API エンドポイントテスト

#### 1. Django REST Framework ブラウザ
```bash
# サーバー起動後、ブラウザで以下にアクセス
# http://localhost:8000/api/
```

#### 2. カール（curl）コマンドでのテスト
```bash
# ユーザー情報取得（要認証）
curl -H "Content-Type: application/json" \
     -H "Authorization: Session <session_id>" \
     http://localhost:8000/api/users/me/

# 申請一覧取得
curl -H "Content-Type: application/json" \
     -H "Authorization: Session <session_id>" \
     http://localhost:8000/api/applications/
```

### トラブルシューティング

#### LDAP認証関連
1. **ldap3ライブラリが見つからない**
   ```bash
   # LDAPライブラリをインストール
   uv sync --extra ldap
   ```

2. **Active Directory接続エラー**
   - `settings.py`のLDAP設定を確認
   ```python
   LDAP_SERVER = 'ldap://your-domain-controller.yourdomain.com:389'
   LDAP_DOMAIN = 'yourdomain.com'
   LDAP_SEARCH_BASE = 'DC=yourdomain,DC=com'
   ```

#### WebSocket接続エラー
1. **WebSocket接続失敗**
   ```bash
   # Daphneサーバーで起動（runserverではなく）
   uv run python -m daphne -p 8000 carry_out_approval.asgi:application
   ```

2. **Redis接続エラー**
   - 開発環境では InMemoryChannelLayer を使用（Redis不要）
   - 本番環境では Redis の起動を確認

#### データベース関連
1. **マイグレーションエラー**
   ```bash
   # マイグレーションをリセット
   uv run python manage.py migrate --fake applications zero
   uv run python manage.py migrate
   ```

2. **テストデータの作成**
   ```bash
   # スーパーユーザー作成
   uv run python manage.py createsuperuser

   # テストユーザー作成（カスタムコマンド）
   uv run python manage.py create_test_users
   ```

### パフォーマンステスト

#### 1. 大量データテスト
```python
# Django Shell でテストデータ生成
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from applications.models import Application
>>> # 大量申請データの作成スクリプト実行
```

#### 2. 同時接続テスト
```bash
# Apache Bench でのロードテスト例
ab -n 100 -c 10 http://localhost:8000/
```

## API エンドポイント

### 認証・ユーザー管理
- `GET /api/users/me/` - 現在のログインユーザー情報取得
- `GET /api/users/search/` - ユーザー検索（承認者選択用）

### 申請管理 (Applications)
- `GET /api/applications/` - 申請一覧（権限に応じてフィルタリング）
- `POST /api/applications/` - 新規申請作成
- `GET /api/applications/{id}/` - 申請詳細取得
- `PUT /api/applications/{id}/` - 申請情報更新
- `PATCH /api/applications/{id}/update_status/` - 申請状態更新（承認・拒否）
- `DELETE /api/applications/{id}/` - 申請削除
- `GET /api/applications/my/` - 自分の申請一覧
- `GET /api/applications/pending/` - 承認待ち申請一覧

### 監査ログ (Audit)
- `GET /api/audit/` - 監査ログ一覧（管理者権限必要）
- `GET /api/audit/{id}/` - 監査ログ詳細

### 通知システム (Notifications)
- `GET /api/notifications/` - 通知一覧（ログインユーザー宛て）
- `GET /api/notifications/{id}/` - 通知詳細
- `PATCH /api/notifications/{id}/mark_read/` - 通知を既読に設定
- `POST /api/notifications/mark-all-read/` - 全通知を既読に設定

### WebSocket エンドポイント
- `ws://localhost:8000/ws/notifications/{user_id}/` - リアルタイム通知受信

### ファイル管理
- `POST /api/applications/upload/` - ファイルアップロード
- `GET /api/applications/{id}/download/` - 承認済みファイルダウンロード

### API仕様
- **認証方式**: Django Session Authentication
- **データ形式**: JSON
- **エラーレスポンス**: HTTP標準ステータスコード + 詳細メッセージ
- **ページネーション**: Django REST Framework標準形式

## 設定

### 環境変数（django/.env）

```env
# Django settings
SECRET_KEY=django-insecure-p-&2w+m!4-8zzo($a755#8uz0mv@u5+$$zx*gqof+8m4j-#+*=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3

# WebSocket & Redis Settings（本番環境用）
REDIS_URL=redis://localhost:6379/0
CHANNEL_LAYERS_BACKEND=channels_redis.core.RedisChannelLayer

# Mock User API URL (for development)
MOCK_USER_API_URL=http://localhost:8001/api/users
```

**注意**: 開発環境では、Redisがなくてもインメモリチャンネルレイヤーで動作します。

### Django設定のカスタマイズ

Django設定は `django/carry_out_approval/settings.py` で管理されています：

- **データベース**: SQLite（開発用）、PostgreSQL（本番用）
- **ファイルストレージ**: ローカルストレージ（`storage/`ディレクトリ）
- **静的ファイル**: `staticfiles/`ディレクトリに収集
- **テンプレート**: Django Templates + HTMX
- **認証**: Django組み込み認証システム

## アーキテクチャの特徴

#### HTMXの採用理由
- **軽量性**: 重いJavaScriptフレームワークが不要
- **学習コストの低さ**: HTMLベースのシンプルな記法
- **サーバー親和性**: Django Templatesとの自然な統合
- **プログレッシブエンハンスメント**: JavaScript無効環境でも動作

#### Django Channels + WebSocketの採用理由
- **リアルタイム性**: 申請状況の即座な通知
- **双方向通信**: サーバーからクライアントへのプッシュ通知
- **Django統合**: 既存の認証システムとの自然な連携
- **スケーラブル**: Redis によるチャンネルレイヤーでの水平拡張対応

#### Bootstrap 5の採用理由
- **レスポンシブ対応**: モバイルファーストデザイン
- **豊富なコンポーネント**: 迅速なUI開発
- **カスタマイゼーション**: 企業ブランディングへの対応
- **アクセシビリティ**: WCAG準拠のUI要素

#### Django統合アーキテクチャ
- **単一責任の原則**: アプリケーションごとの機能分離
- **RESTfulAPI**: フロントエンド・バックエンド分離の準備
- **テンプレートエンジン**: SEO対策とサーバーサイドレンダリング
- **ORM活用**: データベース抽象化による可搬性

### パフォーマンス最適化

- **静的ファイル圧縮**: CSS/JSの最小化
- **データベース最適化**: インデックス活用とクエリ最適化
- **キャッシュ戦略**: Django キャッシュフレームワーク対応
- **CDN対応**: 静的ファイルの高速配信準備済み

## トラブルシューティング

### Python依存関係のインストールエラー

#### Pillowのビルドエラー
```
Failed to build 'pillow'
```
**対処法:**
1. Visual Studio Build Toolsをインストール
2. `uv pip install pillow` を単体で試行

#### uvコマンドが見つからない場合
```powershell
# uvをインストール
pip install uv

# または従来のpipを使用
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r django\requirements.txt
```

### Django関連エラー

#### マイグレーションエラー
```powershell
# マイグレーションをリセット
Remove-Item django\db.sqlite3
cd django
python manage.py migrate
python manage.py create_test_users
```

#### 管理画面にアクセスできない
```powershell
# スーパーユーザーを作成
cd django
python manage.py createsuperuser

# またはテストユーザーを使用
# ユーザー名: admin
# パスワード: admin123
```

#### 静的ファイルが読み込まれない
```powershell
cd django
python manage.py collectstatic --noinput
```

### 起動時のエラー

#### ポート8000が既に使用されている
```powershell
# プロセスを確認・終了
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

#### 仮想環境の問題
```powershell
# 仮想環境を再作成
Remove-Item -Recurse -Force .venv
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r django\requirements.txt
```

### WebSocket・リアルタイム通知のエラー

#### WebSocket接続エラー
```
WebSocket connection failed
```
**対処法:**
1. Daphne（ASGIサーバー）で起動していることを確認
2. `.\start-daphne.ps1` または手動で `python -m daphne -p 8000 carry_out_approval.asgi:application`

#### Redis接続エラー（本番環境）
```
Connection refused to Redis server
```
**対処法:**
1. Redisサーバーが起動していることを確認
2. 開発環境ではインメモリチャンネルレイヤーを使用（Redis不要）

#### 通知が届かない
1. ログイン状態を確認
2. WebSocket接続テストページで動作確認: http://localhost:8000/websocket-test
3. ブラウザの開発者ツールでWebSocket接続エラーを確認

## 今後の開発方針

### 近期実装予定
- **通知システム強化**: ✅ **完了** - WebSocketベースのリアルタイム通知
- **ファイルプレビュー強化**: PDF、画像の直接プレビュー機能
- **承認フロー拡張**: 複数段階承認、条件分岐承認
- **メール通知**: 重要な申請状況変更時のメール通知
- **モバイルアプリ**: PWA対応による快適なモバイル体験

### 中長期ロードマップ
- **高度なレポート機能**: グラフィカルな統計レポート
- **ワークフロー自動化**: 条件に基づく自動承認・振り分け
- **外部システム連携**: Active Directory、LDAP統合
- **AI活用**: 自然言語処理による申請内容分析

### セキュリティ・コンプライアンス強化
- **2要素認証**: TOTP、SMS認証の実装
- **ファイル暗号化**: アップロード・保存時の自動暗号化
- **監査強化**: SOX法、個人情報保護法対応
- **アクセス制御**: ロールベースアクセス制御(RBAC)の拡張

### 本番環境への展開準備

#### インフラストラクチャ
1. **データベース**: PostgreSQL または MySQL への移行
2. **Webサーバー**: Nginx + Gunicorn 構成
3. **ストレージ**: AWS S3、Azure Blob Storage 対応
4. **モニタリング**: Prometheus + Grafana による監視
5. **ログ管理**: ELK Stack (Elasticsearch + Logstash + Kibana)

#### セキュリティ設定
1. **HTTPS強制**: SSL/TLS証明書の設定
2. **セキュリティヘッダー**: CSP、HSTS等の実装
3. **環境変数管理**: 機密情報の適切な分離
4. **定期バックアップ**: データベース・ファイルの自動バックアップ
5. **侵入検知**: 異常アクセスの監視・通知

#### 運用・保守
1. **CI/CDパイプライン**: 自動テスト・デプロイ環境
2. **エラー監視**: Sentry等によるリアルタイム監視
3. **パフォーマンス監視**: APMツールによる性能監視
4. **ドキュメント整備**: 運用マニュアル、API仕様書

## ライセンス

このプロジェクトは開発・学習用のサンプルアプリケーションです。

---

## 開発チーム・コントリビューション

### 貢献方法
1. **Issue報告**: バグや機能要求をGitHub Issuesで報告
2. **プルリクエスト**: コードの改善提案
3. **ドキュメント改善**: README、APIドキュメントの更新
4. **テスト追加**: ユニットテスト、統合テストの拡充

### 開発環境のセットアップ
```powershell
# リポジトリのクローン
git clone <repository-url>
cd CarryOutApproval

# 開発環境セットアップ
.\setup-django.ps1

# 開発サーバー起動
.\start-django.ps1
```

### コードスタイル
- **Python**: PEP 8準拠、Black フォーマッター使用
- **JavaScript**: ESLint + Prettier 設定
- **HTML/CSS**: Prettier 準拠
- **コミットメッセージ**: Conventional Commits 形式

### 技術サポート
- **ドキュメント**: `/docs/` ディレクトリの詳細仕様
- **API仕様**: OpenAPI/Swagger 対応予定
- **開発ガイド**: 新機能開発のベストプラクティス

# コーディング方針

- 一般的運用では「マイグレーション適用済み前提」で冗長防御は減らし、失敗は早期に顕在化させる。
- 外部サービス境界(LDAP通信)は詳細フェイルセーフ/分類を厚く、内部モデル属性はシンプルに。
