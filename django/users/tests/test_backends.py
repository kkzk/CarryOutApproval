from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from ldap3 import SUBTREE, LEVEL

from users.backends import WindowsLDAPBackend


class ApproverBackendTests(TestCase):
    """WindowsLDAPBackend.get_approvers_for_user のテスト"""

    def _build_entry(self, username, display_name, email, dn):
        e = MagicMock()
        e.sAMAccountName = username
        e.cn = display_name
        e.mail = email
        e.distinguishedName = dn
        return e

    @override_settings(
        LDAP_SERVER_URL="ldap://ldap.example.com:389",
        LDAP_SEARCH_BASE="DC=example,DC=com",
        LDAP_BIND_DN="CN=svc,DC=example,DC=com",
        LDAP_BIND_PASSWORD="secret",
    )
    @patch("users.backends.WindowsLDAPBackend._extract_ou_hierarchy")
    @patch("ldap3.Connection")
    @patch("ldap3.Server")
    def test_collects_approvers_across_ou_levels(self, mock_server, mock_conn_cls, mock_extract):
        backend = WindowsLDAPBackend()
        user_dn = "CN=Alice,OU=Dept1,OU=Div,DC=example,DC=com"

        # 下位->上位の返却 (実際利用するのは先頭2つ: 自OU + 親OU)
        mock_extract.return_value = [
            "OU=Dept1,OU=Div,DC=example,DC=com",
            "OU=Div,DC=example,DC=com",
            "DC=example,DC=com",
        ]

        # Connection モック設定
        mock_conn = MagicMock()
        mock_conn.bind.return_value = True

        def search_side_effect(search_base=None, search_filter=None, search_scope=None, attributes=None):
            if search_base and search_base.startswith("OU=Dept1"):
                mock_conn.entries = [
                    self._build_entry(
                        "bob", "Bob Builder", "bob@example.com", "CN=Bob,OU=Dept1,OU=Div,DC=example,DC=com"
                    )
                ]
            elif search_base and search_base.startswith("OU=Div"):
                mock_conn.entries = [
                    self._build_entry(
                        "charlie", "Charlie Chaplin", "charlie@example.com", "CN=Charlie,OU=Div,DC=example,DC=com"
                    )
                ]
            else:
                mock_conn.entries = []
            return True

        mock_conn.search.side_effect = search_side_effect
        mock_conn_cls.return_value = mock_conn

        approvers = backend.get_approvers_for_user(user_dn)

        # 件数: 自OU + 親OU
        self.assertEqual(len(approvers), 2)
        self.assertSetEqual({a['username'] for a in approvers}, {"bob", "charlie"})

        # スコープ: 1回目 SUBTREE, 2回目 LEVEL
        self.assertEqual(mock_conn.search.call_count, 2)
        scopes = [kw['search_scope'] for _, kw in mock_conn.search.call_args_list]
        self.assertEqual(scopes, [SUBTREE, LEVEL])
        mock_conn.unbind.assert_called_once()

    @override_settings(
        LDAP_SERVER_URL="ldap://ldap.example.com:389",
        LDAP_SEARCH_BASE="DC=example,DC=com",
        LDAP_BIND_DN="CN=svc,DC=example,DC=com",
        LDAP_BIND_PASSWORD="secret",
    )
    @patch("ldap3.Connection")
    @patch("ldap3.Server")
    def test_bind_failure_returns_empty(self, mock_server, mock_conn_cls):
        backend = WindowsLDAPBackend()
        user_dn = "CN=Alice,OU=Dept1,OU=Div,DC=example,DC=com"
        mock_conn = MagicMock()
        mock_conn.bind.return_value = False
        mock_conn_cls.return_value = mock_conn
        self.assertEqual(backend.get_approvers_for_user(user_dn), [])
        mock_conn.search.assert_not_called()
        mock_conn.unbind.assert_not_called()

    @override_settings(
        LDAP_SERVER_URL="ldap://ldap.example.com:389",
        LDAP_SEARCH_BASE="DC=example,DC=com",
        LDAP_BIND_DN=None,
        LDAP_BIND_PASSWORD=None,
    )
    def test_missing_service_account_returns_empty(self):
        backend = WindowsLDAPBackend()
        user_dn = "CN=Alice,OU=Dept1,OU=Div,DC=example,DC=com"
        self.assertEqual(backend.get_approvers_for_user(user_dn), [])

    @override_settings(
        LDAP_SERVER_URL="ldap://ldap.example.com:389",
        LDAP_SEARCH_BASE="DC=example,DC=com",
        LDAP_BIND_DN="CN=svc,DC=example,DC=com",
        LDAP_BIND_PASSWORD="secret",
    )
    @patch("ldap3.Connection")
    @patch("ldap3.Server")
    def test_exception_handling_returns_empty(self, mock_server, mock_conn_cls):
        backend = WindowsLDAPBackend()
        user_dn = "CN=Alice,OU=Dept1,OU=Div,DC=example,DC=com"
        mock_conn = MagicMock()
        mock_conn.bind.return_value = True

        def raise_err(*a, **kw):
            raise RuntimeError("LDAP search error")

        mock_conn.search.side_effect = raise_err
        mock_conn_cls.return_value = mock_conn
        self.assertEqual(backend.get_approvers_for_user(user_dn), [])
        mock_conn.unbind.assert_not_called()
