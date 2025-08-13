#!/usr/bin/env python3
"""
ActiveDirectory からテストユーザを削除するスクリプト
"""

import json
import os
import logging
from typing import Dict, List, Optional
try:
    from dotenv import load_dotenv
except ImportError:
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
    ]
)
logger = logging.getLogger(__name__)


def delete_test_users():
    """テストユーザを削除"""
    # 環境変数を読み込み
    load_dotenv()
    
    server_uri = os.getenv('AD_SERVER')
    admin_dn = os.getenv('AD_ADMIN_DN')
    admin_password = os.getenv('AD_ADMIN_PASSWORD')
    base_dn = os.getenv('AD_BASE_DN')
    use_ssl = os.getenv('AD_USE_SSL', 'false').lower() == 'true'
    
    if not all([server_uri, admin_dn, admin_password, base_dn]):
        logger.error("必須の環境変数が設定されていません")
        return False
    
    try:
        # サーバー設定
        if use_ssl:
            import ssl
            tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
            server = Server(server_uri, get_info=ALL, use_ssl=use_ssl, tls=tls)
        else:
            server = Server(server_uri, get_info=ALL, use_ssl=use_ssl)
        
        # 接続
        if 'CN=' in admin_dn.upper():
            connection = Connection(server, user=admin_dn, password=admin_password, auto_bind=True)
        else:
            connection = Connection(server, user=admin_dn, password=admin_password, authentication=NTLM, auto_bind=True)
        
        logger.info(f"ActiveDirectoryに接続しました: {server_uri}")
        
        # テストユーザのリスト
        test_users = ['user001', 'user002', 'user003', 'user004', 'user005']
        
        # 削除実行
        deleted_count = 0
        for username in test_users:
            # ユーザの完全DN構築
            ou_dn = "OU=backend,OU=development,OU=engineering,OU=departments,OU=company," + base_dn
            user_dn = f"CN={username},{ou_dn}"
            
            try:
                # ユーザ存在確認
                if connection.search(user_dn, '(objectClass=user)'):
                    # ユーザ削除
                    result = connection.delete(user_dn)
                    if result:
                        logger.info(f"ユーザ '{username}' を削除しました: {user_dn}")
                        deleted_count += 1
                    else:
                        logger.warning(f"ユーザ '{username}' の削除に失敗しました: {connection.last_error}")
                else:
                    logger.info(f"ユーザ '{username}' は存在しません: {user_dn}")
                    
            except LDAPException as e:
                logger.error(f"ユーザ '{username}' の削除でLDAPエラー: {e}")
        
        logger.info(f"削除完了: {deleted_count}件のユーザを削除しました")
        
        # 接続を閉じる
        connection.unbind()
        return True
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        return False


if __name__ == "__main__":
    delete_test_users()
