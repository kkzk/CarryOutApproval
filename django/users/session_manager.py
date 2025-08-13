from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class SessionManager:
    """セッション管理ユーティリティ（Django標準機能を活用）"""
    
    @staticmethod
    def get_user_sessions(user):
        """指定ユーザーのアクティブなセッション一覧を取得"""
        if not user or not user.is_authenticated:
            return []
        
        active_sessions = []
        sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
        for session in sessions:
            try:
                session_data = session.get_decoded()
                session_user_id = session_data.get('_auth_user_id')
                
                if session_user_id and int(session_user_id) == user.id:
                    active_sessions.append({
                        'session_key': session.session_key,
                        'expire_date': session.expire_date,
                        'session_data': session_data,
                        'created': session_data.get('session_created', None),
                        'user_agent': session_data.get('user_agent', 'Unknown'),
                        'ip_address': session_data.get('ip_address', 'Unknown')
                    })
            except Exception:
                continue
                
        return active_sessions
    
    @staticmethod
    def delete_session(session_key):
        """指定セッションを削除"""
        try:
            session = Session.objects.get(session_key=session_key)
            session.delete()
            return True
        except Session.DoesNotExist:
            return False
    
    @staticmethod
    def delete_other_user_sessions(user, current_session_key):
        """現在のセッション以外のユーザーセッションを削除（管理機能用）"""
        if not user or not user.is_authenticated:
            return 0
        
        deleted_count = 0
        sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
        for session in sessions:
            if session.session_key == current_session_key:
                continue
                
            try:
                session_data = session.get_decoded()
                session_user_id = session_data.get('_auth_user_id')
                
                if session_user_id and int(session_user_id) == user.id:
                    session.delete()
                    deleted_count += 1
            except Exception:
                continue
                
        return deleted_count
