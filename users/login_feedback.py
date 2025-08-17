"""ログイン画面向けのメッセージ整形ヘルパ。

テンプレート内で複雑な JS を書かず、バックエンド側で
以下のポリシーに沿って表示用データへ変換する:

1. dns / unreachable / tls / credentials / other に分類
2. unreachable (旧 network) が 1件以上ある場合は他カテゴリの同時表示を抑止して利用者の一次切り分けを単純化
3. 各メッセージは「最初の一文=要約」「残り=対処(1アイテム)」に分離
4. 追加の自動ヒントは付与しない（メッセージ文字列自体が 2 文構成）
5. Django messages の level/tag を維持し Bootstrap の alert-* に利用

返却構造:
  {
     'login_messages': [ { 'summary': str, 'level': 'error' など }, ...],
     'login_actions': [ '～してください。', ... ]
  }
"""
from __future__ import annotations
from typing import List, Dict, Tuple
import re
from django.contrib import messages as dj_messages

UNREACHABLE_PATTERNS = [
    re.compile(r"ActiveDirectory サーバに到達できません"),
]
DNS_PATTERNS = [
    re.compile(r"ActiveDirectory サーバが見つかりません"),
]
TLS_PATTERNS = [
    re.compile(r"ネットワークレベルの暗号化が要求されました"),
]
CREDENTIAL_PATTERNS = [
    re.compile(r"IDまたはパスワードが違います"),
]

def _classify(full: str) -> str:
    if any(p.search(full) for p in UNREACHABLE_PATTERNS):
        return "unreachable"
    if any(p.search(full) for p in DNS_PATTERNS):
        return "dns"
    if any(p.search(full) for p in TLS_PATTERNS):
        return "tls"
    if any(p.search(full) for p in CREDENTIAL_PATTERNS):
        return "credentials"
    return "other"

def build_login_feedback(request) -> Dict[str, List]:  # noqa: D401
    storage = dj_messages.get_messages(request)
    raw_list = list(storage)  # 消費されるので展開
    classified: List[Tuple[str, object]] = [(_classify(str(m)), m) for m in raw_list]
    has_unreachable = any(cat == "unreachable" for cat, _ in classified)
    if has_unreachable:
        classified = [c for c in classified if c[0] == "unreachable"]
    login_messages: List[Dict[str, str]] = []
    login_actions: List[str] = []
    for cat, m in classified:
        full = str(m).strip()
        if not full:
            continue
        parts = [p for p in re.split(r"。+", full) if p]
        if not parts:
            continue
        summary = parts[0] + "。"
        if len(parts) > 1:
            rest = "。".join(parts[1:]).strip("。")
            if rest:
                login_actions.append(rest + "。")
        login_messages.append({
            "summary": summary,
            "level": str(getattr(m, 'tags', 'info')).split()[0] or 'info',
        })
    return {"login_messages": login_messages, "login_actions": login_actions}
