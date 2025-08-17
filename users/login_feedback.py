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
from .error_catalog import AuthErrorCode, compose_message

# ---------------- 動的分類テーブル ----------------
# error_catalog の文言変更影響を最小化するため、コード→文言(1文目)を起点に分類。
# 1文目が一致 (or で始まる) すれば該当カテゴリ。未該当は other。

def _first_sentence(msg: str) -> str:
    msg = msg.strip()
    if not msg:
        return msg
    # 最初の '。' までを含めた一文; 無ければ全体
    if '。' in msg:
        return msg.split('。', 1)[0] + '。'
    return msg

_CATEGORY_BY_CODE = {
    AuthErrorCode.UNREACHABLE: "unreachable",
    AuthErrorCode.DNS: "dns",
    AuthErrorCode.TLS_REQUIRED: "tls",
    AuthErrorCode.CREDENTIALS: "credentials",
    # その他のコードは "other" にフォールバック
}

# (summary_sentence, category) のリスト (順序安定)
_SUMMARY_CATEGORY: List[Tuple[str, str]] = []
for code, cat in _CATEGORY_BY_CODE.items():
    full = compose_message(code)
    summary = _first_sentence(full)
    if summary:  # 重複防止 (同一 summary が複数コードなら最初優先)
        if not any(existing == summary for existing, _ in _SUMMARY_CATEGORY):
            _SUMMARY_CATEGORY.append((summary, cat))

def _classify(full: str) -> str:
    s = _first_sentence(full)
    for summary, cat in _SUMMARY_CATEGORY:
        if full.startswith(summary):  # summary は末尾 '。' 付き
            return cat
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
