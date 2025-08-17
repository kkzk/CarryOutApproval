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
from notifications.services import NotificationService

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

        action_map = {
            ApprovalStatus.APPROVED: "approve",
            ApprovalStatus.REJECTED: "reject",
            ApprovalStatus.PENDING: f"revert_to_{new_status}",
        }
        AuditLog.objects.create(
            user=actor,
            application=application,
            action=action_map.get(new_status, "status_change"),
            details=f"{old} -> {new_status} comment={comment or 'なし'}"
        )

    NotificationService.broadcast_application_state(application)
    return TransitionResult(application, old, new_status, changed=True)
