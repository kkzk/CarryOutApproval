from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'applications'

router = DefaultRouter()
router.register('', views.ApplicationViewSet)

urlpatterns = [
    # Template views - 詳細なパターンを先に配置
    path('<int:pk>/detail/', views.application_detail_modal, name='application-detail-modal'),
    path('<int:application_id>/file/<int:file_id>/open/', views.open_file, name='open-file'),
    path('<int:application_id>/file/open/', views.open_file, name='open-file-legacy'),
    path('create/', views.create_application, name='create-application'),
    path('list/', views.application_list, name='application-list'),
    path('admin/list/', views.admin_application_list, name='admin-application-list'),
    path('my/', views.my_applications_list, name='my-applications-list'),
    path('pending/', views.pending_approvals, name='pending-approvals'),
    path('approval/', views.approval_list, name='approval-list'),
    path('approval/history/', views.my_approval_history, name='my-approval-history'),
    path('mark-file-reviewed/', views.mark_file_reviewed, name='mark-file-reviewed'),
    
    # API endpoints
    path('api/', include(router.urls)),
    path('api/my/', views.MyApplicationListView.as_view(), name='api-my-applications'),
    path('api/pending/', views.PendingApplicationListView.as_view(), name='api-pending-applications'),
    
    # デフォルト表示（最後に配置）
    path('', views.default_view, name='default-view'),
]
