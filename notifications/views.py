from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """通知一覧API"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """現在のユーザーの通知のみを返す"""
        return Notification.objects.filter(recipient=self.request.user)


class UnreadNotificationListView(generics.ListAPIView):
    """未読通知一覧API"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """現在のユーザーの未読通知のみを返す"""
        return Notification.objects.filter(
            recipient=self.request.user,
            is_read=False
        )


@api_view(['POST'])
def mark_notification_as_read(request, notification_id):
    """通知を既読にする"""
    try:
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            recipient=request.user
        )
        notification.mark_as_read()
        return Response({'success': True})
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
def mark_all_notifications_as_read(request):
    """全ての通知を既読にする"""
    try:
        notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        )
        for notification in notifications:
            notification.mark_as_read()
        
        return Response({
            'success': True,
            'marked_count': notifications.count()
        })
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )
