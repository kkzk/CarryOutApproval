"""Long Polling 移行後の後方互換ダミーサービス。

以前は RQ + WebSocket で push 配信を行っていたが、現在はクライアントが
`/notifications/poll/kanban/` に対し差分(Long Poll)取得するため、
サーバ側での明示的な push は不要となった。

残存する呼び出し箇所 (state_machine / views) を即時で削除せず、
段階的削除の安全策として no-op 実装を提供する。

最終段階では本ファイルごと削除予定。
"""


class NotificationService:  # pragma: no cover - 動作は no-op
    @staticmethod
    def create_notification(*_args, **_kwargs):
        return None

    @staticmethod
    def send_real_time_notification(_notification):
        return

    @staticmethod
    def send_kanban_update_notification(_user, _action, _application):
        return  # Long Polling で代替

    @staticmethod
    def broadcast_application_state(_application):
        return  # Long Polling で代替
