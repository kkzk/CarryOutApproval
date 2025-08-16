"""
URL configuration for carry_out_approval project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.shortcuts import render

def root_redirect(request):
    """ルートURLから適切なページにリダイレクト"""
    if request.user.is_authenticated:
        return redirect('applications:kanban-board')
    else:
        return redirect('users:login')

def websocket_test(request):
    """WebSocket接続テストページ"""
    return render(request, 'websocket_test.html')

urlpatterns = [
    path('', root_redirect, name='root'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('applications/', include('applications.urls')),
    path('api/audit/', include('audit.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('websocket-test/', websocket_test, name='websocket-test'),
]

# 開発環境でのstatic・mediaファイル配信
if settings.DEBUG:
    from django.contrib.staticfiles.views import serve
    from django.views.static import serve as static_serve
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # 開発環境では django.contrib.staticfiles を使用
    urlpatterns += [
        path('static/<path:path>', serve),
    ]
