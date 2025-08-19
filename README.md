このプロジェクトは開発・学習用のサンプルアプリケーションです。

GitHub Copilot によりソースコードとドキュメントを生成しています。

# ファイル持出承認システム

ファイルを外部に持ち出す前に上司の承認を受けるワークフローを想定したWebアプリケーションです。
バックエンドとフロントエンドが一つのDjangoアプリケーションに統合されており、HTMXを活用したモダンなユーザーインターフェースを提供します。

## システム概要

### 主な機能
- **申請者**: ドラッグ&ドロップでファイルをアップロードし、承認者を指定して持出申請を作成
- **承認者**: 一覧表示での申請確認と承認・拒否操作
- **管理者**: Django管理画面での全申請管理、監査ログ確認、証跡管理

### 特徴
- **直感的なUI**: HTMXによるSPAライクな操作性とページリロード不要の更新
- **申請管理**: 申請者・承認者別の一覧表示と詳細検索機能
- **ファイル管理**: 複数ファイルアップロード対応と確認済み状況の追跡
- **監査ログ**: 全ての操作を記録し、証跡管理を実現

## 技術スタック

### バックエンド & フロントエンド (統合型アーキテクチャ)
- **Django 5.2.5** - Pythonベースの高機能Webフレームワーク
- **Django REST Framework 3.16.1** - RESTful API開発フレームワーク
- **Django Templates** - サーバーサイドレンダリングエンジン
- **HTMX 1.8.4** - モダンなAjax通信ライブラリ（SPAライクな操作感を実現）
- **Bootstrap 5.1.3** - レスポンシブUIフレームワーク
- **SQLite** (開発用) / **PostgreSQL** (本番推奨)
- **Pillow 11.3.0** - 画像・ファイル処理ライブラリ
- **python-decouple 3.8** - 設定管理ライブラリ

### 認証・LDAP統合
- **Django-python3-ldap** - Active Directory / LDAP認証対応
- **カスタム認証バックエンド** - 複数認証形式対応 (DOMAIN\\user / user@UPN)

## 主要機能

### 申請機能
- **直感的なファイルアップロード**: ドラッグ&ドロップ対応のモダンなファイル選択
- **承認者検索・選択**: リアルタイム検索による承認者選択
- **持出理由入力**: 詳細な理由とコメントの記録
- **申請履歴管理**: 自分の申請一覧表示と進捗確認

### 承認機能
- **統合型一覧管理**: 承認待ち・承認済み・拒否を統一画面で管理
- **状態フィルター**: プルダウンメニューによる申請状態の絞り込み
- **詳細検索**: 申請者、承認者、ファイル名、コメントによる複合検索
- **申請詳細確認**: モーダルウィンドウでの詳細情報表示
- **ファイルプレビュー**: アップロードされたファイルの確認
- **承認・拒否理由入力**: 詳細なコメント記録
- **ファイル確認状況追跡**: 各ファイルの確認済み状況を管理

### 管理・監査機能
- **Django管理画面**: 管理者向けの包括的な管理インターフェース
- **監査ログシステム**: 全操作の自動記録と追跡
- **証跡管理**: 申請から承認までの完全な履歴
- **ユーザー管理**: LDAP統合による組織階層ベースのユーザー管理

### ユーザーエクスペリエンス
- **レスポンシブデザイン**: Bootstrap 5によるモバイル・デスクトップ対応
- **HTMXによる高速更新**: ページリロード不要のスムーズな操作
- **プログレッシブ・エンハンスメント**: JavaScript無効環境でも基本機能利用可能

## セットアップ方法

## セットアップ方法

### 必要な環境
- Python 3.11+
- uv (Python パッケージマネージャー)
- Windows PowerShell または Command Prompt

### 簡単セットアップ・起動（Windows PowerShell）

```powershell
# 初回セットアップ
.\setup-django.ps1

# 開発サーバー起動
.\start-django.ps1
```

### 手動セットアップ

```powershell
# uvプロジェクト管理を使用（推奨）
uv sync

# データベースマイグレーション
uv run python manage.py migrate

# スーパーユーザー作成
uv run python manage.py createsuperuser

# 静的ファイル収集
uv run python manage.py collectstatic --noinput

# サーバー起動
uv run python manage.py runserver 8000
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
# (Archive) 旧 Daphne 直接起動例 (Long Polling では不要)
# python -m daphne -p 8000 carry_out_approval.asgi:application
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

- **申請一覧・管理**: http://localhost:8000
- **Django管理画面**: http://localhost:8000/admin
- **REST API**: http://localhost:8000/api
- **API ドキュメント**: http://localhost:8000/api/ (DRFブラウザ表示)

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
│   │   │       ├── approval_list.html      # 承認者用一覧画面
│   │   │       └── application_list.html   # 申請者用一覧画面
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
│   ├── notifications/       # 通知システム（Long Polling）
│   │   ├── models.py        # 通知モデル
│   │   ├── views.py         # 通知API
│   │   ├── services.py      # 通知サービス
│   │   └── serializers.py   # 通知シリアライザー
│   ├── templates/           # 共通テンプレート
│   │   └── base.html        # ベーステンプレート
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
2. **申請状況確認**: 一覧画面で申請状況を管理
   - **申請者画面**: 自分の申請一覧と状況確認
   - **承認者画面**: 承認待ち申請の確認と処理
3. **申請処理**: 承認・拒否ボタンによる状況変更
4. **詳細確認**: 申請詳細情報の表示
5. **新規申請作成**: 申請フォームから新規作成

### 高度な機能
- **フィルタリング**: 申請者、承認者、期間による絞り込み
- **検索機能**: キーワードによる申請検索
- **ソート機能**: 作成日、更新日、申請者名による並び替え
- **Long Polling**: リアルタイム状況更新

## テスト・動作確認

### Webアプリケーションテスト

#### 1. 基本的な動作確認
```bash
# Djangoサーバー起動
uv run python manage.py runserver 8000

# ブラウザで以下にアクセス
# http://localhost:8000/users/login/
```

#### 2. 通知システムテスト（Long Polling）
```bash
# Djangoサーバー起動（Long Polling対応）
uv run python manage.py runserver 8000

# 通知システムテスト用URL
# http://localhost:8000/
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

#### (Archive) 従来の実装に関するトラブルシューティング
Long Polling 移行後は通常発生しません。旧実装検証時の参考として残しています。

1. **WebSocket接続失敗** (旧手順)
   - 現在は Long Polling を使用しているため、WebSocket関連のエラーは発生しません

2. **Redis接続エラー** (旧構成)
   - 現行構成では Redis を使用していません

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

# Long Polling Settings
LONG_POLLING_ENABLED=True
LONG_POLLING_TIMEOUT=30

# Mock User API URL (for development)
MOCK_USER_API_URL=http://localhost:8001/api/users
```

**注意**: 現在の構成では Redis や WebSocket を使用していません。

### Django設定のカスタマイズ

Django設定は `django/carry_out_approval/settings.py` で管理されています：

- **データベース**: SQLite（開発用）、PostgreSQL（本番用）
- **ファイルストレージ**: ローカルストレージ（`storage/`ディレクトリ）
- **静的ファイル**: `staticfiles/`ディレクトリに収集
- **テンプレート**: Django Templates + HTMX
- **認証**: Django組み込み認証システム

## アーキテクチャの特徴

#### HTMXの採用理由
#### HTMXの採用理由
- **軽量性**: 重いJavaScriptフレームワークが不要
- **学習コストの低さ**: HTMLベースのシンプルな記法
- **サーバー親和性**: Django Templatesとの自然な統合
- **プログレッシブエンハンスメント**: JavaScript無効環境でも動作

#### Long Polling の採用理由
- **シンプルな実装**: WebSocketより実装・運用が容易
- **十分なリアルタイム性**: 申請状況の更新に必要な応答性を実現
- **高い互換性**: プロキシ・ファイアウォール環境での安定動作
- **Django統合**: 既存の認証システムとの自然な連携

### Long Polling への段階的移行状況 (2025-08)

本システムは当初 WebSocket + Redis (channels) + RQ による push 型更新でカンバン反映を行っていましたが、要件整理の結果「最終状態のみを最新化できれば UX を満たす」ことが判明したため、現在は Long Polling 方式へ段階的移行済みです。

| 項目 | 状態 | 備考 |
|------|------|------|
| WebSocket カンバン更新 | 無効 (fallback クローズ) | `LONG_POLLING_ENABLED=True` 時 asgi で consumer 未登録 |
| RQ 経由の送信タスク | no-op | `NotificationService` が early return |
| Poll API (`/applications/poll/updates/?scope=kanban`) | 稼働 | 差分: `updated_at` > since の Application 一括返却 |
| WebSocket consumer / routing | 残置 (後方互換) | 今後削除予定 (最終確認後) |
| channels / channels_redis 依存 | まだ残置 | 削除候補 (別ブランチで除去予定) |
| redis / django_rq | まだ残置 | 他用途が無ければ削除可能 |

#### Long Polling 仕様概要
- クライアントは前回レスポンスの `latest` (ISO8601 UTC) を次回 `since` として送信
- サーバは対象ユーザ (applicant / approver) 関連 `Application.updated_at` > since が出現するまで最長 25 秒待機 (1 秒間隔ポーリング)
- 変更検知時: 変更分 (最大 50 件) を即時返却。なければタイムアウトで空配列
- クライアントは受信ごとに DOM 差分適用 (既存 WebSocket 処理を再利用)

#### 今後の削除予定ファイル (削除手順メモ)
| ファイル | 役割 | 削除条件 |
|----------|------|----------|
| `notifications/consumers.py` | WebSocket consumer | 全ページで Long Polling 安定運用確認後 |
| `notifications/routing.py` | WebSocket ルーティング | consumer 削除と同時 |
| `notifications/tasks.py` | RQ 送信タスク | 他で RQ 未使用を確認後 |
| `notifications/services.py` 内 WS 関連分岐 | push 不要化 | consumer 削除前に整理 |
| `carry_out_approval/asgi.py` の fallback | 完全削除段階 | WS 需要無しを正式決定後 |
| 依存: `channels`, `channels_redis`, `django_rq`, `redis` | requirements / pyproject から除去 | 上記コード削除後 CI グリーン確認 |

#### 移行後の利点
- インフラ依存削減による運用負荷軽減（Redis、専用ASGIサーバ設定不要）
- 接続維持コスト削減（WebSocket keepalive不要）
- デバッグ容易性：通常のHTTPトレースのみで解析可能

#### 留意点・今後の最適化
- 同時多数ユーザ時のDBポーリング負荷：現状1秒間隔、バックオフ（指数・ジッタ）導入余地
- レスポンスペイロードサイズ最適化：専用軽量シリアライザ導入（必要フィールド限定）検討
- 変更トリガーのpub/sub化（将来再びpushが必要になった場合に備えたイベント抽象化）

> NOTE: 現在WebSocketへ接続した場合は即時正常コード（1000）でクローズするfallback実装。クライアント側で未使用であればユーザ影響なし。

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

### Long Polling 通知システムのエラー

#### 通知が更新されない
1. ブラウザの開発者ツールでネットワークタブを確認
2. `/api/applications/poll/updates/` エンドポイントへのリクエストを確認
3. `LONG_POLLING_ENABLED=True` 設定を確認
4. サーバログでエラーがないか確認

## 今後の開発方針

### 近期実装予定
- **通知システム強化**: ✅ **完了** - Long Pollingベースのリアルタイム通知
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
