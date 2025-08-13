# Windows compatible LDAP backend using ldap3
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.conf import settings
import json
import os


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
        """ldap3ライブラリを使用したActive Directory認証"""
        try:
            from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
            
            # LDAP設定を取得
            ldap_server = getattr(settings, 'LDAP_AUTH_URL', 'ldap://localhost:389')
            search_base = getattr(settings, 'LDAP_AUTH_SEARCH_BASE', 'DC=company,DC=com')
            domain = getattr(settings, 'LDAP_DOMAIN', 'company.com')
            
            # サーバー接続
            server = Server(ldap_server, get_info=ALL)
            
            # NTLM認証を試行（WindowsのActive Directory向け）
            user_dn = f'{domain}\\{username}'
            conn = Connection(server, user=user_dn, password=password, authentication=NTLM)
            
            if not conn.bind():
                # NTLM認証に失敗した場合、Simple認証を試行
                user_dn = f'{username}@{domain}'
                conn = Connection(server, user=user_dn, password=password)
                if not conn.bind():
                    return None
            
            # ユーザー情報を検索
            search_filter = f'(sAMAccountName={username})'
            attributes = ['cn', 'mail', 'distinguishedName', 'department', 'title', 'memberOf']
            
            success = conn.search(
                search_base=search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes
            )
            
            if not success or not conn.entries:
                conn.unbind()
                return None
                
            entry = conn.entries[0]
            
            # ユーザー情報の抽出
            display_name = str(entry.cn) if hasattr(entry, 'cn') else username
            email = str(entry.mail) if hasattr(entry, 'mail') else f'{username}@{domain}'
            distinguished_name = str(entry.distinguishedName) if hasattr(entry, 'distinguishedName') else ''
            department = str(entry.department) if hasattr(entry, 'department') else ''
            title = str(entry.title) if hasattr(entry, 'title') else ''
            
            # Djangoユーザーを作成または更新
            UserModel = get_user_model()
            try:
                user = UserModel.objects.get(username=username)
            except UserModel.DoesNotExist:
                # 新規ユーザー作成
                user = UserModel.objects.create_user(
                    username=username,
                    email=email,
                    first_name=display_name.split(' ')[0] if ' ' in display_name else display_name,
                    last_name=display_name.split(' ', 1)[1] if ' ' in display_name else ''
                )
                user.set_unusable_password()
                user.save()
            
            # ユーザープロファイルにLDAP情報を保存
            from .models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.ldap_dn = distinguished_name
            profile.department_name = department
            profile.title = title
            profile.save()
            
            conn.unbind()
            return user
            
        except ImportError:
            print("ldap3 package is not installed.")
            return None
        except Exception as e:
            print(f"LDAP3 authentication error: {e}")
            return None
    
    def get_approvers_for_user(self, user_dn):
        """
        Active DirectoryからOU階層に基づく承認者を取得
        """
        try:
            from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
            
            # LDAP設定を取得
            ldap_server = getattr(settings, 'LDAP_AUTH_URL', 'ldap://localhost:389')
            search_base = getattr(settings, 'LDAP_AUTH_SEARCH_BASE', 'DC=company,DC=com')
            service_user = getattr(settings, 'LDAP_AUTH_CONNECTION_USERNAME', None)
            service_password = getattr(settings, 'LDAP_AUTH_CONNECTION_PASSWORD', None)
            
            if not service_user:
                # サービスアカウントが設定されていない場合はエラー
                print("LDAP service account not configured")
                return []
            
            # サーバー接続
            server = Server(ldap_server, get_info=ALL)
            conn = Connection(server, user=service_user, password=service_password)
            
            if not conn.bind():
                print("Failed to bind to LDAP server with service account")
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
            print(f"Error getting approvers from LDAP: {e}")
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
