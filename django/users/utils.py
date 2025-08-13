"""
承認者選択のためのユーティリティ関数
"""
from django.contrib.auth.models import User
from .backends import WindowsLDAPBackend
from .models import UserProfile


def get_approvers_for_user(user):
    """
    ユーザーの申請を承認できるユーザーのリストを取得
    同一のOUおよび上位のOUに所属するユーザーを検索
    """
    try:
        # ユーザーのLDAP DNを取得
        if hasattr(user, 'profile') and user.profile.ldap_dn:
            user_dn = user.profile.ldap_dn
        else:
            # LDAP DNが無い場合は空のリストを返す
            return []
        
        # WindowsLDAP認証バックエンドを使用して承認者を取得
        backend = WindowsLDAPBackend()
        ldap_approvers = backend.get_approvers_for_user(user_dn)
        
        # LDAP情報をDjangoユーザーとマッチング
        django_approvers = []
        for ldap_user in ldap_approvers:
            try:
                django_user = User.objects.get(username=ldap_user['username'])
                django_approvers.append({
                    'user': django_user,
                    'display_name': ldap_user['display_name'],
                    'email': ldap_user['email'],
                    'ou': ldap_user['ou']
                })
            except User.DoesNotExist:
                # Djangoにユーザーが存在しない場合は、とりあえず情報だけ含める
                django_approvers.append({
                    'user': None,
                    'username': ldap_user['username'],
                    'display_name': ldap_user['display_name'],
                    'email': ldap_user['email'],
                    'ou': ldap_user['ou']
                })
        
        return django_approvers
        
    except Exception as e:
        print(f"Error getting approvers: {e}")
        # エラー時はモックバックエンドを使用
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
        
        # ユーザープロファイルを作成
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.ldap_dn = ldap_dn
        profile.save()
    
    return user


def test_ldap_connection():
    """
    LDAP接続のテスト
    """
    try:
        backend = WindowsLDAPBackend()
        # テスト用の認証を試行
        result = backend._authenticate_ldap3('testuser', 'testpass')
        return result is not None
    except Exception as e:
        print(f"LDAP connection test failed: {e}")
        return False


def sync_ldap_users():
    """
    Active Directoryからユーザーリストを同期
    管理コマンドから実行することを想定
    """
    # 実装は必要に応じて
    pass
