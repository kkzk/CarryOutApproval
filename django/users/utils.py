"""
承認者選択のためのユーティリティ関数
"""
from django.contrib.auth.models import User
from .ldap_service import LDAPReadOnlyService
from .models import UserProfile, UserSource


def get_approvers_for_user(user):
    """
    ユーザーの申請を承認できるユーザーのリストを取得
    同一のOUおよび上位のOUに所属するユーザーを検索
    """
    try:
        if hasattr(user, 'profile') and getattr(user.profile, 'ldap_dn', None):
            user_dn = user.profile.ldap_dn
        else:
            return []
        ldap_service = LDAPReadOnlyService()
        ldap_approvers = ldap_service.get_approvers_for_dn(user_dn)
        django_approvers = []
        for ldap_user in ldap_approvers:
            try:
                django_user = User.objects.get(username=ldap_user['username'])
                django_approvers.append({
                    'user': django_user,
                    'username': django_user.username,
                    'display_name': ldap_user['display_name'],
                    'email': ldap_user['email'],
                    'ou': ldap_user['ou']
                })
            except User.DoesNotExist:
                django_approvers.append({
                    'user': None,
                    'username': ldap_user['username'],
                    'display_name': ldap_user['display_name'],
                    'email': ldap_user['email'],
                    'ou': ldap_user['ou']
                })
        return django_approvers
    except Exception as e:  # noqa: BLE001
        print(f"Error getting approvers: {e}")
        return []


def create_user_from_ldap_info(username, display_name, email, ldap_dn):
    """
    LDAP情報からDjangoユーザーを作成
    """
    from django.contrib.auth.models import User
    
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # 新規ユーザー作成
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=display_name.split(' ')[0] if ' ' in display_name else display_name,
            last_name=display_name.split(' ', 1)[1] if ' ' in display_name else ''
        )
        user.set_unusable_password()
        user.save()

    # プロファイル更新/作成（常に実施）
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.source = UserSource.LDAP
    if ldap_dn:
        profile.ldap_dn = ldap_dn
    profile.save()
    
    return user


def test_ldap_connection():
    """
    LDAP接続のテスト
    """
    try:
        svc = LDAPReadOnlyService()
        svc.get_approvers_for_dn('CN=dummy,OU=Dummy,DC=example,DC=com')
        return True
    except Exception as e:  # noqa: BLE001
        print(f"LDAP connection test failed: {e}")
        return False


def sync_ldap_users():
    """
    Active Directoryからユーザーリストを同期
    管理コマンドから実行することを想定
    """
    # 実装は必要に応じて
    pass
