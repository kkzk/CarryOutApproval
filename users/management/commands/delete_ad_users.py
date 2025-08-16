from __future__ import annotations
"""Active Directory からテスト / 指定ユーザを削除する管理コマンド。

特徴:
  - register_ad_data の ADConfig / ActiveDirectoryManager を再利用
  - ユーザ DN は固定パスを組み立てず LDAP 検索で取得 (より安全)
  - --users で複数指定 (カンマ区切り / 繰り返し指定両対応)
  - 未指定時はデフォルトのテストユーザセット (user001..user005)
  - --dry-run で削除予定のみ表示
  - 既に存在しないユーザはスキップ扱い

使用例:
  uv run python manage.py delete_ad_users --users user001,user002 --dry-run
  uv run python manage.py delete_ad_users --users user001 --users user002
"""

import logging
from typing import List

from django.core.management.base import BaseCommand, CommandError

from .register_ad_data import ADConfig, ActiveDirectoryManager  # type: ignore

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '指定 (または既定) のテストユーザを AD から削除 (冪等)。LDAP 検索で DN を解決。'

    def add_arguments(self, parser):  # noqa: D401
        parser.add_argument('--users', action='append', help='削除対象ユーザ (カンマ区切り可) 複数指定可')
        parser.add_argument('--dry-run', action='store_true', help='実際には削除せず計画を表示')
        parser.add_argument('--debug-log', action='store_true', help='詳細ログ (DEBUG) 出力')

    def handle(self, *args, **options):  # noqa: D401
        if options['debug_log']:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)
        cfg = ADConfig()
        cfg.validate()
        # 型明示 (validate 済みなので None ではない想定)
        from typing import cast as _cast
        search_base: str = _cast(str, cfg.search_base)

        raw_users: List[str] = []
        if options.get('users'):
            for item in options['users']:
                if item:
                    raw_users.extend([u.strip() for u in item.split(',') if u.strip()])
        if not raw_users:
            raw_users = [f'user{n:03d}' for n in range(1, 6)]

        dry = bool(options['dry_run'])
        manager = ActiveDirectoryManager(cfg, dry_run=dry)
        if not manager.connect():
            raise CommandError('AD 接続に失敗しました。設定を確認してください。')

        try:
            conn = manager.connection
            if conn is None:
                raise CommandError('内部エラー: 接続オブジェクトがありません。')
            from ldap3 import SUBTREE  # type: ignore

            deleted = 0
            missing = 0
            for username in raw_users:
                search_filter = f'(sAMAccountName={username})'
                logger.debug('検索 user=%s filter=%s base=%s', username, search_filter, cfg.search_base)
                if not conn.search(search_base=search_base, search_filter=search_filter, search_scope=SUBTREE, attributes=['distinguishedName']):
                    logger.info('未存在: %s', username)
                    missing += 1
                    continue
                if not conn.entries:
                    logger.info('未存在(エントリ空): %s', username)
                    missing += 1
                    continue
                dn = conn.entries[0].entry_dn  # type: ignore[attr-defined]
                if dry:
                    logger.info('[DRY-RUN] 削除予定: %s (%s)', username, dn)
                    deleted += 1
                    continue
                if conn.delete(dn):
                    logger.info('削除成功: %s (%s)', username, dn)
                    deleted += 1
                else:
                    logger.warning('削除失敗: %s (%s) error=%s result=%s', username, dn, conn.last_error, conn.result)
            self.stdout.write(self.style.SUCCESS(f'対象 {len(raw_users)} / 削除(予定含) {deleted} / 未存在 {missing}'))
            if dry:
                self.stdout.write(self.style.WARNING('DRY-RUN: 実際の削除は行っていません。'))
        finally:
            manager.disconnect()
