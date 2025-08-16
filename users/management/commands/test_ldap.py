from django.core.management.base import BaseCommand
from django.conf import settings
from users.backends import WindowsLDAPBackend
from users.utils import get_approvers_for_user


class Command(BaseCommand):
    help = 'Test LDAP connection and authentication'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username to test')
        parser.add_argument('--password', type=str, help='Password to test')
        parser.add_argument('--mock', action='store_true', help='Test with mock LDAP backend')

    def handle(self, *args, **options):
        username = options.get('username')
        password = options.get('password')
        use_mock = options.get('mock', False)

        backend = None
        if use_mock:
            self.stdout.write('Testing Mock LDAP Backend...')
            # TODO: モックバックエンド実装時に差し替え
        else:
            self.stdout.write('Testing Windows LDAP Backend...')
            backend = WindowsLDAPBackend()

        # LDAP設定の表示 (統一設定名で出力・後方互換考慮)
        self.stdout.write(f'LDAP Server URL: {getattr(settings, "LDAP_SERVER_URL", getattr(settings, "LDAP_AUTH_URL", "Not configured"))}')
        self.stdout.write(f'LDAP Domain: {getattr(settings, "LDAP_DOMAIN", "Not configured")}')
        self.stdout.write(f'LDAP Search Base: {getattr(settings, "LDAP_SEARCH_BASE", getattr(settings, "LDAP_AUTH_SEARCH_BASE", "Not configured"))}')
        self.stdout.write(f'LDAP Bind DN: {getattr(settings, "LDAP_BIND_DN", getattr(settings, "LDAP_AUTH_CONNECTION_USERNAME", "Not configured"))}')

        if username and password and backend:
            self.stdout.write(f'Testing authentication for user: {username}')
            try:
                # 型チェッカー回避: manage.py コマンドから直接呼ぶため request は None
                user = backend.authenticate(request=None, username=username, password=password)  # type: ignore[arg-type]
                if user:
                    self.stdout.write(self.style.SUCCESS(f'Authentication successful: {user.username}'))
                    self.stdout.write(f'Email: {user.email}')
                    self.stdout.write(f'Full Name: {user.first_name} {user.last_name}')
                    if getattr(user, 'ldap_dn', None):
                        self.stdout.write(f'LDAP DN: {user.ldap_dn}')
                        # department_name / title は廃止済みフィールドのため出力抑止
                        self.stdout.write('\nTesting approver search...')
                        approvers = get_approvers_for_user(user)
                        if approvers:
                            self.stdout.write(f'Found {len(approvers)} potential approvers:')
                            for approver in approvers[:5]:
                                self.stdout.write(f'  - {approver["display_name"]} ({approver["username"]}) - {approver["email"]}')
                        else:
                            self.stdout.write('No approvers found')
                    else:
                        self.stdout.write('No LDAP attributes synced yet')
                else:
                    self.stdout.write(self.style.ERROR('Authentication failed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Authentication error: {str(e)}'))
        else:
            self.stdout.write(self.style.WARNING('No username/password provided or backend unavailable. Use --username and --password.'))

        # 設定テスト (認証しない場合)
        if backend is not None:
            try:
                from ldap3 import Server
                server_url = getattr(settings, 'LDAP_SERVER_URL', getattr(settings, 'LDAP_AUTH_URL', 'ldap://localhost:389'))
                Server(server_url)  # オブジェクト生成テスト
                self.stdout.write(self.style.SUCCESS(f'ldap3 server object created: {server_url}'))
            except ImportError:
                self.stdout.write(self.style.ERROR('ldap3 library is not installed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating LDAP server object: {str(e)}'))

        self.stdout.write('\nUsage examples:')
        self.stdout.write('  python manage.py test_ldap --username testuser --password testpass')
        self.stdout.write('  python manage.py test_ldap --username user1_1 --password pass1_1 --mock')
        self.stdout.write('  python manage.py test_ldap  # Just test configuration')
