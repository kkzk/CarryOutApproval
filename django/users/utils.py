"""承認者選択等のユーティリティ (カスタムUser対応)"""
from django.contrib.auth import get_user_model
from .ldap_service import LDAPReadOnlyService
from .models import UserSource


def get_approvers_for_user(user):
    """
    ユーザーの申請を承認できるユーザーのリストを取得
    同一のOUおよび上位のOUに所属するユーザーを検索
    """
    try:
        user_dn = getattr(user, 'ldap_dn', None)
        if not user_dn:
            return []
        ldap_service = LDAPReadOnlyService()
        ldap_approvers = ldap_service.get_approvers_for_dn(user_dn)
        django_approvers = []
        User = get_user_model()
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
    """LDAP情報からローカルユーザーを取得/作成しフィールド更新"""
    User = get_user_model()
    user, created = User.objects.get_or_create(username=username, defaults={
        'email': email,
        'first_name': (display_name.split(' ')[0] if ' ' in display_name else display_name),
        'last_name': (display_name.split(' ', 1)[1] if ' ' in display_name else ''),
    })
    if created:
        user.set_unusable_password()
    # LDAPフィールド更新
    changed = False
    if ldap_dn and user.ldap_dn != ldap_dn:
        user.ldap_dn = ldap_dn
        changed = True
    if user.source != UserSource.LDAP:
        user.source = UserSource.LDAP
        changed = True
    if changed:
        user.save(update_fields=['ldap_dn', 'source'])
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
