# ユーザーモデリング概要

## 1. モデル構成

本システムのユーザー管理は、Django標準の `User` モデルと、拡張情報を格納する `UserProfile` モデルの2層構成です。

### User（Django標準）

- 認証・認可の基盤となるモデル
- 主なフィールド: username, password, email, is_active, is_staff, is_superuser など

`django.contrib.auth` パッケージの `models` モジュールに定義されている `User` クラスです。

https://docs.djangoproject.com/ja/5.2/ref/contrib/auth/#django.contrib.auth.models.User

### UserProfile（拡張プロファイル）

- `User` と 1対1（OneToOneField）で紐付く
- LDAP/ローカルの区別や、所属・役職・LDAP DN など追加情報を保持
- 主なフィールド:
  - user: User への OneToOneField
  - source: ユーザーの出所（local/ldap）
  - ldap_dn: LDAP Distinguished Name
  - department_code: 所属コード
  - department_name: 所属名
  - title: 役職
  - last_synced_at: LDAP最終同期時刻

### シグナルによる自動生成

- User作成時に自動でUserProfileも生成
- User更新時にもProfileの整合性を維持

---

## 2. ER図

```mermaid
erDiagram
    USER {
        int id PK
        string username
        string password
        string email
        ...
    }
    USER_PROFILE {
        int id PK
        int user_id FK, UNIQUE
        string source
        string ldap_dn
        string department_code
        string department_name
        string title
        datetime last_synced_at
    }

    USER ||--o| USER_PROFILE : "1対1"
```

---

## 3. モデル定義例

```python
from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile'
    )
    source = models.CharField(max_length=20, choices=UserSource.choices, default=UserSource.LOCAL)
    ldap_dn = models.TextField(blank=True)
    department_code = models.CharField(max_length=20, blank=True)
    department_name = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=100, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
```

---

## 4. 運用上のポイント

- ユーザーの追加属性はすべてUserProfileで管理
- 所属コード・役職などは申請・承認フローや外部連携（CIFS配置時の識別）にも利用
- LDAP連携時は `source` や `ldap_dn` で識別・同期管理

---

## 5. 今後の拡張例

- 権限ロールやグループ管理の追加
- 多要素認証や外部ID連携
- 監査ログとの連携強化
