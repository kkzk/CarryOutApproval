import types
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings

from users.backends import WindowsLDAPBackend


class ApproverBackendTests(TestCase):
    """Tests for WindowsLDAPBackend.get_approvers_for_user.

    方針:
      - ldap3.Server / ldap3.Connection をモックして外部LDAPへ接続しない
      - _extract_ou_hierarchy の戻り値を制御することで search 呼び出し回数と結果マージを検証
    """

    def make_mock_connection(self, per_ou_entries):
        """per_ou_entries: {ou_dn: [ {username, display_name, email, dn}, ... ] }"""
        conn = MagicMock(name="MockConnection")
        conn.bound = True
        conn.bind.return_value = True

        def search_side_effect(search_base=None, search_filter=None, search_scope=None, attributes=None):  # noqa: D401
            entries_data = per_ou_entries.get(search_base, [])
            entry_objs = []
            for d in entries_data:
                e = types.SimpleNamespace()
                # ldap3 の Entry の属性アクセスを最低限再現
                e.sAMAccountName = d.get("username")
                e.cn = d.get("display_name")
                e.mail = d.get("email")
                e.distinguishedName = d.get("dn")
                entry_objs.append(e)
            conn.entries = entry_objs
            # True/False は検索ヒットしたか (0件でも True にする)
            return True

        conn.search.side_effect = search_side_effect
        conn.unbind.return_value = True
        return conn

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
        # 下位から上位順で返る設計 (テストでは 3 要素返すが実際使用されるのは先頭2つ)
        full_sequence = [
            "OU=Dept1,OU=Div,DC=example,DC=com",  # 自OU
            "OU=Div,DC=example,DC=com",           # 親OU
            "DC=example,DC=com",                  # ルート (使われない)
        ]
        mock_extract.return_value = full_sequence

        per_ou_entries = {
            full_sequence[0]: [
                {
                    "username": "bob",
                    "display_name": "Bob Builder",
                    "email": "bob@example.com",
                    "dn": "CN=Bob,OU=Dept1,OU=Div,DC=example,DC=com",
                }
            ],
            full_sequence[1]: [
                {
                    "username": "charlie",
                    "display_name": "Charlie Chaplin",
                    "email": "charlie@example.com",
                    "dn": "CN=Charlie,OU=Div,DC=example,DC=com",
                }
            ],
            full_sequence[2]: [
                {
                    "username": "rootuser",
                    "display_name": "Root User",
                    "email": "root@example.com",
                    "dn": "CN=Root User,DC=example,DC=com",
                }
            ],
        }
        mock_conn = self.make_mock_connection(per_ou_entries)
        mock_conn_cls.return_value = mock_conn

        approvers = backend.get_approvers_for_user(user_dn)
        # 仕様変更: 自OU + 親OU のみ (2件) を確認
        self.assertEqual(len(approvers), 2)
        usernames = {a["username"] for a in approvers}
        self.assertSetEqual(usernames, {"bob", "charlie"})

        mock_extract.assert_called_once_with(user_dn)
        self.assertEqual(mock_conn.search.call_count, 2)
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
        mock_conn.bind.return_value = False  # バインド失敗
        mock_conn_cls.return_value = mock_conn

        result = backend.get_approvers_for_user(user_dn)
        self.assertEqual(result, [])
        # bind 失敗時は search / unbind を呼ばない
        mock_conn.search.assert_not_called()
        mock_conn.unbind.assert_not_called()

    @override_settings(
        LDAP_SERVER_URL="ldap://ldap.example.com:389",
        LDAP_SEARCH_BASE="DC=example,DC=com",
        LDAP_BIND_DN=None,  # サービスアカウント未設定
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

        def raise_err(*a, **kw):  # noqa: D401
            raise RuntimeError("LDAP search error")

        # 正常バインド後、search で例外
        mock_conn = MagicMock()
        mock_conn.bind.return_value = True
        mock_conn.search.side_effect = raise_err
        mock_conn_cls.return_value = mock_conn

        result = backend.get_approvers_for_user(user_dn)
        self.assertEqual(result, [])
        mock_conn.unbind.assert_not_called()  # 例外経路では finally/unbind 無 (実装に依存)
