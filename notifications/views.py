from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404


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
