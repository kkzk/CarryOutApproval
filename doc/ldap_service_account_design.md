# LDAP 検索専用サービスアカウント設計 / 作成手順

## 目的
アプリケーション内で承認者候補などのディレクトリ検索を行う際、
各ユーザ本人の資格情報（パスワード）を再利用・保存せず、最小権限の検索専用アカウントで LDAP (AD DS) にバインドして検索を行う。
これにより:
- 利用者パスワードの保存リスク排除
- 一貫した接続失敗/レート制御と監査ログ集中
- OU 変更後の再同期をアプリ側から即時実行可能

## 要求事項 / ポリシー
| 項目 | 要件 |
|------|------|
| 用途 | 読み取り検索 (ユーザ属性 / OU 内ユーザ列挙) のみ |
| 書込権限 | 付与しない (パスワード変更, 追加, 削除権限不要) |
| 有効期限 | パスワードは定期ローテーション (例: 90日) |
| 認証方式 | Simple Bind / (可能なら StartTLS もしくは LDAPS) |
| ネットワーク | アプリサーバから DC 389(または636) への inbound 許可 |
| ログ | 失敗バインド試行は DC のセキュリティログで監査可能 |
| 2要素 | 不要 (サービスアカウント) |

## 命名規約例
```
svc_ca_read       (短く用途を示す)
svc_carryout_ldap (アプリ識別入り)
```
推奨: `svc_` プレフィックス + システム略称 + 機能。説明欄 (description) に「CarryOutApproval 読み取り専用 LDAP サービスアカウント」と明記。

## OU 配置
専用 OU 例: `OU=Service Accounts,DC=testadds,DC=internal`
- GPO で対話型ログオン禁止
- パスワードポリシー: 長く (20+ 文字) / 履歴保持 / 有効期限

## 権限付与 (最小権限原則)
通常、Active Directory はデフォルトでドメインユーザに対する「ユーザ / グループ オブジェクトの読み取り」を許可しているため、**追加権限が不要** なケースが多い。以下が必要な場合のみ設定:
- 特定 OU に対して明示的にアクセス制限があり既定継承が外れている場合 → OU の [Security] タブで `Read` 系 ACE を追加。

付与すべきでない権限:
- Write / Delete
- Reset Password
- Create / Delete Computer Objects
- Add Member to Group など

## StartTLS / LDAPS 方針
| 環境 | 推奨 |
|------|------|
| 本番 | LDAPS (636) もしくは 389 + StartTLS 強制 |
| 検証 | StartTLS か平文 (防火壁内 / TLS導入前) |
| 開発ローカル | 平文許容可 (早期段階) |

settings.py 例:
```
LDAP_SERVER_URL=ldaps://dc01.testadds.internal:636
LDAP_USE_SSL=true
LDAP_FORCE_STARTTLS=false
LDAP_TLS_INSECURE=false
```
StartTLS 利用例:
```
LDAP_SERVER_URL=ldap://dc01.testadds.internal:389
LDAP_USE_SSL=false
LDAP_FORCE_STARTTLS=true
```

## .env への設定例
```
LDAP_SERVER_URL=ldap://dc01.testadds.internal:389
LDAP_BIND_DN=CN=svc_carryout_ldap,OU=Service Accounts,DC=testadds,DC=internal
LDAP_BIND_PASSWORD=**************
LDAP_SEARCH_BASE=DC=testadds,DC=internal
LDAP_DOMAIN=testadds
LDAP_UPN_SUFFIX=testadds.internal
LDAP_USE_SSL=false
LDAP_FORCE_STARTTLS=true
LDAP_ALLOW_PLAIN_FALLBACK=false
LDAP_TLS_INSECURE=false
```

## PowerShell によるアカウント作成手順 (AD DS)
管理者権限 PowerShell (ドメインコントローラ もしくは RSAT が使える端末) で:
```powershell
$Name = 'svc_carryout_ldap'
$OU = 'OU=Service Accounts,DC=testadds,DC=internal'
$PasswordPlain = 'LongRandom#Passw0rd-2025!'
$SecurePass = ConvertTo-SecureString $PasswordPlain -AsPlainText -Force
New-ADUser `
  -Name $Name `
  -SamAccountName $Name `
  -Path $OU `
  -Enabled $true `
  -AccountPassword $SecurePass `
  -PasswordNeverExpires $false `
  -ChangePasswordAtLogon $false `
  -Description 'CarryOutApproval 読み取り専用 LDAP サービスアカウント'
```

(必要なら初回パスワード期限を無効化する場合)
```powershell
Set-ADUser $Name -PasswordNeverExpires $true
```

OU に対話型ログオン禁止 GPO を適用（`Deny log on locally` に該当アカウント追加）するか、メンバーシップにログオン不可のグループを使用。

## パスワードローテーション運用
1. 新パスワード生成 (秘密管理システムで保存)
2. `.env` 更新 → サーバ再起動 / プロセス再読み込み
3. 旧パスワード無効化 (期限切れ設定 or 変更) / ログ監視で失敗試行がないか確認

自動化案: CI/CD シークレット更新 + Ansible / Script で `.env` 差し替え & プロセス再起動。

## アプリ側チェック (推奨追加)
- 起動時: `LDAP_BIND_DN` / `LDAP_BIND_PASSWORD` がデフォルト (example.com / your_admin_password) のままなら WARNING ログ。
- バインド失敗時: result code / description を DEBUG で出力。

## 監査
| 監査項目 | 方法 |
|----------|------|
| バインド成功/失敗 | AD セキュリティログ (Event ID 4624/4625) フィルタ SamAccountName=svc_carryout_ldap |
| 過剰クエリ | DC のパフォーマンスモニタ (LDAP searches/sec) |
| 最終ローテーション日 | パスワード管理台帳 or Secret Manager のメタデータ |

## 既存コードへの影響
- 既に `get_approvers_for_user` はサービスアカウント利用を前提としているため**コード変更不要**。
- 未設定時 (空文字) は接続不可 → 明示的なエラーハンドリングを後で追加可。

## 今後の拡張候補
- 接続失敗リトライ (指数バックオフ) 実装
- 候補キャッシュ (メモリ or Redis) + TTL (例: 5分) で LDAP 負荷低減
- サービスアカウント異常時のフォールバック（直近キャッシュ）
- Prometheus などでバインド/検索統計メトリクス出力

---
この文書に沿ってサービスアカウントを作成し、`.env` を更新後、再起動して再同期ボタンで候補が取得できることを確認してください。
