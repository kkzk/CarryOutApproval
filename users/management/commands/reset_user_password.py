from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
import secrets

class Command(BaseCommand):
    help = "指定ユーザのパスワードを再設定する ( --username と --password / 自動生成 )"

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='対象ユーザー名')
        parser.add_argument('--password', help='新しいパスワード (未指定なら自動生成)')
        parser.add_argument('--show', action='store_true', help='自動生成時にパスワードを表示 (CI等では避ける)')
        parser.add_argument('--force', action='store_true', help='パスワードバリデータをスキップして強制的に設定')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        password = options.get('password')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"ユーザー '{username}' は存在しません。")

        generated = False
        if not password:
            # 十分な複雑性: 24文字英数+記号 (URL安全)
            password = secrets.token_urlsafe(18)
            generated = True

        # バリデーション: --force が指定されていない場合は Django のパスワードバリデータを実行
        if not options.get('force', False):
            try:
                from django.contrib.auth.password_validation import validate_password
                validate_password(password, user)
            except Exception as e:  # noqa: BLE001
                raise CommandError(f"パスワード検証エラー: {e}\n短いパスワードを設定するには --force を使用してください。")

        # 実際のパスワード設定 (set_password は直接ハッシュを設定するためバリデータ適用は任意)
        user.set_password(password)
        user.save(update_fields=['password'])

        if generated:
            if options['show']:
                self.stdout.write(self.style.SUCCESS(f"ユーザー '{username}' の新パスワード(自動生成): {password}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"ユーザー '{username}' のパスワードを自動生成し設定しました (--show で表示可能)。"))
        else:
            self.stdout.write(self.style.SUCCESS(f"ユーザー '{username}' のパスワードを更新しました。"))

        self.stdout.write("ログイン後は適切なパスワードポリシに従い変更してください。")
