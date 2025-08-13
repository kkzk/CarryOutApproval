from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.sessions.models import Session
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from .serializers import UserSerializer
from .session_manager import SessionManager

User = get_user_model()


class CurrentUserView(generics.RetrieveAPIView):
    """現在のユーザー情報を取得"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class UserSearchView(generics.ListAPIView):
    """ユーザー検索"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        department = self.request.query_params.get('department', '')
        
        queryset = User.objects.filter(is_active=True)
        
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            )
        
        if department:
            queryset = queryset.filter(department_code=department)
        
        return queryset.order_by('username')[:50]  # 最大50件まで


class LoginView(View):
    """ログイン画面とログイン処理"""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('applications:kanban-board')
        return render(request, 'users/login.html')
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_active:
                # Django標準のlogin関数を使用（自動的にセッションが作成される）
                login(request, user)
                
                next_url = request.GET.get('next', 'applications:kanban-board')
                return redirect(next_url)
            else:
                messages.error(request, 'ユーザー名またはパスワードが間違っています。')
        else:
            messages.error(request, 'ユーザー名とパスワードを入力してください。')
        
        return render(request, 'users/login.html')


class LogoutView(View):
    """ログアウト処理（Django標準機能を使用）"""
    
    def get(self, request):
        return self._logout_user(request)
    
    def post(self, request):
        return self._logout_user(request)
    
    def _logout_user(self, request):
        """ログアウト処理の実装"""
        if request.user.is_authenticated:
            # Django標準のlogout関数を使用（セッションを適切に処理）
            logout(request)
            messages.success(request, 'ログアウトしました。')
        else:
            messages.info(request, '既にログアウトしています。')
            
        return redirect('users:login')


class SessionManagementView(View):
    """セッション管理画面"""
    
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('users:login')
            
        # ユーザーのアクティブセッション一覧
        user_sessions = SessionManager.get_user_sessions(request.user)
        current_session_key = request.session.session_key
        
        # 現在のセッションにマーク
        for session in user_sessions:
            session['is_current'] = session['session_key'] == current_session_key
        
        context = {
            'user_sessions': user_sessions,
            'current_session_key': current_session_key,
        }
        
        return render(request, 'users/session_management.html', context)
    
    def post(self, request):
        """他のセッションを削除"""
        if not request.user.is_authenticated:
            return redirect('users:login')
            
        action = request.POST.get('action')
        session_key = request.POST.get('session_key')
        
        if action == 'delete_session' and session_key:
            if session_key != request.session.session_key:
                if SessionManager.delete_session(session_key):
                    messages.success(request, 'セッションを削除しました。')
                else:
                    messages.error(request, 'セッションの削除に失敗しました。')
            else:
                messages.error(request, '現在のセッションは削除できません。')
                
        elif action == 'delete_others':
            deleted_count = SessionManager.delete_other_user_sessions(
                request.user, 
                request.session.session_key
            )
            messages.success(request, f'{deleted_count}個の他のセッションを削除しました。')
        
        return redirect('users:session-management')
