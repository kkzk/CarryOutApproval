from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'テストユーザーを作成する'

    def handle(self, *args, **options):
        test_users = [
            {
                'username': 'user001',
                'password': 'password123',
                'first_name': '太郎',
                'last_name': '田中',
                'email': 'tanaka@example.com',
                'department_code': 'DEPT001',
            },
            {
                'username': 'user002',
                'password': 'password123',
                'first_name': '花子',
                'last_name': '佐藤',
                'email': 'sato@example.com',
                'department_code': 'DEPT002',
            },
            {
                'username': 'user003',
                'password': 'password123',
                'first_name': '一郎',
                'last_name': '鈴木',
                'email': 'suzuki@example.com',
                'department_code': 'DEPT001',
            },
            {
                'username': 'admin',
                'password': 'admin123',
                'first_name': '管理者',
                'last_name': 'システム',
                'email': 'admin@example.com',
                'department_code': 'ADMIN',
                'is_staff': True,
                'is_superuser': True,
            },
        ]

        for user_data in test_users:
            username = user_data['username']
            
            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.WARNING(f'ユーザー {username} は既に存在します。')
                )
                continue

            # パスワードを取り出し
            password = user_data.pop('password')
            
            # 管理者フラグを取り出し
            is_staff = user_data.pop('is_staff', False)
            is_superuser = user_data.pop('is_superuser', False)
            
            # ユーザーを作成
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                email=user_data['email'],
                department_code=user_data['department_code'],
            )
            
            # 管理者フラグを設定
            if is_staff:
                user.is_staff = True
            if is_superuser:
                user.is_superuser = True
            user.save()

            self.stdout.write(
                self.style.SUCCESS(f'ユーザー {username} を作成しました。')
            )
