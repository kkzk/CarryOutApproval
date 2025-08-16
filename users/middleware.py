from django.utils import timezone


class SessionManagementMiddleware:
    """セッション管理ミドルウェア（標準機能を使用）"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 認証済みユーザーのセッションに基本情報を記録（初回のみ）
        if (request.user.is_authenticated and 
            request.session.get('session_created') is None):
            request.session['session_created'] = timezone.now().isoformat()
            request.session['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:200]
            request.session['ip_address'] = request.META.get('REMOTE_ADDR', '')
        
        response = self.get_response(request)
        return response
