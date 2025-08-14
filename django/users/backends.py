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

            # 設定値
            ldap_server_url = getattr(settings, 'LDAP_SERVER_URL', getattr(settings, 'LDAP_AUTH_URL', 'ldap://localhost:389'))
            search_base = getattr(settings, 'LDAP_SEARCH_BASE', getattr(settings, 'LDAP_AUTH_SEARCH_BASE', 'DC=example,DC=com'))
            domain = getattr(settings, 'LDAP_DOMAIN', '')
            upn_suffix = getattr(settings, 'LDAP_UPN_SUFFIX', None)
            use_ssl = bool(getattr(settings, 'LDAP_USE_SSL', False))
            force_starttls = bool(getattr(settings, 'LDAP_FORCE_STARTTLS', False))
            allow_plain = bool(getattr(settings, 'LDAP_ALLOW_PLAIN_FALLBACK', False))  # 平文 fallback 許可

            # URL 解析
            parsed = urlparse(ldap_server_url)
            host = parsed.hostname or ldap_server_url
            port = parsed.port or (636 if use_ssl else 389)

            # TLS オブジェクト
            tls = None
            if use_ssl or force_starttls:
                try:
                    tls = Tls(validate=ssl.CERT_NONE if getattr(settings, 'LDAP_TLS_INSECURE', False) else ssl.CERT_REQUIRED)
                except Exception:  # noqa: BLE001
                    tls = None

            server = Server(host, port=port, use_ssl=use_ssl, get_info=ALL, tls=tls)

            # 接続先ホストの性質 (IPかFQDNか) を簡易判定してログに出すことで、
            # FQDN 未使用による SPN 解決不可 / TLS hostname mismatch 起因のポリシー影響を切り分けやすくする
            try:
                host_is_ip = all(part.isdigit() and 0 <= int(part) <= 255 for part in host.split('.')) if host.count('.') == 3 else False
            except Exception:  # noqa: BLE001
                host_is_ip = False

            # 資格情報候補生成
            def distinct(seq):
                seen = set()
                out = []
                for item in seq:
                    if item[1] in seen:
                        continue
                    seen.add(item[1])
                    out.append(item)
                return out

            candidates: List[Tuple[str, str, Optional[str]]] = []
            original = username
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
            candidates = distinct(candidates)

            if not candidates:
                logger.warning(
                    "LDAP no credential candidates | user=%s original=%s domain=%s upn_suffix=%s use_ssl=%s force_starttls=%s allow_plain=%s",
                    username, original, domain or '', upn_suffix or '', use_ssl, force_starttls, allow_plain
                )
                logger.warning(
                    "LDAP candidate generation hint | conditions: (has \\ => NTLM(as-is)) (has @ => UPN(as-is)) (domain set => NTLM(domain)) (suffix/domain with dot => UPN(constructed))"
                )
                return None

            # 候補一覧を事前表示（ドメイン確認用）
            logger.debug(
                "LDAP bind candidates | user=%s domain=%s candidates=%s",
                username, domain or '', [(lbl, usr, auth) for lbl, usr, auth in candidates]
            )

            # セキュアチャネル必須条件確認
            if not use_ssl and not force_starttls and not allow_plain:
                force_starttls = True

            last_errors = []

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
                    if not use_ssl and force_starttls:
                        if not conn.start_tls():
                            logger.warning(
                                "LDAP StartTLS failed | host=%s user=%s label=%s last_error=%s result=%s",
                                host, bind_user, label, conn.last_error, conn.result,
                                extra={'ldap_params': {'attempt': label, 'user': bind_user, 'stage': 'starttls'}}
                            )
                            last_errors.append((label, conn.last_error, conn.result))
                            conn.unbind()
                            continue
                    if not conn.bind():
                        # 追加詳細: result code (数値), description, message を取得
                        result_dict = conn.result if isinstance(conn.result, dict) else {}
                        result_code = result_dict.get('result')
                        result_desc = result_dict.get('description') or getattr(conn.result, 'description', None)
                        result_msg = result_dict.get('message')
                        logger.debug(
                            "LDAP bind failed | host=%s ip=%s secure_ssl=%s starttls=%s label=%s auth=%s code=%s desc=%s message=%s last_error=%s",  # noqa: E501
                            host, host_is_ip, use_ssl, force_starttls, label, auth_method, result_code, result_desc, result_msg, conn.last_error,
                        )
                        last_errors.append((label, conn.last_error, conn.result))
                        conn.unbind()
                        continue

                    search_filter = f'(sAMAccountName={username})'
                    attributes = ['cn', 'mail', 'distinguishedName', 'department', 'title', 'memberOf', 'givenName', 'sn', 'displayName']
                    if not conn.search(search_base=search_base, search_filter=search_filter, search_scope=SUBTREE, attributes=attributes):
                        logger.warning(
                            "LDAP search returned no entries | host=%s bind_user=%s filter=%s base=%s",
                            host, bind_user, search_filter, search_base,
                            extra={'ldap_params': {'attempt': label, 'filter': search_filter, 'base': search_base}}
                        )
                        conn.unbind()
                        return None
                    if not conn.entries:
                        logger.warning("LDAP search empty entries | host=%s bind_user=%s", host, bind_user)
                        conn.unbind()
                        return None
                    entry = conn.entries[0]

                    UserModel = get_user_model()
                    try:
                        user = UserModel.objects.get(username=username)
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

                    try:
                        from .models import UserProfile
                        profile, _ = UserProfile.objects.get_or_create(user=user)
                        profile.ldap_dn = str(getattr(entry, 'distinguishedName', '') or '')
                        profile.department_name = str(getattr(entry, 'department', '') or '')
                        profile.title = str(getattr(entry, 'title', '') or '')
                        profile.save()
                    except Exception:  # noqa: BLE001
                        logger.debug("UserProfile 更新をスキップ (存在しない/エラー)")

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

            # 短いメッセージ (詳細は DEBUG で)
            attempt_count = len(last_errors)
            logger.debug(
                "LDAP all bind attempts failed | user=%s host=%s ip=%s domain=%s attempts=%d secure=(ssl:%s starttls:%s)", 
                username, host, host_is_ip, domain or '', attempt_count, use_ssl, force_starttls
            )
            if last_errors:
                # 各試行を DEBUG で簡潔表示
                for l, le, r in last_errors:
                    desc = None
                    if isinstance(r, dict):
                        desc = r.get('description')
                    else:
                        desc = getattr(r, 'description', None)
                    code = None
                    msg = None
                    if isinstance(r, dict):
                        code = r.get('result')
                        msg = r.get('message')
                    logger.debug(
                        "LDAP attempt detail | user=%s label=%s code=%s desc=%s msg=%s last_error=%s", username, l, code, desc, msg, le
                    )
            return None
        except ImportError:
            logger.exception("ldap3 not installed | user=%s", username)
            return None
        except Exception:
            logger.exception("LDAP unexpected error | user=%s", username)
            return None
    
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
