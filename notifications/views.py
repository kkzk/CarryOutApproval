from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta, timezone as dt_timezone
from django.db.models import Q
import time


POLL_MAX_WAIT_SECONDS = 25  # 典型的な 30s タイムアウト未満 (ブラウザ/リバースプロキシ互換)
POLL_INTERVAL_SECONDS = 1.0  # DB 負荷抑制のため 1 秒間隔


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def broadcast_application_state(request, application_id: int):
    """申請の最新状態を申請者/承認者へWebSocket再送

    冪等であり、UI がズレた時の手動同期やデバッグ用途。
    """
    from applications.models import Application
    application = get_object_or_404(Application, id=application_id)
    from .services import NotificationService
    NotificationService.broadcast_application_state(application)
    return Response({'status': 'queued', 'application_id': application.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def poll_kanban_updates(request):
    """カンバン状態ロングポーリングエンドポイント

    クライアントはクエリ文字列で `since` (ISO8601) を渡す。なければ直近10秒を基準。
    `since` 以降に applicant / approver として自分が関係する Application の updated_at が更新されていれば
    その差分 (全件でなく変更分) を返却。なければ最大 POLL_MAX_WAIT_SECONDS まで待機。

    レスポンス:
    {
      "applications": [ { ApplicationSerializer データ ... }, ... ],
      "latest": "2025-08-17T12:34:56.789012Z"  # サーバ側で観測した最新 updated_at (次回 since に利用)
    }
    changes が空配列の場合はタイムアウトもしくは変化無し。
    """
    from applications.models import Application
    from rest_framework import serializers
    from applications.models import Application

    # 軽量シリアライザ: 必要最小限のみ返却
    class ApplicationLiteSerializer(serializers.ModelSerializer):
        class Meta:
            model = Application
            fields = [
                'id', 'status', 'updated_at', 'applicant', 'approver',
                'approval_comment', 'comment', 'approved_at'
            ]

    user = request.user
    raw_since = request.query_params.get('since')
    if raw_since:
        try:
            # ISO8601 -> aware datetime (Z を +00:00 に置換)
            since_dt = datetime.fromisoformat(raw_since.replace('Z', '+00:00'))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=dt_timezone.utc)
        except Exception:
            since_dt = timezone.now() - timedelta(seconds=10)
    else:
        since_dt = timezone.now() - timedelta(seconds=10)

    # ループで変更検知
    start = time.time()
    latest_seen = since_dt
    serialized = []
    while True:
        qs = (Application.objects
              .filter(Q(applicant=user.username) | Q(approver=user.username))
              .filter(updated_at__gt=since_dt)
              .order_by('updated_at')[:50])  # 1 回で最大 50 件まで
        if qs:
            data = ApplicationLiteSerializer(qs, many=True).data
            serialized = data
            # 最新 updated_at を記録
            latest_seen = max(obj.updated_at for obj in qs)  # type: ignore[attr-defined]
            break
        if time.time() - start >= POLL_MAX_WAIT_SECONDS:
            # タイムアウト -> 空返却
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    return Response({
        'applications': serialized,
        'latest': latest_seen.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z'),
        'backoff_hint': {
            'min_ms': 200,
            'max_ms': 2000,
            'strategy': 'exponential-jitter',
            'note': 'クライアントは連続空応答時にポーリング間隔を段階的に伸ばしてください'
        }
    })
