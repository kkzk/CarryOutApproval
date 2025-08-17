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
    # シンプル化: フラグや重複抑止を排除し常にイベント送信
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
    def broadcast_application_state(application):
        """申請の現在状態を申請者・承認者双方にブロードキャスト (重複除去)

        applicant と approver が同一ユーザ名の場合は 1 回のみ送信。
        """
        unique_usernames = []
        for username in [application.applicant, application.approver]:
            if username and username not in unique_usernames:
                unique_usernames.append(username)
        for username in unique_usernames:
            NotificationService.send_kanban_update_notification(
                user=username,
                action='application_state',
                application=application
            )
