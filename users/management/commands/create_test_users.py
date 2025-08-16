from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'テストユーザーを作成する'

    def handle(self, *args, **options):
        test_users = [
            {
                'username': 'admin',
                'password': 'admin123',
                'first_name': '管理者',
                'last_name': '',
                'email': 'admin@example.com',
                'department_code': '',
                'parent_department_code': 'PARENT-ROOT',  # 仮の上位所属コード
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'user001',
                'password': 'pass001',
                'first_name': '太郎',
                'last_name': '田中',
                'email': 'tanaka@example.com',
                'department_code': 'DEPT1000100',
                'parent_department_code': 'DEPT1000',  # 仮
            },
            {
                'username': 'user002',
                'password': 'pass002',
                'first_name': '花子',
                'last_name': '佐藤',
                'email': 'sato@example.com',
                'department_code': 'DEPT1000100',
                'parent_department_code': 'DEPT1000',  # 仮
            },
            {
                'username': 'user003',
                'password': 'pass003',
                'first_name': '一郎',
                'last_name': '鈴木',
                'email': 'suzuki@example.com',
                'department_code': 'DEPT1000',
                'parent_department_code': 'PARENT-ROOT',  # 仮
            },
        ]

        for user_data in test_users:
            username = user_data['username']
            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.WARNING(f'ユーザー {username} は既に存在します。')
                )
                continue

            password = user_data.pop('password')
            is_staff = user_data.pop('is_staff', False)
            is_superuser = user_data.pop('is_superuser', False)

            user = User(
                username=username,
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                email=user_data.get('email', ''),
                department_code=user_data.get('department_code', ''),
                parent_department_code=user_data.get('parent_department_code', ''),
            )
            user.set_password(password)
            if is_staff:
                user.is_staff = True  # type: ignore[attr-defined]
            if is_superuser:
                user.is_superuser = True  # type: ignore[attr-defined]
            user.save()

            self.stdout.write(
                self.style.SUCCESS(f'ユーザー {username} を作成しました。')
            )
