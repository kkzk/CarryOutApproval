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
from users.utils import get_approvers_for_user
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required


@login_required
def resync_and_fetch_approvers(request):
    """現在ログインユーザのLDAP情報を再同期し、承認者候補をJSONで返す"""
    import logging
    logger = logging.getLogger('users.backends')
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'method_not_allowed'}, status=405)

    user = request.user
    logger.debug("[resync] start user=%s", user.username)
    try:
        profile = getattr(user, 'profile', None)
        ldap_dn = getattr(profile, 'ldap_dn', '') if profile else ''
        if not ldap_dn:
            logger.warning("[resync] missing ldap_dn user=%s", user.username)
            return JsonResponse({'ok': False, 'error': 'ldap_dn_not_set', 'candidates': []}, status=400)
        from users.ldap_service import LDAPReadOnlyService
        approvers_raw = LDAPReadOnlyService().get_approvers_for_dn(ldap_dn) or []
        logger.debug("[resync] fetched count=%d", len(approvers_raw))
        cleaned = [
            {
                'username': a.get('username',''),
                'display_name': a.get('display_name') or a.get('username',''),
                'email': a.get('email',''),
                'ou': a.get('ou','')
            } for a in approvers_raw if a.get('username') and a.get('username') != user.username
        ]
        logger.debug("[resync] cleaned count=%d", len(cleaned))
        return JsonResponse({'ok': True, 'candidates': cleaned})
    except Exception as e:  # noqa: BLE001
        logger.exception("[resync] unexpected error user=%s", user.username)
        return JsonResponse({'ok': False, 'error': 'exception', 'detail': str(e)}, status=500)

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
        query = self.request.GET.get('q', '')
        department = self.request.GET.get('department', '')

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
                # 認証エラーメッセージがある場合は表示
                if hasattr(request, 'auth_error_messages') and request.auth_error_messages:
                    messages.error(request, request.auth_error_messages[0])
                else:
                    messages.error(request, 'ユーザー名またはパスワードが正しくありません。')
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
