"""認証系エラーメッセージ集中管理モジュール.

エラー発生箇所では文字列ではなく AuthErrorCode.* を返し、
最終的なユーザー表示直前で compose_message で 2 文 (要約。対処。) に整形する。
"""
from __future__ import annotations
from enum import Enum
from typing import Tuple, Dict

class AuthErrorCode(str, Enum):
    DNS = "DNS"
    UNREACHABLE = "UNREACHABLE"
    TLS_REQUIRED = "TLS_REQUIRED"
    CREDENTIALS = "CREDENTIALS"
    LDAP_USER_NOT_FOUND = "LDAP_USER_NOT_FOUND"
    DOMAIN_INFO_MISSING = "DOMAIN_INFO_MISSING"
    UNKNOWN = "UNKNOWN"

# summary, action (末尾句点含む)
_ERROR_TABLE: Dict[AuthErrorCode, Tuple[str, str]] = {
    AuthErrorCode.DNS: (
        "ActiveDirectory サーバが見つかりません。",
        "【保守担当】アプリケーションサーバの DNS 設定を確認してください。",
    ),
    AuthErrorCode.UNREACHABLE: (
        "ActiveDirectory サーバに到達できません。",
        "【運用窓口】ActiveDirectoryサーバが稼働しているか確認してください。",
    ),
    AuthErrorCode.TLS_REQUIRED: (
        "サーバ間通信の暗号化が不十分です。",
        "【運用窓口】ActiveDirectoryサーバの設定および証明書を確認してください。",
    ),
    AuthErrorCode.CREDENTIALS: (
        "IDまたはパスワードが違います。",
        "正しいIDおよびパスワードを入力してください。",
    ),
    AuthErrorCode.LDAP_USER_NOT_FOUND: (
        "ActiveDirectory ユーザー情報が見つかりません。",
        "【運用窓口】ディレクトリにユーザー未登録（追加/同期要確認）と連絡してください。",
    ),
    AuthErrorCode.DOMAIN_INFO_MISSING: (
        "認証に必要なドメイン情報が不足しています。",
        "【保守担当】LDAP ドメイン/UPN サフィックス設定を確認してください。",
    ),
    AuthErrorCode.UNKNOWN: (
        "認証に失敗しました。",
        "【運用窓口】状況を記録し、必要なら保守担当へエスカレーションしてください。",
    ),
}

def compose_message(code: AuthErrorCode) -> str:
    summary, action = _ERROR_TABLE.get(code, _ERROR_TABLE[AuthErrorCode.UNKNOWN])
    return f"{summary}{action}"  # 2 文構成 (テンプレ側で句点分割)
