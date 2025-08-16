"""承認者選択等のユーティリティ (カスタムUser対応)

ldap_service を廃止し、認証時に自動生成された User レコード (同一OU / 上位OU) を
直接参照して承認候補を返す方式に変更。
"""
from django.contrib.auth import get_user_model
from django.db import models  # Q 利用
from .models import UserSource


def get_approvers_for_user(user):
    """User テーブルだけを用いて承認候補を返す。

    ロジック:
      - 同じ department_code の他ユーザ
      - parent_department_code があれば、その OU を department_code に持つユーザ
    """
    try:
        User = get_user_model()
        dept = getattr(user, 'department_code', '') or ''
        parent = getattr(user, 'parent_department_code', '') or ''
        if not dept and not parent:
            return []
        qs = User.objects.filter(is_active=True)
        cond = models.Q()
        if dept:
            cond |= models.Q(department_code=dept)
        if parent:
            cond |= models.Q(department_code=parent)
        candidates = (
            qs.filter(cond)
              .exclude(pk=user.pk)
              .order_by('username')[:100]
        )
        results = []
        for u in candidates:  # type: ignore[assignment]
            results.append({
                'user': u,
                'username': getattr(u, 'username', ''),  # type: ignore[attr-defined]
                'display_name': (f"{getattr(u,'first_name','')} {getattr(u,'last_name','')}".strip() or getattr(u,'username','')),  # type: ignore[attr-defined]
                'email': getattr(u, 'email', ''),  # type: ignore[attr-defined]
                'ou': getattr(u, 'department_code', ''),  # type: ignore[attr-defined]
            })
        return results
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
    if ldap_dn and getattr(user, 'ldap_dn', None) != ldap_dn:  # type: ignore[attr-defined]
        setattr(user, 'ldap_dn', ldap_dn)  # type: ignore[attr-defined]
        changed = True
    if getattr(user, 'source', None) != UserSource.LDAP:  # type: ignore[attr-defined]
        setattr(user, 'source', UserSource.LDAP)  # type: ignore[attr-defined]
        changed = True
    if changed:
        user.save(update_fields=['ldap_dn', 'source'])
    return user


def test_ldap_connection():  # 互換: 旧API呼び出し対応 (常にTrue返却)
    return True


def sync_ldap_users():
    """
    Active Directoryからユーザーリストを同期
    管理コマンドから実行することを想定
    """
    # 実装は必要に応じて
    pass  # 旧仕様のまま (自動生成に移行)
