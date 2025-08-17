"""申請関連ロングポーリング (差分取得) 共通エンドポイント。

scope パラメータで取得対象を切替:
  - kanban  : applicant / approver いずれか (従来カンバン)
  - my      : 自分が applicant の申請
  - pending : 自分が approver かつ PENDING
  - history : 自分が approver で APPROVED / REJECTED

since: ISO8601 (Z or +00:00)。未指定時は直近10秒を基準。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
import time
from django.utils import timezone
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers

from .models import Application, ApprovalStatus

POLL_MAX_WAIT_SECONDS = 25
POLL_INTERVAL_SECONDS = 1.0


class ApplicationLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = [
            'id', 'status', 'updated_at', 'applicant', 'approver',
            'approval_comment', 'comment', 'approved_at'
        ]


def build_scope_q(user, scope: str):
    if scope == 'my':
        return Q(applicant=user.username)
    if scope == 'pending':
        return Q(approver=user.username, status=ApprovalStatus.PENDING)
    if scope == 'history':
        return Q(approver=user.username) & Q(status__in=[ApprovalStatus.APPROVED, ApprovalStatus.REJECTED])
    # default kanban
    return Q(applicant=user.username) | Q(approver=user.username)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def poll_updates(request):
    user = request.user
    scope = request.query_params.get('scope', 'kanban')
    raw_since = request.query_params.get('since')
    if raw_since:
        try:
            since_dt = datetime.fromisoformat(raw_since.replace('Z', '+00:00'))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=dt_timezone.utc)
        except Exception:
            since_dt = timezone.now() - timedelta(seconds=10)
    else:
        since_dt = timezone.now() - timedelta(seconds=10)

    start = time.time()
    latest_seen = since_dt
    serialized = []
    scope_q = build_scope_q(user, scope)

    while True:
        qs = (Application.objects
              .filter(scope_q)
              .filter(updated_at__gt=since_dt)
              .order_by('updated_at')[:50])
        if qs:
            data = ApplicationLiteSerializer(qs, many=True).data
            serialized = data
            latest_seen = max(obj.updated_at for obj in qs)  # type: ignore[attr-defined]
            break
        if time.time() - start >= POLL_MAX_WAIT_SECONDS:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    return Response({
        'applications': serialized,
        'latest': latest_seen.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z'),
        'scope': scope,
        'backoff_hint': {
            'min_ms': 200,
            'max_ms': 2000,
            'strategy': 'exponential-jitter',
            'note': '連続空応答時はポーリング間隔を徐々に延長してください'
        }
    })
