from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('broadcast/application/<int:application_id>/', views.broadcast_application_state, name='broadcast_application_state'),
    path('poll/kanban/', views.poll_kanban_updates, name='poll_kanban_updates'),
]
