from django.conf import settings
from django.contrib.auth import get_user_model
from django_rq import get_queue

User = get_user_model()


def _resolve_user(maybe_user_or_username):
    """文字列(ユーザ名)が渡された場合は User を取得。既に User ならそのまま返す。
    見つからない場合は None を返し、呼び出し側でスキップ判断。
    """
    if maybe_user_or_username is None:
        return None
    if hasattr(maybe_user_or_username, 'pk'):
        return maybe_user_or_username  # User インスタンス想定
    # 文字列としてユーザ名が来たケース
    username = str(maybe_user_or_username).strip()
    if not username:
        return None
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


class NotificationService:
    """リアルタイム(kanban)更新サービス

    永続通知(DB) は廃止し、WebSocket へのイベント送信のみを行う。
    """
    
    @staticmethod
    def create_notification(*args, **kwargs):  # 互換メソッド (何もしない)
        return None
    
    @staticmethod
    def send_real_time_notification(notification):  # 後方互換 no-op
        return
    
    @staticmethod
    def send_kanban_update_notification(user, action, application):
        """カンバンボード更新通知を送信"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        from django_rq import get_queue
        # user が文字列(username) の場合 User を取得して id に変換。存在しない場合は username グループ送信でフォールバック
        username_for_fallback = None
        user_id = None
        resolved = _resolve_user(user)
        if resolved is not None:
            user_id = resolved.id  # type: ignore[attr-defined]
            username_for_fallback = getattr(resolved, 'username', None)
        elif isinstance(user, int):
            user_id = user
        else:
            # 文字列ユーザ名（まだDBにユーザが存在しないケース）
            if isinstance(user, str) and user.strip():
                username_for_fallback = user.strip()
            else:
                return  # 送信不能

        q = get_queue('notifications')
        q.enqueue(
            'notifications.tasks.send_kanban_update',
            user_id=user_id,
            username=username_for_fallback,
            action=action,
            application_id=getattr(application, 'id'),  # type: ignore[arg-type]
        )
    
    @staticmethod
    def notify_new_application(application):
        """新規申請の通知"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        # 重複防止: 同一 application.id の new_application を短時間で多重送信しない
        try:
            from django_rq import get_queue
            q = get_queue('notifications')
            conn = q.connection
            key = f"notif:new_app:{application.id}"
            # 10秒以内の再送抑止 (SETNX)
            added = conn.set(key, '1', nx=True, ex=10)
            if not added:
                return  # 既に送信済み
        except Exception:
            # 失敗時はフォールバックでそのまま続行（最悪二重になるが通知欠落よりは許容）
            pass
        NotificationService.send_kanban_update_notification(
            user=application.approver,
            action='new_application',
            application=application
        )
    
    @staticmethod
    def notify_application_approved(application):
        """申請承認の通知"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        # 冪等化: 承認通知の重複送信防止 (5秒)
        try:
            from django_rq import get_queue
            q = get_queue('notifications')
            conn = q.connection
            key = f"notif:approved:{application.id}"
            added = conn.set(key, '1', nx=True, ex=5)
            if not added:
                return
        except Exception:
            pass
        # 永続通知は生成せず Kanban 更新のみ送信
        NotificationService.send_kanban_update_notification(
            user=application.applicant,
            action='application_approved',
            application=application
        )
    
    @staticmethod
    def notify_application_rejected(application):
        """申請却下の通知"""
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            return
        # 冪等化: 却下通知の重複送信防止 (5秒)
        try:
            from django_rq import get_queue
            q = get_queue('notifications')
            conn = q.connection
            key = f"notif:rejected:{application.id}"
            added = conn.set(key, '1', nx=True, ex=5)
            if not added:
                return
        except Exception:
            pass
        # 永続通知は生成せず Kanban 更新のみ送信
        NotificationService.send_kanban_update_notification(
            user=application.applicant,
            action='application_rejected',
            application=application
        )
