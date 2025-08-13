#!/usr/bin/env python3
"""
ActiveDirectory にOUとユーザを登録するスクリプト
ldap3ライブラリを使用してLDAP接続を行います。
"""

import json
import os
import logging
from typing import Dict, List, Optional
try:
    from dotenv import load_dotenv
except ImportError:
    # dotenvがインストールされていない場合は無視
    def load_dotenv():
        pass

from ldap3 import Server, Connection, ALL, NTLM, SUBTREE, MODIFY_REPLACE, Tls
from ldap3.core.exceptions import LDAPException, LDAPBindError, LDAPEntryAlreadyExistsResult

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ad_registration.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class ActiveDirectoryManager:
    """ActiveDirectory管理クラス"""
    
    def __init__(self):
        """初期化"""
        # 環境変数を読み込み
        load_dotenv()
        
        self.server_uri = os.getenv('AD_SERVER')
        self.admin_dn = os.getenv('AD_ADMIN_DN')
        self.admin_password = os.getenv('AD_ADMIN_PASSWORD')
        self.base_dn = os.getenv('AD_BASE_DN')
        self.users_ou = os.getenv('AD_USERS_OU', f'CN=Users,{self.base_dn or ""}')
        self.default_password = os.getenv('AD_DEFAULT_PASSWORD', 'TempPassword123!')
        self.use_ssl = os.getenv('AD_USE_SSL', 'false').lower() == 'true'
        
        # ログレベル設定
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, log_level))
        
        # 必須パラメータのチェック
        if not all([self.server_uri, self.admin_dn, self.admin_password, self.base_dn]):
            raise ValueError("必須の環境変数が設定されていません。.envファイルを確認してください。")
        
        self.connection: Optional[Connection] = None
        
    def connect(self) -> bool:
        """ActiveDirectoryに接続"""
        if not self.server_uri or not self.admin_dn or not self.admin_password:
            logger.error("接続に必要な情報が不足しています")
            return False
            
        try:
            # サーバー設定（SSL使用時は証明書検証を調整）
            if self.use_ssl:
                import ssl
                tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
                server = Server(self.server_uri, get_info=ALL, use_ssl=self.use_ssl, tls=tls)
            else:
                server = Server(self.server_uri, get_info=ALL, use_ssl=self.use_ssl)
            
            # 接続設定（NTLM認証またはSimple認証）
            if 'CN=' in self.admin_dn.upper():
                # Simple認証
                self.connection = Connection(
                    server, 
                    user=self.admin_dn, 
                    password=self.admin_password,
                    auto_bind=True
                )
            else:
                # NTLM認証
                self.connection = Connection(
                    server, 
                    user=self.admin_dn, 
                    password=self.admin_password,
                    authentication=NTLM,
                    auto_bind=True
                )
            
            logger.info(f"ActiveDirectoryに接続しました: {self.server_uri}")
            return True
            
        except LDAPBindError as e:
            logger.error(f"認証に失敗しました: {e}")
            return False
        except LDAPException as e:
            logger.error(f"LDAP接続エラー: {e}")
            return False
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            return False
    
    def disconnect(self):
        """接続を閉じる"""
        if self.connection:
            self.connection.unbind()
            logger.info("ActiveDirectoryから切断しました")
    
    def create_organizational_unit(self, ou_name: str, parent_dn: str, description: str = "") -> bool:
        """組織単位(OU)を作成"""
        if not self.connection:
            logger.error("ActiveDirectoryに接続されていません")
            return False
            
        ou_dn = f"OU={ou_name},{parent_dn}"
        
        # 既存チェック
        if self.connection.search(ou_dn, '(objectClass=organizationalUnit)'):
            logger.info(f"OU '{ou_name}' は既に存在します: {ou_dn}")
            return True
        
        # OU作成
        attributes = {
            'objectClass': ['top', 'organizationalUnit'],
            'ou': ou_name
        }
        
        if description:
            attributes['description'] = description
        
        try:
            result = self.connection.add(ou_dn, attributes=attributes)
            if result:
                logger.info(f"OU '{ou_name}' を作成しました: {ou_dn}")
                return True
            else:
                logger.error(f"OU '{ou_name}' の作成に失敗しました: {self.connection.last_error}")
                return False
                
        except LDAPEntryAlreadyExistsResult:
            logger.info(f"OU '{ou_name}' は既に存在します: {ou_dn}")
            return True
        except LDAPException as e:
            logger.error(f"OU '{ou_name}' の作成でLDAPエラー: {e}")
            return False
    
    def create_user(self, username: str, display_name: str, password: str, ou_dn: str) -> bool:
        """ユーザを作成"""
        if not self.connection:
            logger.error("ActiveDirectoryに接続されていません")
            return False
            
        if not self.base_dn:
            logger.error("ベースDNが設定されていません")
            return False
            
        user_dn = f"CN={username},{ou_dn}"
        
        # 既存チェック
        if self.connection.search(user_dn, '(objectClass=user)'):
            logger.info(f"ユーザ '{username}' は既に存在します: {user_dn}")
            return True
        
        # ドメイン名を作成（DC=example,DC=com -> example.com）
        domain_name = self.base_dn.replace('DC=', '').replace(',', '.')
        
        # ユーザ作成
        attributes = {
            'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
            'cn': username,
            'sAMAccountName': username,
            'userPrincipalName': f"{username}@{domain_name}",
            'displayName': display_name,
            'userAccountControl': 512,  # 通常のアカウント
            'pwdLastSet': 0  # 次回ログイン時にパスワード変更を強制
        }
        
        try:
            result = self.connection.add(user_dn, attributes=attributes)
            if result:
                logger.info(f"ユーザ '{username}' を作成しました: {user_dn}")
                
                # パスワード設定
                if self.set_user_password(user_dn, password):
                    logger.info(f"ユーザ '{username}' のパスワードを設定しました")
                    return True
                else:
                    logger.warning(f"ユーザ '{username}' は作成されましたが、パスワード設定に失敗しました")
                    return False
            else:
                logger.error(f"ユーザ '{username}' の作成に失敗しました: {self.connection.last_error}")
                return False
                
        except LDAPEntryAlreadyExistsResult:
            logger.info(f"ユーザ '{username}' は既に存在します: {user_dn}")
            return True
        except LDAPException as e:
            logger.error(f"ユーザ '{username}' の作成でLDAPエラー: {e}")
            return False
    
    def set_user_password(self, user_dn: str, password: str) -> bool:
        """ユーザのパスワードを設定"""
        if not self.connection:
            logger.error("ActiveDirectoryに接続されていません")
            return False
            
        try:
            # 方法1: modify_passwordメソッドを使用（推奨方法）
            logger.debug(f"modify_passwordでパスワード設定を試行: {user_dn}")
            result = self.connection.extend.microsoft.modify_password(user_dn, password)
            
            if result:
                logger.debug(f"modify_passwordでパスワード設定成功: {user_dn}")
                return True
            else:
                logger.warning(f"modify_password失敗 - エラー: {self.connection.last_error}")
            
            # 方法2: userPasswordア属性を直接設定（標準LDAP）
            logger.debug(f"userPassword属性で再試行: {user_dn}")
            modify_result = self.connection.modify(
                user_dn, 
                {'userPassword': [(MODIFY_REPLACE, [password])]}
            )
            
            if modify_result:
                logger.debug(f"userPassword属性でパスワード設定成功: {user_dn}")
                return True
            else:
                logger.warning(f"userPassword属性でのパスワード設定失敗 - エラー: {self.connection.last_error}")
            
            # 方法3: アカウントを有効化してからパスワード設定を試行
            logger.debug(f"アカウント有効化後のパスワード設定を試行: {user_dn}")
            
            # アカウントを有効化（userAccountControl = 512）
            enable_result = self.connection.modify(
                user_dn,
                {'userAccountControl': [(MODIFY_REPLACE, [512])]}
            )
            
            if enable_result:
                logger.debug(f"アカウント有効化成功: {user_dn}")
                # 再度パスワード設定を試行
                final_result = self.connection.extend.microsoft.modify_password(user_dn, password)
                if final_result:
                    logger.debug(f"アカウント有効化後のパスワード設定成功: {user_dn}")
                    return True
                else:
                    logger.warning(f"アカウント有効化後もパスワード設定失敗: {self.connection.last_error}")
            
            return False
                
        except LDAPException as e:
            logger.error(f"パスワード設定エラー (LDAP例外): {e}")
            return False
        except Exception as e:
            logger.error(f"パスワード設定で予期しないエラー: {e}")
            return False
    
    def build_ou_hierarchy(self, ou_data: List[Dict]) -> Dict[str, str]:
        """OUの階層構造を構築してDNマッピングを作成"""
        ou_dn_map = {}
        
        # 親がnullのものから開始（ルートOU）
        root_ous = [ou for ou in ou_data if ou['parent_id'] is None]
        processed = set()
        
        def process_ou(ou_item, parent_dn=None):
            if ou_item['id'] in processed:
                return
                
            if parent_dn is None:
                parent_dn = self.base_dn
            
            ou_dn = f"OU={ou_item['ou']},{parent_dn}"
            ou_dn_map[ou_item['id']] = ou_dn
            processed.add(ou_item['id'])
            
            # 子OUを処理
            children = [ou for ou in ou_data if ou['parent_id'] == ou_item['id']]
            for child in children:
                process_ou(child, ou_dn)
        
        # ルートOUから再帰的に処理
        for root_ou in root_ous:
            process_ou(root_ou)
        
        return ou_dn_map
    
    def register_ldap_data(self, ldap_data_file: str) -> bool:
        """LDAPデータファイルからOUとユーザを登録"""
        try:
            # JSONファイル読み込み
            with open(ldap_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            ou_data = data.get('ou_table', [])
            user_data = data.get('user_table', [])
            
            logger.info(f"読み込み完了: OU={len(ou_data)}件, ユーザ={len(user_data)}件")
            
            # OU階層のDNマッピングを構築
            ou_dn_map = self.build_ou_hierarchy(ou_data)
            
            # OU作成
            success_count = 0
            for ou_item in ou_data:
                if not self.base_dn:
                    logger.error("ベースDNが設定されていません")
                    continue
                    
                parent_dn = self.base_dn
                if ou_item['parent_id']:
                    parent_dn_from_map = ou_dn_map.get(ou_item['parent_id'])
                    if parent_dn_from_map:
                        parent_dn = parent_dn_from_map
                
                if self.create_organizational_unit(
                    ou_item['ou'], 
                    parent_dn, 
                    ou_item.get('description', '')
                ):
                    success_count += 1
            
            logger.info(f"OU作成完了: {success_count}/{len(ou_data)}件成功")
            
            # ユーザ作成
            success_count = 0
            for user_item in user_data:
                ou_id = user_item.get('ou_id')
                target_ou_dn = ou_dn_map.get(ou_id, self.users_ou)
                
                if self.create_user(
                    user_item['uid'],
                    user_item.get('displayName', user_item['uid']),
                    user_item.get('userPassword', self.default_password),
                    target_ou_dn
                ):
                    success_count += 1
            
            logger.info(f"ユーザ作成完了: {success_count}/{len(user_data)}件成功")
            
            return True
            
        except FileNotFoundError:
            logger.error(f"ファイルが見つかりません: {ldap_data_file}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"JSONファイルの解析に失敗しました: {e}")
            return False
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            return False


def main():
    """メイン処理"""
    ldap_data_file = "ldap_data.json"
    
    # .envファイルの存在チェック
    if not os.path.exists('.env'):
        logger.error(".envファイルが見つかりません。.env.templateを参考に作成してください。")
        return False
    
    try:
        # ActiveDirectoryマネージャーを初期化
        ad_manager = ActiveDirectoryManager()
        
        # ActiveDirectoryに接続
        if not ad_manager.connect():
            logger.error("ActiveDirectoryへの接続に失敗しました")
            return False
        
        # LDAPデータを登録
        success = ad_manager.register_ldap_data(ldap_data_file)
        
        # 接続を閉じる
        ad_manager.disconnect()
        
        if success:
            logger.info("ActiveDirectoryへのデータ登録が完了しました")
        else:
            logger.error("ActiveDirectoryへのデータ登録に失敗しました")
        
        return success
        
    except Exception as e:
        logger.error(f"スクリプト実行中にエラーが発生しました: {e}")
        return False


if __name__ == "__main__":
    main()
