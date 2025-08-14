# Windows compatible LDAP backend using ldap3
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.conf import settings
import logging
from urllib.parse import urlparse
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class WindowsLDAPBackend(ModelBackend):
    """
    Windows対応のLDAP認証バックエンド（ldap3使用）
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
            
        # まずDjangoデフォルトのユーザーを確認
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(username=username)
            if user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            pass
        
        # Djangoにユーザーが存在しない場合、LDAP認証を実行
        return self._authenticate_ldap3(username, password)
    
    def _authenticate_ldap3(self, username, password):
        """利用者資格情報のみで Active Directory に直接バインドして認証。

        ポリシー: 管理用サービスアカウントを保持しない。ユーザ入力の ID/パスワードで安全チャネル( LDAPS / StartTLS ) を優先的に使用。
        試行順序:
          1. ユーザが \\ もしくは @ を含めて入力した場合はその形式を最優先
          2. NTLM (DOMAIN\\username)
          3. UPN (username@upn_suffix)
        いずれも失敗したら認証失敗。
        """
        try:
            from ldap3 import Server, Connection, ALL, NTLM, SUBTREE, Tls, SIMPLE
            import ssl

            # 1) 設定と基礎情報取得 (インライン化：_get_ldap_runtime_config 廃止)
            ldap_server_url = getattr(settings, 'LDAP_SERVER_URL', getattr(settings, 'LDAP_AUTH_URL', 'ldap://localhost:389'))
            search_base = getattr(settings, 'LDAP_SEARCH_BASE', getattr(settings, 'LDAP_AUTH_SEARCH_BASE', 'DC=example,DC=com'))
            domain = getattr(settings, 'LDAP_DOMAIN', '')
            upn_suffix = getattr(settings, 'LDAP_UPN_SUFFIX', None)
            use_ssl = bool(getattr(settings, 'LDAP_USE_SSL', False))
            force_starttls = bool(getattr(settings, 'LDAP_FORCE_STARTTLS', False))
            allow_plain = bool(getattr(settings, 'LDAP_ALLOW_PLAIN_FALLBACK', False))

            # 2) Server 準備
            host, port = self._parse_host_port(ldap_server_url, use_ssl)
            tls = self._build_tls(use_ssl, force_starttls, ssl)
            server = Server(host, port=port, use_ssl=use_ssl, get_info=ALL, tls=tls)
            host_is_ip = self._is_ipv4_like(host)

            # 3) 認証候補生成
            candidates = self._build_candidate_credentials(username, domain, upn_suffix)
            if not candidates:
                self._log_no_candidates(username, domain, upn_suffix, use_ssl, force_starttls, allow_plain)
                return None
            logger.debug(
                "LDAP bind candidates | user=%s domain=%s candidates=%s",
                username, domain or '', [(lbl, usr, auth) for lbl, usr, auth in candidates]
            )

            # 4) セキュアチャネル (StartTLS 強制条件調整)
            if not use_ssl and not force_starttls and not allow_plain:
                force_starttls = True

            last_errors = []  # (label, last_error, result)

            # 5) 試行ループ
            for label, bind_user, auth_label in candidates:
                try:
                    auth_method = NTLM if auth_label == 'NTLM' else SIMPLE
                    conn = Connection(
                        server,
                        user=bind_user,
                        password=password,
                        authentication=auth_method,
                        auto_bind=False,
                        raise_exceptions=False,
                    )
                    # StartTLS
                    if not use_ssl and force_starttls and not self._start_tls_if_needed(conn, host, bind_user, label, last_errors):
                        continue

                    # Bind
                    if not self._bind_connection(conn, host, host_is_ip, use_ssl, force_starttls, label, auth_method, last_errors):
                        continue

                    # Search user entry
                    entry = self._search_user_entry(conn, username, host, label, search_base, last_errors)
                    if not entry:
                        conn.unbind()
                        return None  # 元実装と同じ早期終了（検索失敗時）

                    # Django ユーザ作成/取得 + Profile 更新
                    user = self._get_or_create_local_user(username, entry, upn_suffix, domain)
                    self._update_user_profile(user, entry)

                    conn.unbind()
                    logger.info(
                        "LDAP auth success | user=%s attempt=%s bind_user=%s host=%s",
                        username, label, bind_user, host,
                        extra={'ldap_params': {'attempt': label, 'bind_user': bind_user}}
                    )
                    return user
                except Exception as e:  # noqa: BLE001
                    logger.debug(
                        "LDAP attempt exception | user=%s label=%s error=%s domain=%s", username, label, e, domain or ''
                    )
                    last_errors.append((label, str(e), {'description': 'exception'}))
                    continue

            # 6) 全失敗ログ
            self._log_all_attempt_fail(username, host, host_is_ip, domain, last_errors, use_ssl, force_starttls)
            return None
        except ImportError:
            logger.exception("ldap3 not installed | user=%s", username)
            return None
        except Exception:
            logger.exception("LDAP unexpected error | user=%s", username)
            return None

    # ===== Helper methods (読みやすさ向上用) =====
    def _parse_host_port(self, url, use_ssl):
        parsed = urlparse(url)
        host = parsed.hostname or url
        port = parsed.port or (636 if use_ssl else 389)
        return host, port

    def _build_tls(self, use_ssl, force_starttls, ssl_mod):
        if not (use_ssl or force_starttls):
            return None
        try:
            from ldap3 import Tls  # 局所 import
            validate_mode = ssl_mod.CERT_NONE if getattr(settings, 'LDAP_TLS_INSECURE', False) else ssl_mod.CERT_REQUIRED
            return Tls(validate=validate_mode)
        except Exception:  # noqa: BLE001
            return None

    def _is_ipv4_like(self, host: str) -> bool:
        try:
            if host.count('.') != 3:
                return False
            return all(part.isdigit() and 0 <= int(part) <= 255 for part in host.split('.'))
        except Exception:  # noqa: BLE001
            return False

    def _build_candidate_credentials(self, username: str, domain: str, upn_suffix: Optional[str]):
        original = username
        candidates: List[Tuple[str, str, Optional[str]]] = []
        if '\\' in original:
            candidates.append(("NTLM(as-is)", original, 'NTLM'))
        if '@' in original:
            candidates.append(("UPN(as-is)", original, None))
        if '\\' not in original and '@' not in original and domain:
            candidates.append(("NTLM(domain)", f"{domain}\\{original}", 'NTLM'))
        if '\\' not in original and '@' not in original:
            suffix = upn_suffix or (domain if domain and '.' in domain else None)
            if suffix:
                candidates.append(("UPN(constructed)", f"{original}@{suffix}", None))
        # distinct by bind_user
        seen = set()
        distinct_list = []
        for lbl, usr, auth in candidates:
            if usr in seen:
                continue
            seen.add(usr)
            distinct_list.append((lbl, usr, auth))
        return distinct_list

    def _log_no_candidates(self, username, domain, upn_suffix, use_ssl, force_starttls, allow_plain):
        logger.warning(
            "LDAP no credential candidates | user=%s original=%s domain=%s upn_suffix=%s use_ssl=%s force_starttls=%s allow_plain=%s",
            username, username, domain or '', upn_suffix or '', use_ssl, force_starttls, allow_plain
        )
        logger.warning(
            "LDAP candidate generation hint | conditions: (has \\ => NTLM(as-is)) (has @ => UPN(as-is)) (domain set => NTLM(domain)) (suffix/domain with dot => UPN(constructed))"
        )

    def _start_tls_if_needed(self, conn, host, bind_user, label, last_errors):
        if conn.start_tls():
            return True
        logger.warning(
            "LDAP StartTLS failed | host=%s user=%s label=%s last_error=%s result=%s",
            host, bind_user, label, conn.last_error, conn.result,
            extra={'ldap_params': {'attempt': label, 'user': bind_user, 'stage': 'starttls'}}
        )
        last_errors.append((label, conn.last_error, conn.result))
        conn.unbind()
        return False

    def _bind_connection(self, conn, host, host_is_ip, use_ssl, force_starttls, label, auth_method, last_errors):
        if conn.bind():
            return True
        result_dict = conn.result if isinstance(conn.result, dict) else {}
        result_code = result_dict.get('result')
        result_desc = result_dict.get('description') or getattr(conn.result, 'description', None)
        result_msg = result_dict.get('message')
        logger.debug(
            "LDAP bind failed | host=%s ip=%s secure_ssl=%s starttls=%s label=%s auth=%s code=%s desc=%s message=%s last_error=%s",
            host, host_is_ip, use_ssl, force_starttls, label, auth_method, result_code, result_desc, result_msg, conn.last_error,
        )
        last_errors.append((label, conn.last_error, conn.result))
        conn.unbind()
        return False

    def _search_user_entry(self, conn, username, host, label, search_base, last_errors):
        from ldap3 import SUBTREE  # 局所 import (既に本体で import されているが保険)
        search_filter = f'(sAMAccountName={username})'
        attributes = ['cn', 'mail', 'distinguishedName', 'department', 'title', 'memberOf', 'givenName', 'sn', 'displayName']
        if not conn.search(search_base=search_base, search_filter=search_filter, search_scope=SUBTREE, attributes=attributes):
            logger.warning(
                "LDAP search returned no entries | host=%s bind_user=%s filter=%s base=%s",
                host, conn.user, search_filter, search_base,
                extra={'ldap_params': {'attempt': label, 'filter': search_filter, 'base': search_base}}
            )
            return None
        if not conn.entries:
            logger.warning("LDAP search empty entries | host=%s bind_user=%s", host, conn.user)
            return None
        return conn.entries[0]

    def _get_or_create_local_user(self, username, entry, upn_suffix, domain):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            display_name = str(getattr(entry, 'displayName', '') or getattr(entry, 'cn', '') or username)
            first_name, last_name = (display_name, '')
            if ' ' in display_name:
                first_name, last_name = display_name.split(' ', 1)
            email_attr = str(getattr(entry, 'mail', '') or f"{username}@{(upn_suffix or domain or 'local')}")
            user = UserModel.objects.create_user(
                username=username,
                email=email_attr,
                first_name=first_name,
                last_name=last_name,
            )
            user.set_unusable_password()
            user.save()
            return user

    def _update_user_profile(self, user, entry):
        try:
            from .models import UserProfile  # 遅延 import
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.ldap_dn = str(getattr(entry, 'distinguishedName', '') or '')
            profile.department_name = str(getattr(entry, 'department', '') or '')
            profile.title = str(getattr(entry, 'title', '') or '')
            profile.save()
        except Exception:  # noqa: BLE001
            logger.debug("UserProfile 更新をスキップ (存在しない/エラー)")

    def _log_all_attempt_fail(self, username, host, host_is_ip, domain, last_errors, use_ssl, force_starttls):
        attempt_count = len(last_errors)
        logger.debug(
            "LDAP all bind attempts failed | user=%s host=%s ip=%s domain=%s attempts=%d secure=(ssl:%s starttls:%s)",
            username, host, host_is_ip, domain or '', attempt_count, use_ssl, force_starttls
        )
        for l, le, r in last_errors:
            if isinstance(r, dict):
                desc = r.get('description')
                code = r.get('result')
                msg = r.get('message')
            else:  # pragma: no cover - 想定外フォーマット
                desc = getattr(r, 'description', None)
                code = getattr(r, 'result', None)
                msg = getattr(r, 'message', None)
            logger.debug(
                "LDAP attempt detail | user=%s label=%s code=%s desc=%s msg=%s last_error=%s", username, l, code, desc, msg, le
            )
    
    def get_approvers_for_user(self, user_dn):
        """
        Active DirectoryからOU階層に基づく承認者を取得
        """
        try:
            from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
            
            # LDAP設定を取得 (統一名を優先)
            ldap_server = getattr(settings, 'LDAP_SERVER_URL', getattr(settings, 'LDAP_AUTH_URL', 'ldap://localhost:389'))
            search_base = getattr(settings, 'LDAP_SEARCH_BASE', getattr(settings, 'LDAP_AUTH_SEARCH_BASE', 'DC=company,DC=com'))
            service_user = getattr(settings, 'LDAP_BIND_DN', getattr(settings, 'LDAP_AUTH_CONNECTION_USERNAME', None))
            service_password = getattr(settings, 'LDAP_BIND_PASSWORD', getattr(settings, 'LDAP_AUTH_CONNECTION_PASSWORD', None))
            
            if not service_user:
                # サービスアカウントが設定されていない場合はエラー
                logger.error(
                    "LDAP service account not configured | server=%s search_base=%s", ldap_server, search_base,
                    extra={
                        'ldap_params': {
                            'server': ldap_server,
                            'search_base': search_base
                        }
                    }
                )
                return []
            
            # サーバー接続
            server = Server(ldap_server, get_info=ALL)
            conn = Connection(server, user=service_user, password=service_password)
            
            if not conn.bind():
                logger.error(
                    "Failed to bind to LDAP server with service account | server=%s service_user=%s search_base=%s", 
                    ldap_server, service_user, search_base,
                    extra={
                        'ldap_params': {
                            'server': ldap_server,
                            'service_user': service_user,
                            'search_base': search_base
                        }
                    }
                )
                return []
            
            # OU階層を抽出
            ou_hierarchy = self._extract_ou_hierarchy(user_dn)
            approvers = []
            
            # 各OU階層のユーザーを検索
            for ou_dn in ou_hierarchy:
                search_filter = '(&(objectClass=user)(!(objectClass=computer)))'
                attributes = ['sAMAccountName', 'cn', 'mail', 'distinguishedName']
                
                success = conn.search(
                    search_base=ou_dn,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=attributes
                )
                
                if success:
                    for entry in conn.entries:
                        username = str(entry.sAMAccountName) if hasattr(entry, 'sAMAccountName') else ''
                        display_name = str(entry.cn) if hasattr(entry, 'cn') else ''
                        email = str(entry.mail) if hasattr(entry, 'mail') else ''
                        entry_dn = str(entry.distinguishedName) if hasattr(entry, 'distinguishedName') else ''
                        
                        if username and display_name:
                            approvers.append({
                                'username': username,
                                'display_name': display_name,
                                'email': email,
                                'dn': entry_dn,
                                'ou': ou_dn
                            })
            
            conn.unbind()
            return approvers
            
        except Exception as e:
            logger.exception(
                "Error getting approvers from LDAP | user_dn=%s server=%s search_base=%s", 
                user_dn, locals().get('ldap_server'), locals().get('search_base'),
                extra={
                    'ldap_params': {
                        'user_dn': user_dn,
                        'server': locals().get('ldap_server'),
                        'search_base': locals().get('search_base')
                    }
                }
            )
            return []
    
    def _extract_ou_hierarchy(self, user_dn):
        """
        ユーザーのDNからOU階層を抽出
        下位から上位への順序で返す
        """
        ou_list = []
        parts = user_dn.split(',')
        
        # OUの部分を抽出
        ou_parts = []
        dc_parts = []
        
        for part in parts:
            part = part.strip()
            if part.startswith('OU='):
                ou_parts.append(part)
            elif part.startswith('DC='):
                dc_parts.append(part)
        
        # DC部分を結合
        base_dn = ','.join(dc_parts)
        
        # OU階層を構築（下位から上位へ）
        for i in range(len(ou_parts)):
            ou_dn = ','.join(ou_parts[i:] + dc_parts)
            ou_list.append(ou_dn)
        
        # ルートドメインも追加
        if base_dn not in ou_list:
            ou_list.append(base_dn)
        
        return ou_list


    # ...existing code...
