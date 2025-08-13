from django.core.management.base import BaseCommand
from django.conf import settings
from users.backends import WindowsLDAPBackend


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

        if use_mock:
            self.stdout.write('Testing Mock LDAP Backend...')
            # ...existing code...
        else:
            self.stdout.write('Testing Windows LDAP Backend...')
            backend = WindowsLDAPBackend()

        # LDAP設定の表示
        self.stdout.write(f'LDAP Server: {getattr(settings, "LDAP_SERVER", "Not configured")}')
        self.stdout.write(f'LDAP Domain: {getattr(settings, "LDAP_DOMAIN", "Not configured")}')
        self.stdout.write(f'Search Base: {getattr(settings, "LDAP_SEARCH_BASE", "Not configured")}')

        if username and password:
            self.stdout.write(f'Testing authentication for user: {username}')
            
            try:
                user = backend.authenticate(None, username=username, password=password)
                if user:
                    self.stdout.write(self.style.SUCCESS(f'Authentication successful: {user.username}'))
                    self.stdout.write(f'Email: {user.email}')
                    self.stdout.write(f'Full Name: {user.first_name} {user.last_name}')
                    
                    # ユーザープロファイル情報の表示
                    if hasattr(user, 'profile'):
                        profile = user.profile
                        self.stdout.write(f'LDAP DN: {profile.ldap_dn}')
                        self.stdout.write(f'Department: {profile.department_name}')
                        self.stdout.write(f'Title: {profile.title}')
                        
                        # 承認者リストのテスト
                        self.stdout.write('\nTesting approver search...')
                        approvers = backend.get_approvers_for_user(profile.ldap_dn)
                        if approvers:
                            self.stdout.write(f'Found {len(approvers)} potential approvers:')
                            for approver in approvers[:5]:  # 最初の5人を表示
                                self.stdout.write(f'  - {approver["display_name"]} ({approver["username"]}) - {approver["email"]}')
                        else:
                            self.stdout.write('No approvers found')
                    else:
                        self.stdout.write('No user profile found')
                else:
                    self.stdout.write(self.style.ERROR('Authentication failed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Authentication error: {str(e)}'))
        else:
            self.stdout.write(self.style.WARNING('No username or password provided. Use --username and --password to test authentication'))
            
            # 設定のテスト
            if not use_mock:
                try:
                    # ldap3の動作確認
                    from ldap3 import Server, Connection
                    server_url = getattr(settings, 'LDAP_SERVER', 'ldap://localhost:389')
                    server = Server(server_url)
                    self.stdout.write(self.style.SUCCESS(f'ldap3 library is available and server object created for: {server_url}'))
                except ImportError:
                    self.stdout.write(self.style.ERROR('ldap3 library is not installed'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error creating LDAP server object: {str(e)}'))
            
            # モックLDAPサーバーの設定確認
            if use_mock:
                # ...existing code...
                try:
                    # モック用のJSONファイルの確認
                    import os
                    json_path = os.path.join(
                        settings.BASE_DIR.parent, 
                        'mockldap_server', 
                        'mock_ou_users.json'
                    )
                    if os.path.exists(json_path):
                        self.stdout.write(self.style.SUCCESS(f'Mock LDAP JSON file found: {json_path}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Mock LDAP JSON file not found: {json_path}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error checking mock LDAP file: {str(e)}'))

        self.stdout.write('\nUsage examples:')
        self.stdout.write('  python manage.py test_ldap --username testuser --password testpass')
        self.stdout.write('  python manage.py test_ldap --username user1_1 --password pass1_1 --mock')
        self.stdout.write('  python manage.py test_ldap  # Just test configuration')
