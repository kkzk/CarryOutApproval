from __future__ import annotations

"""Active Directory にテスト用 OU / ユーザを登録する管理コマンド。

元: `register_testuser/register_to_ad.py` の機能を `manage.py` コマンド化。

方針:
 1. 既存 README / LDAP Backend と整合する設定名 (環境変数 or settings) を利用
 2. 旧 `.env` の AD_* 系環境変数 (AD_SERVER など) も後方互換で読み取り
 3. JSON 形式 (ldap_data.json) から OU/ユーザを作成
 4. 既存オブジェクトはスキップ (冪等性)
 5. --dry-run で内容だけ確認可能

使用例:
  uv run python manage.py register_ad_data \
      --file register_testuser/ldap_data.json

  uv run python manage.py register_ad_data --dry-run

  (後方互換) 旧 .env を利用する場合はプロジェクトルートに配置し AD_SERVER などを設定。

注意:
  本コマンドは AD (実 LDAP) への直接変更を行うため、本番実行前に --dry-run で必ず確認。
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, cast

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

try:  # python-dotenv は任意依存
    from dotenv import load_dotenv  # type: ignore
except Exception:  # noqa: BLE001
    def load_dotenv(*_a: Any, **_kw: Any) -> bool:  # type: ignore
        return False


logger = logging.getLogger(__name__)


class ADConfig:
    """AD 接続設定 (settings + 環境変数)。"""

    def __init__(self):  # noqa: D401 - 単純初期化
        load_dotenv()  # .env があれば読む (後方互換)

        # 1) 新方式 (settings.py / README 準拠)
        self.server_url = getattr(settings, 'LDAP_SERVER_URL', None)
        self.domain = getattr(settings, 'LDAP_DOMAIN', None)
        self.search_base = getattr(settings, 'LDAP_SEARCH_BASE', None)
        self.service_user = getattr(settings, 'LDAP_SERVICE_USER', None)  # 任意 (固定サービスアカウント利用時)
        self.service_password = getattr(settings, 'LDAP_SERVICE_PASSWORD', None)
        self.use_ssl = bool(getattr(settings, 'LDAP_USE_SSL', False))
        self.force_starttls = bool(getattr(settings, 'LDAP_FORCE_STARTTLS', False))
        self.tls_insecure = bool(getattr(settings, 'LDAP_TLS_INSECURE', False))

        # 2) 旧方式 (.env の AD_* 系) 後方互換 (未設定のみ上書き)
        self.server_url = self.server_url or os.getenv('AD_SERVER')
        self.search_base = self.search_base or os.getenv('AD_BASE_DN')
        # サービスアカウント DN / UPN
        self.service_user = self.service_user or os.getenv('AD_ADMIN_DN')
        self.service_password = self.service_password or os.getenv('AD_ADMIN_PASSWORD')
        # TLS/SSL 旧キー
        if os.getenv('AD_USE_SSL'):
            self.use_ssl = os.getenv('AD_USE_SSL', 'false').lower() == 'true'
        if os.getenv('AD_STARTTLS'):
            self.force_starttls = os.getenv('AD_STARTTLS', 'false').lower() == 'true'

        # ベース DN から domain 推測 (dc=example,dc=com → example.com)
        if not self.domain and self.search_base and 'DC=' in self.search_base.upper():
            self.domain = self.search_base.replace('DC=', '').replace('dc=', '').replace(',', '.')

    def validate(self) -> None:
        missing = [k for k, v in {
            'LDAP_SERVER_URL/AD_SERVER': self.server_url,
            'LDAP_SEARCH_BASE/AD_BASE_DN': self.search_base,
            'LDAP_SERVICE_USER/AD_ADMIN_DN': self.service_user,
            'LDAP_SERVICE_PASSWORD/AD_ADMIN_PASSWORD': self.service_password,
        }.items() if not v]
        if missing:
            raise CommandError('必須設定が不足: ' + ', '.join(missing))


class ActiveDirectoryManager:
    """簡易 AD 管理 (OU/ユーザ登録) - ldap3 を直接利用。"""

    def __init__(self, cfg: ADConfig, dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.connection = None  # type: ignore[var-annotated]

    # ============ 接続 ============
    def connect(self) -> bool:
        from ldap3 import Server, Connection, ALL, NTLM, Tls  # 局所 import
        import ssl
        import re

        if not (self.cfg.server_url and self.cfg.service_user and self.cfg.service_password):  # 認証情報不足
            logger.error('接続情報不足')
            return False

        uri = self.cfg.server_url.strip()
        m = re.match(r'^(ldap[s]?://)?([^:/]+)(?::(\d+))?$', uri)
        if m:
            _sch, host, p = m.groups()
        else:
            host, p = uri, None
        port = int(p) if p else (636 if self.cfg.use_ssl else 389)

        tls = None
        if self.cfg.use_ssl or self.cfg.force_starttls:
            validate = ssl.CERT_NONE if self.cfg.tls_insecure else ssl.CERT_REQUIRED
            try:
                tls = Tls(validate=validate)
            except Exception:  # noqa: BLE001
                pass

        server = Server(host, port=port, use_ssl=self.cfg.use_ssl, get_info=ALL, tls=tls)

        def auth_kind(user: str):
            if user.upper().startswith('CN='):
                return 'SIMPLE'
            if '\\' in user:
                return NTLM
            if '@' in user:
                return 'SIMPLE'
            return 'SIMPLE'

        authentication = auth_kind(self.cfg.service_user)
        conn = Connection(
            server,
            user=self.cfg.service_user,
            password=self.cfg.service_password,
            authentication=authentication,
            auto_bind=False,
            raise_exceptions=False,
        )

        # StartTLS (LDAPS でない & force) の場合
        if not self.cfg.use_ssl and self.cfg.force_starttls:
            if not conn.start_tls():
                logger.error('StartTLS 失敗: %s %s', conn.last_error, conn.result)
                return False

        if not conn.bind():
            logger.error('Bind 失敗: %s %s', conn.last_error, conn.result)
            return False

        self.connection = conn
        logger.info('AD 接続成功 host=%s port=%s ssl=%s starttls=%s', host, port, self.cfg.use_ssl, self.cfg.force_starttls)
        return True

    def disconnect(self) -> None:  # noqa: D401
        if self.connection:
            try:
                self.connection.unbind()
            except Exception:  # noqa: BLE001
                pass
            logger.info('AD 切断')

    # ============ OU / USER 作成 ============
    def ensure_ou(self, ou_name: str, parent_dn: str, description: str = '') -> bool:
        if not self.connection:
            return False
        ou_dn = f'OU={ou_name},{parent_dn}'
        if self.dry_run:
            logger.info('[DRY-RUN] OU 作成予定: %s', ou_dn)
            return True
        if self.connection.search(ou_dn, '(objectClass=organizationalUnit)'):
            logger.debug('OU 既存: %s', ou_dn)
            return True
        attrs = {'objectClass': ['top', 'organizationalUnit'], 'ou': ou_name}
        if description:
            attrs['description'] = description
        if self.connection.add(ou_dn, attributes=attrs):
            logger.info('OU 作成: %s', ou_dn)
            return True
        logger.error('OU 作成失敗 %s error=%s', ou_dn, self.connection.last_error)
        return False

    def ensure_user(self, username: str, display_name: str, password: str, ou_dn: str) -> bool:
        if not self.connection:
            return False
        user_dn = f'CN={username},{ou_dn}'
        if self.dry_run:
            logger.info('[DRY-RUN] ユーザ作成予定: %s (%s)', username, user_dn)
            return True
        if self.connection.search(user_dn, '(objectClass=user)'):
            logger.debug('ユーザ既存: %s', user_dn)
            return True
        domain = (self.cfg.domain or '').strip()
        upn = f'{username}@{domain}' if domain else username
        attrs = {
            'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
            'cn': username,
            'sAMAccountName': username,
            'userPrincipalName': upn,
            'displayName': display_name,
            'userAccountControl': 512,
            'pwdLastSet': 0,
        }
        if not self.connection.add(user_dn, attributes=attrs):
            logger.error('ユーザ作成失敗 %s error=%s', user_dn, self.connection.last_error)
            return False
        # パスワード設定
        try:
            if not self.connection.extend.microsoft.modify_password(user_dn, password):  # type: ignore[attr-defined]
                logger.warning('modify_password 失敗 fallback userPassword: %s', self.connection.last_error)
                from ldap3 import MODIFY_REPLACE  # 局所 import
                self.connection.modify(user_dn, {'userPassword': [(MODIFY_REPLACE, [password])]})
            logger.info('ユーザ作成: %s (%s)', username, user_dn)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error('パスワード設定失敗 %s error=%s', user_dn, e)
            return False

    # ============ JSON 処理 ============
    def build_ou_dn_map(self, ou_table: List[Dict[str, Any]], base_dn: str) -> Dict[int, str]:
        dn_map: Dict[int, str] = {}
        roots = [o for o in ou_table if o.get('parent_id') is None]

        def rec(ou_item, parent_dn: str):
            ou_dn = f"OU={ou_item['ou']},{parent_dn}"
            dn_map[ou_item['id']] = ou_dn
            for child in [c for c in ou_table if c.get('parent_id') == ou_item['id']]:
                rec(child, ou_dn)

        for r in roots:
            rec(r, base_dn)
        return dn_map

    def register_from_file(self, path: Path, default_password: str) -> None:
        if not path.exists():
            raise CommandError(f'LDAPデータファイルが見つかりません: {path}')
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        ou_table = data.get('ou_table', [])
        user_table = data.get('user_table', [])
        logger.info('JSON 読込: OU=%d, users=%d', len(ou_table), len(user_table))
        if not self.cfg.search_base:
            raise CommandError('search_base 未設定')
        dn_map = self.build_ou_dn_map(ou_table, self.cfg.search_base)
        # OU 作成 (親から順に処理するため ou_table の順序を尊重 / 事前マップ構築で DN 参照)
        ok_ou = 0
        for ou in ou_table:
            parent_dn = self.cfg.search_base
            if ou.get('parent_id'):
                parent_dn = dn_map.get(ou['parent_id'], parent_dn)
            if self.ensure_ou(ou['ou'], parent_dn, ou.get('description', '')):
                ok_ou += 1
        logger.info('OU 処理完了 success=%d total=%d', ok_ou, len(ou_table))

        # ユーザ
        ok_user = 0
        for user in user_table:
            ou_id = user.get('ou_id')
            ou_dn = dn_map.get(ou_id)
            if not ou_dn:
                # fallback: Users コンテナ (存在しない場合あり) / もしくは search_base 直下
                ou_dn = f"CN=Users,{self.cfg.search_base}"  # type: ignore[str-format]
            pwd = user.get('userPassword') or default_password
            if self.ensure_user(user['uid'], user.get('displayName', user['uid']), pwd, ou_dn):
                ok_user += 1
        logger.info('ユーザ処理完了 success=%d total=%d', ok_user, len(user_table))


class Command(BaseCommand):
    help = 'ldap_data.json から AD に OU / ユーザを登録 (冪等)。後方互換で旧 .env (AD_*) も利用可。'

    def add_arguments(self, parser):  # noqa: D401
        parser.add_argument(
            '--file', '-f',
            default='users/management/data/ldap_testdata.json',
            help='LDAP データ JSON パス'
        )
        parser.add_argument(
            '--default-password',
            default='TempPassword123!',
            help='userPassword 未指定時の既定パスワード'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='変更を行わず実行計画のみ表示'
        )
        # Django の標準 -v (verbosity) と衝突するため短縮なし
        parser.add_argument(
            '--debug-log',
            action='store_true',
            help='詳細ログ (DEBUG) 出力'
        )

    def handle(self, *args, **options):  # noqa: D401
        if options['debug_log']:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)
        cfg = ADConfig()
        cfg.validate()
        dry = bool(options['dry_run'])
        manager = ActiveDirectoryManager(cfg, dry_run=dry)
        if not manager.connect():
            raise CommandError('AD への接続に失敗しました。設定を確認してください。')
        try:
            manager.register_from_file(Path(options['file']), options['default_password'])
        finally:
            manager.disconnect()
        if dry:
            self.stdout.write(self.style.WARNING('DRY-RUN: 変更は行っていません。'))
        self.stdout.write(self.style.SUCCESS('AD 登録処理が完了しました。'))
