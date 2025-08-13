from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('unread/', views.UnreadNotificationListView.as_view(), name='unread'),
    path('<int:notification_id>/read/', views.mark_notification_as_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_notifications_as_read, name='mark_all_read'),
]
