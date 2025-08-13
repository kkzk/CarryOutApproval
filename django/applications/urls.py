from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'applications'

router = DefaultRouter()
router.register('', views.ApplicationViewSet)

urlpatterns = [
    # Template views - 詳細なパターンを先に配置
    path('<int:pk>/detail/', views.application_detail_modal, name='application-detail-modal'),
    path('<int:pk>/card/', views.application_card, name='application-card'),
    path('create/', views.create_application, name='create-application'),
    path('list/', views.application_list, name='application-list'),
    path('admin/list/', views.admin_application_list, name='admin-application-list'),
    path('my/', views.my_applications, name='my-applications-list'),
    path('my/board/', views.my_applications_board, name='my-applications-board'),
    path('pending/', views.pending_approvals, name='pending-approvals'),
    path('approval/board/', views.approval_board, name='approval-board'),
    path('approval/history/', views.my_approval_history, name='my-approval-history'),
    path('update-status/', views.update_application_status, name='update-application-status'),
    
    # API endpoints
    path('api/', include(router.urls)),
    path('api/my/', views.MyApplicationListView.as_view(), name='api-my-applications'),
    path('api/pending/', views.PendingApplicationListView.as_view(), name='api-pending-applications'),
    
    # カンバンボード（最後に配置）
    path('', views.kanban_board, name='kanban-board'),
]
