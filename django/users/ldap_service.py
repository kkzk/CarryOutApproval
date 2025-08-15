"""LDAP 認証以外の読み取り系操作 (承認者取得等) 専用サービス。

Django AUTHENTICATION_BACKENDS に登録する ModelBackend 実装からは純粋に
ユーザ認証の責務のみを扱いたいため、承認者探索等を分離する。
"""
from __future__ import annotations
from typing import List
from dataclasses import dataclass
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

@dataclass
class Approver:
    username: str
    display_name: str
    email: str
    dn: str
    ou: str

    def to_dict(self):
        return {
            'username': self.username,
            'display_name': self.display_name,
            'email': self.email,
            'dn': self.dn,
            'ou': self.ou,
        }

class LDAPReadOnlyService:
    """サービスアカウント (Bind DN) を利用した読み取り専用操作。
    認証バックエンドからは使用しない (利用者資格情報のみでの bind 方針のため)。
    """
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        return {
            'server': getattr(settings, 'LDAP_SERVER_URL', getattr(settings, 'LDAP_AUTH_URL', 'ldap://localhost:389')),
            'search_base': getattr(settings, 'LDAP_SEARCH_BASE', getattr(settings, 'LDAP_AUTH_SEARCH_BASE', 'DC=company,DC=com')),
            'service_user': getattr(settings, 'LDAP_BIND_DN', getattr(settings, 'LDAP_AUTH_CONNECTION_USERNAME', None)),
            'service_password': getattr(settings, 'LDAP_BIND_PASSWORD', getattr(settings, 'LDAP_AUTH_CONNECTION_PASSWORD', None)),
        }

    def get_approvers_for_dn(self, user_dn: str) -> List[dict]:
        try:
            if not self.config['service_user']:
                logger.error("LDAP service account not configured for approver lookup")
                return []
            from ldap3 import Server, Connection, ALL, SUBTREE, LEVEL
            server = Server(self.config['server'], get_info=ALL)
            conn = Connection(server, user=self.config['service_user'], password=self.config['service_password'])
            if not conn.bind():
                logger.error("LDAP service bind failed for approver lookup | server=%s", self.config['server'])
                return []
            ou_list = self._extract_ou_hierarchy(user_dn)[:2]
            approvers: List[Approver] = []
            for idx, ou_dn in enumerate(ou_list):
                scope = SUBTREE if idx == 0 else LEVEL
                if conn.search(
                    search_base=ou_dn,
                    search_filter='(&(objectClass=user)(!(objectClass=computer)))',
                    search_scope=scope,
                    attributes=['sAMAccountName', 'cn', 'mail', 'distinguishedName']
                ):
                    for entry in conn.entries:
                        username = str(getattr(entry, 'sAMAccountName', '') or '')
                        display_name = str(getattr(entry, 'cn', '') or '')
                        if not (username and display_name):
                            continue
                        approvers.append(
                            Approver(
                                username=username,
                                display_name=display_name,
                                email=str(getattr(entry, 'mail', '') or ''),
                                dn=str(getattr(entry, 'distinguishedName', '') or ''),
                                ou=ou_dn,
                            )
                        )
            conn.unbind()
            return [a.to_dict() for a in approvers]
        except Exception:
            logger.exception("Error during approver lookup | user_dn=%s", user_dn)
            return []

    def _extract_ou_hierarchy(self, user_dn: str):
        ou_parts = []
        dc_parts = []
        for part in user_dn.split(','):
            p = part.strip()
            if p.startswith('OU='):
                ou_parts.append(p)
            elif p.startswith('DC='):
                dc_parts.append(p)
        base_dn = ','.join(dc_parts)
        ou_list = [','.join(ou_parts[i:] + dc_parts) for i in range(len(ou_parts))]
        if base_dn and base_dn not in ou_list:
            ou_list.append(base_dn)
        return ou_list
