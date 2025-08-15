# LDAP 認証

## LDAP 用語の説明

LDAPおよびActive Directoryを扱う上で頻出する、略語を中心とした専門用語を解説します。

| 用語 (略語) | 正式名称 / 名称 | 説明 |
| :--- | :--- | :--- |
| **LDAP** | Lightweight Directory Access Protocol | ディレクトリサービスにアクセスし、情報を問い合わせたり変更したりするための標準的なプロトコル。 |
| **Entry** | エントリ | ディレクトリ内の個々のレコード。一人のユーザー、一つのコンピュータ、一つのプリンターなどがそれぞれエントリにあたる。 |
| **Attribute** | 属性 | エントリが持つ個々の情報項目。`mail`（メールアドレス）や`cn`（名前）など、キーと値のペアで構成される。 |
| **Schema** | スキーマ | ディレクトリに格納できる情報の構造、型、規則の定義。どのようなエントリが存在でき、各エントリがどのような属性を持てるかを定める設計図。 |
| **DN** | Distinguished Name | **識別名**。ディレクトリツリー内でのエントリの一意な完全パス。ルートからエントリまでを一意に特定する、いわば「絶対パス」。 |
| **RDN** | Relative Distinguished Name | **相対識別名**。DNの一部で、同じ階層内でエントリを区別する部分。例えば`CN=Taro Yamada`がRDNにあたる。 |
| **Base DN** | ベースDN | LDAP検索を開始するディレクトリツリーの起点となるDN。このDN以下の階層が検索対象となる。 |
| **Bind** | バインド | LDAPサーバーに接続し、クライアントを認証する操作。認証が成功すると、後続の操作（検索など）が許可される。 |
| **Search** | 検索 | ディレクトリ内の情報を検索する操作。 |
| **Filter** | フィルタ | `Search`操作時に、特定の条件に一致するエントリを見つけるために使用する検索条件式。例: `(sAMAccountName=testuser)` |
| **Scope** | スコープ | `Search`操作時の検索範囲。`Base`（指定したエントリのみ）、`OneLevel`（1階層下のみ）、`Subtree`（配下の全階層）がある。 |
| **LDAPS** | LDAP over SSL/TLS | 最初からSSL/TLSで暗号化されたLDAP通信。デフォルトポートは`636`。 |
| **STARTTLS** | - | 標準のLDAPポート(`389`)で接続後、`STARTTLS`コマンドで通信を暗号化されたTLSセッションにアップグレードする仕組み。 |
| **CN** | Common Name | エントリの一般的な名前を表す属性。ユーザーのフルネームやオブジェクト名に使われることが多い。 |
| **OU** | Organizational Unit | **組織単位**。組織内の部署や部門などを表現するためのコンテナ（入れ物）オブジェクト。エントリを階層的に管理するために使用する。 |
| **DC** | Domain Component | DNSのドメイン名を構成する要素を表す属性。`example.com`は`DC=example,DC=com`のように表現される。 |
| **UPN** | User Principal Name | Active Directoryで使われる、`user@domain.com`というメールアドレス形式のユーザーログイン名。 |
| **sAMAccountName**| - | Active Directoryで使われる、Windows 2000以前の互換性を保つためのレガシーなログイン名（例: `tyamada`）。 |

## LDAPで使われるポート番号

LDAP接続では、主に以下の2つのポート番号が使用されます。

*   **ポート 389 (LDAP):**
    *   暗号化されていない、平文で通信するための標準ポートです。
    *   通信内容が盗聴される危険性があるため、セキュリティが重要な環境では推奨されません。
    *   `STARTTLS` という拡張機能を使うことで、このポート上で暗号化通信を開始することも可能です。
*   **ポート 636 (LDAPS - LDAP over SSL/TLS):**
    *   SSL/TLSによって初めから暗号化された通信を行うためのポートです。
    *   通信の安全性と機密性が確保されます。

## LDAP接続のシーケンス図

```mermaid
sequenceDiagram
    participant Client as クライアント
    participant LDAP Server as LDAPサーバー

    %% 1. 接続フェーズ
    alt 接続方法の選択
        option ポート 389 (平文)
            Client->>LDAP Server: 1. TCP接続要求 (ポート 389)
            activate LDAP Server
            LDAP Server-->>Client: 2. 接続確立
            deactivate LDAP Server
        option ポート 636 (LDAPS)
            Client->>LDAP Server: 1. TLSハンドシェイク (ポート 636)
            activate LDAP Server
            LDAP Server-->>Client: 2. 暗号化された接続を確立
            deactivate LDAP Server
        option ポート 389 (STARTTLS)
            Client->>LDAP Server: 1. TCP接続要求 (ポート 389)
            activate LDAP Server
            LDAP Server-->>Client: 2. 接続確立
            deactivate LDAP Server
            Client->>LDAP Server: 3. STARTTLSコマンド (暗号化要求)
            activate LDAP Server
            LDAP Server-->>Client: 4. TLSハンドシェイクを開始し、暗号化通信へ移行
            deactivate LDAP Server
    end

    %% 2. 認証 (Bind) フェーズ
    Client->>LDAP Server: 5. Bind Request (認証要求)<br>送信情報: ユーザーDN, パスワード
    activate LDAP Server
    LDAP Server-->>Client: 6. Bind Response (認証結果)<br>結果: 成功 / 失敗
    deactivate LDAP Server

    %% 3. 操作 (Search) フェーズ
    alt 認証が成功した場合
        Client->>LDAP Server: 7. Search Request (検索要求)<br>条件: ベースDN, 検索範囲, フィルタ
        activate LDAP Server
        LDAP Server-->>Client: 8. Search Result Entry (検索結果エントリ)
        LDAP Server-->>Client: ... (複数のエントリが返される)
        LDAP Server-->>Client: 9. Search Result Done (検索完了通知)
        deactivate LDAP Server
    else 認証が失敗した場合
        note over Client, LDAP Server: 処理はここで終了
    end

    %% 4. 切断 (Unbind) フェーズ
    Client->>LDAP Server: 10. Unbind Request (接続解除要求)
    note over LDAP Server: Unbindに対するサーバーからの応答はない
    Client--xLDAP Server: 11. TCP接続を切断
```

## シーケンス図の解説

### 1. 接続 (Connect)
クライアントは、設定されたポート番号（389または636）を使用して、LDAPサーバーとのネットワーク接続を確立します。
LDAPS(636)やSTARTTLSを使用する場合、この段階で通信が暗号化されます。

### 2. バインド (Bind)
接続が確立されると、クライアントは`Bind`操作を行い、サーバーに対して自身を認証します。
一般的には、ユーザーの識別名（DN: Distinguished Name）とパスワードをサーバーに送信します。
サーバーは認証情報を検証し、成功または失敗の結果をクライアントに返します。

### 3. 検索 (Search)
認証が成功すると、クライアントはディレクトリ情報を検索するための`Search`操作を実行できます。
検索リクエストには、以下の主要な情報が含まれます。
- **ベースDN:** 検索を開始するディレクトリツリーの起点。
- **スコープ:** 検索範囲（ベースオブジェクトのみ、1階層下、サブツリー全体など）。
- **フィルタ:** 検索条件（例: `(uid=testuser)`）。

サーバーは条件に一致するエントリをクライアントに送信し、最後に検索が完了したことを通知します。

### 4. アンバインド (Unbind)
必要な操作がすべて完了したら、クライアントは`Unbind`リクエストを送信して、セッションを終了する意思をサーバーに伝えます。
このリクエストに対するサーバーからの応答は規約上ありません。その後、クライアントはTCP接続を切断します。

---
この一連の流れを経て、アプリケーションはLDAPサーバーから安全にユーザー情報を取得し、認証や認可を行うことができます。

# LDAP の検索と LDAP によるユーザ認証の違い

LDAPの「検索（Search）」と「ユーザー認証（Authentication）」は、目的と使用する操作が根本的に異なります。

### LDAP検索 (Search)
- **目的:** ディレクトリ内に存在するエントリ（ユーザー、グループなど）の情報を**取得する**こと。
- **操作:** `Search` 操作を使用します。
- **仕組み:**
    1. まず、検索を実行する権限を持つアカウント（多くの場合、専用のサービスアカウント）でサーバーに接続し、認証（Bind）します。
    2. 認証後、指定したベースDN（検索の起点）から、フィルタ条件に一致するエントリを探します。
    3. サーバーは、条件に一致したエントリの属性（例: メールアドレス、電話番号、所属部署など）を返します。
- **例:** 「`uid`が`testuser`であるユーザーの`mail`属性を取得する」といった使い方をします。

### LDAPユーザー認証 (Authentication)
- **目的:** 特定のユーザーが提供したパスワードが正しいかどうかを**検証する**こと。
- **操作:** `Bind` 操作を使用します。
- **仕組み:**
    1. 認証したいユーザー自身のDN（Distinguished Name）と、そのユーザーが入力したパスワードを使って、サーバーに対して`Bind`（接続・認証）を試みます。
    2. `Bind`が成功すれば、パスワードが正しいと判断されます。
    3. `Bind`が失敗すれば、パスワードが間違っているか、ユーザーが存在しないと判断されます。
- **ポイント:** この操作自体はユーザー情報を取得するものではなく、あくまで「本人であることの確認」が目的です。

### まとめ：主な違い

| 特徴 | LDAP検索 (Search) | LDAPユーザー認証 (Bind) |
| :--- | :--- | :--- |
| **目的** | 情報の**取得** | 本人性の**検証** |
| **主な操作** | `Search` | `Bind` |
| **必要な情報** | 検索用アカウントの認証情報、検索ベース、フィルタ | 認証したいユーザーのDN、パスワード |
| **結果** | 条件に一致したエントリの情報 | 認証の成功または失敗 |

### 一般的な認証フロー
実際のアプリケーションでは、これら2つが組み合わせて使われることがよくあります。
1. **Search:** まず、サービスアカウントでログインし、ユーザーID（例: `sAMAccountName`）を元にユーザーの正確なDNを**検索**します。
2. **Bind:** 次に、見つかったDNとユーザーが入力したパスワードを使って**Bind**を試み、認証を行います。

# Active DirectoryにおけるBind操作のパラメータ例

Active Directory（AD）環境で`Bind`（認証）操作を行う際には、ユーザーを特定するための情報とパスワードが必要です。特にユーザーの特定方法には複数のフォーマットがあり、サーバー側の設定によって使用できるものが異なります。

### 1. Bindに必要な主要パラメータ

#### a. ユーザー識別子 (User Identifier)

ユーザーを特定するために、以下のいずれかの形式を使用します。

| フォーマット | 説明 | 例 |
| :--- | :--- | :--- |
| **Distinguished Name (DN)** | ディレクトリ内でのオブジェクトの一意な完全パス。最も確実で基本的な指定方法。 | `CN=Taro Yamada,OU=Sales,DC=example,DC=com` |
| **User Principal Name (UPN)** | メールアドレス形式のログイン名。ユーザーフレンドリーで、多くのアプリケーションで推奨される。 | `tyamada@example.com` |
| **sAMAccountName** | `ドメイン名\ユーザー名` の形式。Windowsのレガシーなログイン形式。 | `EXAMPLE\tyamada` |

#### b. パスワード (Password)

上記で指定したユーザーの現在のパスワード。

---

### 2. ユーザー識別子のフォーマット詳細

#### Distinguished Name (DN)
- **フォーマット:** `CN=コモンネーム,OU=組織単位,...,DC=ドメインコンポーネント,...`
- **詳細:**
    - `CN` (Common Name): ユーザーのフルネームやログイン名など。
    - `OU` (Organizational Unit): ユーザーが所属する組織単位。階層構造にできます。
    - `DC` (Domain Component): ドメイン名を構成する要素。`example.com`なら`DC=example,DC=com`となります。
- **取得方法:** ADの管理ツール（Active Directory Users and Computers）でユーザーのプロパティから確認するか、`Search`操作で事前に取得する必要があります。

#### User Principal Name (UPN)
- **フォーマット:** `username@suffix`
- **詳細:**
    - `username`: ユーザーのログイン名。
    - `suffix`: UPNサフィックス。通常はADのDNSドメイン名ですが、管理者が追加のサフィックスを登録することも可能です。
- **サーバー側の前提条件:**
    - UPNで認証するには、そのUPNサフィックス（`@`以降の部分）がADフォレストで有効な代替UPNサフィックスとして登録されている必要があります。

#### sAMAccountName
- **フォーマット:** `DOMAIN\username` または `username`
- **詳細:**
    - `DOMAIN`: NetBIOSドメイン名。
    - `username`: 20文字以下のレガシーログイン名。
- **サーバー側の前提条件:**
    - `username`だけでBindする場合、LDAPサーバー（ドメインコントローラー）が所属ドメインを特定できる必要があります。
    - `DOMAIN\username`形式がより確実です。

### 3. サーバー側の前提条件

Bind操作が成功するためには、クライアントからの情報だけでなく、サーバー側（ドメインコントローラー）で以下の条件が満たされている必要があります。

- **アカウントの状態:**
    - ユーザーアカウントがAD上に存在し、「有効」であること。
    - アカウントがロックアウトされていたり、無効化されていたりすると認証は失敗します。
- **ネットワーク接続:**
    - クライアントからドメインコントローラーのLDAPポート（デフォルト: `389/TCP`）またはLDAPSポート（`636/TCP`）へのネットワーク経路が確保されていること。ファイアウォール等で通信が許可されている必要があります。
- **証明書（LDAPS/STARTTLS利用時）:**
    - LDAPS（ポート636）やSTARTTLSを利用して暗号化通信を行う場合、ドメインコントローラーに有効なサーバー証明書がインストールされている必要があります。
    - また、クライアントはその証明書を信頼できる（証明書を発行したCAが信頼されている）必要があります。

# `django\users\backends.py` のコーディングでの対応

`django/users/backends.py` に実装されている `WindowsLDAPBackend` は、Active Directoryとの認証を柔軟かつ安全に行うためのカスタム認証バックエンドです。

### ユーザー名しか入力されなかった場合の認証戦略

多くのLDAP実装では、ユーザーに `DOMAIN\username` や `user@example.com` のような完全な形式での入力を強いることがあります。しかし、このバックエンドでは、ユーザーが自身のID（例: `tyamada`）のみを入力した場合でも、システム側で複数の認証形式を自動的に試行する仕組みを持っています。

この処理の中核を担うのが `_generate_bind_candidates` メソッドです。

**仕組み:**
1.  ユーザーが入力した文字列を分析します。
2.  `\` や `@` が含まれていない場合、`settings.py` に設定された `LDAP_DOMAIN` や `LDAP_UPN_SUFFIX` の値を使って、複数のバインド候補を自動生成します。
    -   `LDAP_DOMAIN` が設定されていれば、**NTLM形式** (`DOMAIN\username`) の候補を生成します。
    -   `LDAP_UPN_SUFFIX` が設定されていれば、**UPN形式** (`username@suffix`) の候補を生成します。
3.  生成された候補リスト（例: `['EXAMPLE\tyamada', 'tyamada@example.com']`）を順番に試し、最初に認証（Bind）が成功したものを採用します。

これにより、ユーザーはログイン形式を意識することなく、単純なIDだけでログインすることが可能になります。

```python
# django/users/backends.py より抜粋
def _generate_bind_candidates(self, username: str, cfg: LDAPRuntimeConfig) -> Iterable[Tuple[str, str, Optional[str]]]:
    """与えられた username から順序付きのバインド候補 (label, user, auth_kind) を生成."""
    original = username
    # ... (入力が既に NTLM or UPN 形式の場合の処理) ...

    # username のみにドメイン情報を付与してNTLM候補を生成
    if '\\' not in original and '@' not in original and cfg.domain:
        yield from push(("NTLM(domain)", f"{cfg.domain}\\{original}", 'NTLM'))

    # username のみにUPNサフィックスを付与してUPN候補を生成
    if '\\' not in original and '@' not in original:
        suffix = cfg.upn_suffix or (cfg.domain if cfg.domain and '.' in cfg.domain else None)
        if suffix:
            yield from push(("UPN(constructed)", f"{original}@{suffix}", None))
```

### LDAPS と STARTTLS によるセキュア接続への対応

通信の盗聴を防ぐため、このバックエンドは暗号化通信を優先します。`settings.py` の設定に応じて、LDAPSまたはSTARTTLSを自動的に利用します。

#### LDAPS (LDAP over SSL/TLS)
- **設定:** `LDAP_USE_SSL = True`
- **動作:** 最初から暗号化されたSSL/TLSトンネルを確立して通信します。接続ポートは自動的に `636` がデフォルトになります。

#### STARTTLS
- **設定:** `LDAP_FORCE_STARTTLS = True`
- **動作:**
    1.  標準のLDAPポート（`389`）で平文の接続を開始します。
    2.  接続後、`STARTTLS` コマンドをサーバーに送信し、現在の接続を暗号化されたTLS接続にアップグレードします。
    3.  暗号化が確立された後で、`Bind` 操作（認証情報の送信）を行います。

#### 安全性を重視したデフォルト動作
このバックエンドは「セキュア・バイ・デフォルト」の思想で設計されています。
`settings.py` で `LDAP_USE_SSL` も `LDAP_FORCE_STARTTLS` も `False` で、かつ平文通信を許可する `LDAP_ALLOW_PLAIN_FALLBACK = False` の場合、**自動的にSTARTTLSを試行します**。これにより、設定漏れによって意図せず平文でパスワードが流出するリスクを低減しています。

```python
# django/users/backends.py より抜粋

# StartTLS を強制する条件を決定
force_starttls = cfg.force_starttls or (not cfg.use_ssl and not cfg.allow_plain)

# ...

# 接続試行のループ内
def _attempt_single_candidate(...):
    # ...
    # LDAPS接続でなく、STARTTLSが強制されている場合はアップグレードを試行
    if not cfg.use_ssl and force_starttls and not self._start_tls_if_needed(conn, ...):
        return None # STARTTLS失敗時は次の処理へ進まない

    # Bind処理を実行
    if not self._bind_connection(conn, ...):
        return None
    # ...
```

また、暗号化通信の際にはサーバー証明書の検証も行いますが、開発環境向けに `LDAP_TLS_INSECURE = True` を設定することで、証明書検証を無効にすることも可能です。

