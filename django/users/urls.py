from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('sessions/', views.SessionManagementView.as_view(), name='session-management'),
    path('me/', views.CurrentUserView.as_view(), name='current-user'),
    path('search/', views.UserSearchView.as_view(), name='user-search'),
    path('approvers/resync/', views.resync_and_fetch_approvers, name='approvers-resync'),
]
