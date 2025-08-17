"""Application ステータス遷移集中管理モジュール

責務:
- 許可された遷移の定義 (単一ソース)
- 遷移実行 (検証 / 監査ログ / タイムスタンプ調整 / 通知ブロードキャスト)

フロント側は常に application_state (kanban_update) を受信して差分反映する。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from django.utils import timezone
from django.db import transaction
from .models import Application, ApprovalStatus
from audit.models import AuditLog
def broadcast_application_state(_application):  # pragma: no cover
    """通知ブロードキャスト (WebSocket撤去に伴い no-op)。

    以前は WebSocket / RQ push を行っていたが Long Polling 完全移行により不要。
    呼び出し箇所を残し将来 SSE 等へ差し替え可能な拡張ポイントとする。
    """
    return None

# 許可遷移 (from -> to)
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ApprovalStatus.PENDING: {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED},
    ApprovalStatus.APPROVED: {ApprovalStatus.PENDING},  # 差し戻し
    ApprovalStatus.REJECTED: {ApprovalStatus.PENDING},  # 再申請扱い (方針により削除可)
}


@dataclass
class TransitionResult:
    application: Application
    old_status: str
    new_status: str
    changed: bool


class InvalidTransition(Exception):
    pass


def allowed_targets(current: str) -> Iterable[str]:
    return ALLOWED_TRANSITIONS.get(current, set())


def change_status(application: Application, new_status: str, actor, comment: str | None = None) -> TransitionResult:
    """ステータス遷移を実行し、全クライアントへブロードキャスト。

    ルール:
    - 同一ステータス指定は no-op (changed=False)
    - 未許可遷移は InvalidTransition 例外
    - APPROVED 遷移時に approved_at を設定
    - 承認解除時 (差し戻し) は approved_at を保持 (監査用途)。クリアしたい場合は方針で調整。
    - 監査ログを一元記録
    - 通知は常に broadcast_application_state (双方) を使用
    """
    old = application.status
    if new_status == old:
        return TransitionResult(application, old, new_status, changed=False)
    if new_status not in allowed_targets(old):
        raise InvalidTransition(f"Invalid transition: {old} -> {new_status}")

    with transaction.atomic():
        application.status = new_status
        if new_status == ApprovalStatus.APPROVED and application.approved_at is None:
            application.approved_at = timezone.now()
        if comment and new_status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
            application.approval_comment = comment
        application.save()

        if new_status == ApprovalStatus.APPROVED:
            action = "approve"
        elif new_status == ApprovalStatus.REJECTED:
            action = "reject"
        elif new_status == ApprovalStatus.PENDING:
            action = f"revert_to_{new_status}"
        else:
            action = "status_change"

        AuditLog.objects.create(
            user=actor,
            application=application,
            action=action,
            details=f"{old} -> {new_status} comment={comment or 'なし'}"
        )

    # Long Polling クライアントは更新後の差分取得で同期するため、ここでは no-op ブロードキャスト関数を呼ぶのみ。
    broadcast_application_state(application)
    return TransitionResult(application, old, new_status, changed=True)
