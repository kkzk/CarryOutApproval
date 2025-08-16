# Windows compatible LDAP backend using ldap3
#
# 主な接続失敗・認証失敗の原因と、それに対応するログメッセージの例です。
#
# 1. サーバーのアドレスやポートが間違っている
#   - ログ例: `desc=Can't contact LDAP server`
#   - 発生箇所: Bind (接続試行) 時
#
# 2. 認証情報 (ユーザー名/パスワード) が無効
#   - ログ例: `desc=invalidCredentials`
#   - 発生箇所: Bind (認証) 時
#   - 補足: Active Directory から返されるエラーコード (例: 52e) があります。
#
# 3. ネットワーク接続の問題 (ファイアウォール、VPN など)
#   - ログ例: `desc=Connect error` または `desc=Can't contact LDAP server`
#   - 発生箇所: StartTLS や Bind (接続試行) 時
#   - 補足: タイムアウトや接続拒否が発生します。
#
# 4. STARTTLS の失敗 (証明書の問題など)
#   - ログ例: `LDAP StartTLS failed ... desc=Connect error`
#   - 発生箇所: StartTLS 実行時
#   - 補足: サーバーがSTARTTLSをサポートしていない、またはクライアントがサーバー証明書を検証できない場合に発生します。
#

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.conf import settings
import logging
import re
from urllib.parse import urlparse
from typing import List, Tuple, Optional, Iterable, Any, cast
from dataclasses import dataclass

# ================== LDAP 定数/Dataclass ==================
LDAP_ATTRS_USER = [
    'cn', 'mail', 'distinguishedName', 'department', 'title',
    'memberOf', 'givenName', 'sn', 'displayName'
]
LDAP_SEARCH_FILTER_USER = '(sAMAccountName={username})'


@dataclass(frozen=True)
class LDAPRuntimeConfig:
    """LDAP 実行時設定 (ユーザ資格情報認証で使用)。"""
    server_url: str
    search_base: str
    domain: str
    upn_suffix: Optional[str]
    use_ssl: bool
    force_starttls: bool
    allow_plain: bool

    @staticmethod
    def load() -> 'LDAPRuntimeConfig':
        return LDAPRuntimeConfig(
            server_url=getattr(settings, 'LDAP_SERVER_URL', getattr(settings, 'LDAP_AUTH_URL', 'ldap://localhost:389')),
            search_base=getattr(settings, 'LDAP_SEARCH_BASE', getattr(settings, 'LDAP_AUTH_SEARCH_BASE', 'DC=example,DC=com')),
            domain=getattr(settings, 'LDAP_DOMAIN', ''),
            upn_suffix=getattr(settings, 'LDAP_UPN_SUFFIX', None),
            use_ssl=bool(getattr(settings, 'LDAP_USE_SSL', False)),
            force_starttls=bool(getattr(settings, 'LDAP_FORCE_STARTTLS', False)),
            allow_plain=bool(getattr(settings, 'LDAP_ALLOW_PLAIN_FALLBACK', False)),
        )


# ロガー
logger = logging.getLogger('django.security.authentication')  # 既存 WARNING/INFO 用
dbg_logger = logging.getLogger('users.backends')  # 詳細デバッグ用 (LOGGING で DEBUG レベル指定済)


class WindowsLDAPBackend(ModelBackend):
    """Windows対応 LDAP 認証バックエンド (ldap3)。

    ポリシー:
        - 管理用固定サービスアカウントを持たず、利用者資格情報で直接バインド
        - LDAPS / StartTLS を優先 (設定で明示無い場合は StartTLS を強制)
        - バインド候補生成順: as-is(入力形式) > NTLM(domain\\user) > UPN(constructed)
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """認証フロー (現行ポリシー要約 / 仕様 v2)

        ゴール:
            - 非 LDAP ユーザ (source!=LDAP) はプレフィックス許可 & PW 一致時のみ成功し、失敗時は LDAP 試行なしで終了。
            - LDAP ユーザ (source==LDAP) または未登録ユーザのみ LDAP に問い合わせ。

        手順:
            A. username/password 無し → None
            B. ローカルユーザ取得
            C. ローカルユーザ & source!=LDAP:
                 C1. プレフィックス一致 & パスワード一致 → 成功
                 C2. 上記以外 → 失敗 (LDAP へは行かない)
            D. (未登録 or source==LDAP) → LDAP 認証
            E. 失敗時: メッセージ付与し None

        影響 (仕様v1との差分):
            - v1 では非LDAPユーザのパスワード不一致時に LDAP へフォールバックする余地があったが排除。
            - ローカル先取り後に LDAP アカウントが後から作成されても自動昇格しない (運用で変換が必要)。
        """
        # (A) username/password 無し → None
        if not username or not password:
            return None

        # (B) ローカルユーザ取得
        UserModel = get_user_model()
        try:
            local_user = UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            local_user = None

        # (C) local-first: パターン & 非LDAPユーザ
        prefixes = getattr(settings, 'AUTH_LOCAL_FIRST_PREFIXES', []) or []  # list[str]
        dbg_logger.debug(
            "Local-first precheck | user=%s exists=%s prefixes=%s", username, local_user is not None, prefixes
        )
        if local_user is not None:
            from .models import UserSource
            try:
                user_source = local_user.source  # type: ignore[attr-defined]
            except AttributeError:
                dbg_logger.warning("User has no 'source' attribute (treat as LDAP) | user=%s", username)
                user_source = 'UNKNOWN'
                is_ldap_user = True
            else:
                is_ldap_user = (user_source == UserSource.LDAP)
            dbg_logger.debug(
                "Local-first user info | user=%s source=%s is_ldap_user=%s usable=%s",
                username, user_source, is_ldap_user, local_user.has_usable_password()
            )
            if not is_ldap_user:
                # 仕様変更: 非LDAPユーザは LDAP に問い合わせない。
                if not (prefixes and any(username.startswith(p) for p in prefixes)):
                    dbg_logger.debug("Non-LDAP user without allowed prefix -> auth fail (no LDAP query) | user=%s", username)
                    return None
                dbg_logger.debug("Local-first prefix matched | user=%s prefixes=%s", username, prefixes)
                if local_user.check_password(password):
                    logger.info("Local-first auth success | user=%s", username)
                    return local_user
                dbg_logger.debug("Local-first password mismatch (non-LDAP user, no LDAP fallback) | user=%s", username)
                return None
            else:
                dbg_logger.debug("Local-first skipped (LDAP sourced user) | user=%s", username)

        # (D) LDAP 認証
        user, auth_result = self._authenticate_ldap3(username, password)
        if user is not None:
            return user

        # (E) 失敗時メッセージ
        if request and auth_result:
            try:
                messages.error(request, auth_result)
            except Exception:  # 非標準環境フォールバック
                existing = getattr(request, '_auth_error_messages', [])
                existing.append(auth_result)
                setattr(request, '_auth_error_messages', existing)
        return None

    def _authenticate_ldap3(self, username, password):
        """利用者資格情報で AD (LDAP) に直接バインドして認証するメインフロー。

        流れ (成功した時点で即 return):
          1. 設定ロード & Server/TLS 初期化
          2. ユーザ名表記の揺れを吸収する複数のバインド候補生成
          3. 各候補で順次: Connection 準備 → (必要なら StartTLS) → bind → ユーザ検索
          4. 最初に成功したエントリでローカルユーザ作成/取得 & プロファイル同期し返却
          5. 全候補失敗時は詳細ログを残して None

        戻り値:
          - (ユーザーオブジェクト, None): 認証成功時
          - (None, エラーメッセージ): 認証失敗時
        """
        try:
            # 1) 設定ロード (毎回: 動的に設定変更される可能性を考慮 / キャッシュは不要な軽コスト)
            cfg = LDAPRuntimeConfig.load()
            # 2) ldap3 のインポートを遅延させることで: (a) 起動時コスト削減 (b) モジュール未導入時に他機能を壊さない
            from ldap3 import Server, ALL  # 遅延 import
            import ssl  # TLS 設定用 (証明書検証モード選択に利用)
            # --- 接続パラメータ準備 ---
            # URL から (host, port) を抽出
            host, port = self._parse_host_port(cfg.server_url, cfg.use_ssl)
            # LDAPS or StartTLS を使う場合のみ TLS オブジェクト生成
            tls = self._build_tls(cfg.use_ssl, cfg.force_starttls, ssl)
            # get_info=ALL: スキーマ等のメタ情報取得 (軽量)
            server = Server(host, port=port, use_ssl=cfg.use_ssl, get_info=ALL, tls=tls)
            # IP 指定かどうか (証明書 CN 不一致ログ判断用)
            host_is_ip = self._is_ipv4_like(host)
            # StartTLS 強制条件: 明示 force_starttls OR (暗号化手段が無 & allow_plain=False)
            force_starttls = cfg.force_starttls or (not cfg.use_ssl and not cfg.allow_plain)
            # 失敗試行の (label, last_error, result) 蓄積
            last_errors: List[Tuple[str, str, object]] = []
            # 認証候補 credential 群 (順序維持: 最初に成功したものを採用)
            candidates = list(self._generate_bind_candidates(username, cfg))
            if not candidates:
                # 早期終了: 生成条件に合致する資格文字列が一つも無い (入力形式 + 設定不足)
                self._log_no_candidates(username, cfg.domain, cfg.upn_suffix, cfg.use_ssl, force_starttls, cfg.allow_plain)
                return None, "認証に必要なドメイン情報が不足しています。システム管理者に連絡してください。"
            
            logger.debug("LDAP bind candidates | user=%s candidates=%s", username, [(c[0], c[1]) for c in candidates])
            for label, bind_user, auth_kind in candidates:
                user, error_msg = self._attempt_single_candidate(
                    username=username,
                    password=password,
                    server=server,
                    host=host,
                    host_is_ip=host_is_ip,
                    cfg=cfg,
                    force_starttls=force_starttls,
                    label=label,
                    bind_user=bind_user,
                    auth_kind=auth_kind,
                    last_errors=last_errors,
                )
                # 特殊ケース: エントリ無し (bind 成功だが検索 0 件) → 全体として None を確定
                if user is False:  # sentinel (検索なし早期終了)
                    return None, (
                        "【LDAPユーザー未登録】LDAPには接続できましたが該当ユーザー情報が見つかりません。"  # 事象概要
                        "運用窓口へ『LDAPにユーザー未登録（追加/同期要確認）』と連絡してください。"
                    )
                # User インスタンスが返れば成功
                if user is not None:
                    return user, None
            
            # 全候補失敗: 蓄積した失敗情報を DEBUG 出力し None
            self._log_all_attempt_fail(username, host, host_is_ip, cfg.domain, last_errors, cfg.use_ssl, force_starttls)
            
            # エラー詳細から適切なユーザー向けメッセージを生成
            error_msg = self._generate_user_friendly_error(last_errors)
            return None, error_msg
            
        except ImportError:  # noqa: BLE001
            logger.exception("ldap3 not installed | user=%s", username)
            return None, "認証システムの設定に問題があります。システム管理者に連絡してください。"
        except Exception:  # noqa: BLE001
            logger.exception("LDAP unexpected error | user=%s", username)
            return None, "認証処理中に予期せぬエラーが発生しました。システム管理者に連絡してください。"

    def _attempt_single_candidate(self, *, username, password, server, host, host_is_ip, cfg, force_starttls,
                                   label, bind_user, auth_kind, last_errors):
        """単一のバインド候補 (label, bind_user, auth_kind) を試行し結果を返す。

        戻り値:
          - (User インスタンス, None): 認証 + 検索成功
          - (False, None): bind 成功したが検索結果 0 件 → 早期に全体 None を返すべきシグナル
          - (None, エラーメッセージ): 失敗 (次候補継続)
        """
        from ldap3 import NTLM, SIMPLE  # 遅延 import (各候補で失敗を局所化)
        try:
            conn = self._prepare_connection(server, bind_user, password, auth_kind)
            if not cfg.use_ssl and force_starttls and not self._start_tls_if_needed(conn, host, bind_user, label, last_errors):
                return None, "セキュアな接続（STARTTLS）の確立に失敗しました。"
            
            if not self._bind_connection(conn, host, host_is_ip, cfg.use_ssl, force_starttls, label, auth_kind, last_errors):
                # 最後のエラーからメッセージを生成
                if last_errors:
                    _, _, result = last_errors[-1]
                    if isinstance(result, dict) and result.get('description') == 'invalidCredentials':
                        return None, "ユーザー名またはパスワードが正しくありません。"
                return None, "LDAPサーバーへの接続に失敗しました。"
            
            entry = self._search_user_entry(conn, username, host, label, cfg.search_base, last_errors)
            if not entry:
                conn.unbind()
                return False, None  # 認証は通ったがユーザが居ない
            
            user = self._ensure_local_user(username, entry, cfg.upn_suffix, cfg.domain)
            self._sync_profile_from_ldap(user, entry)
            # 同一 OU / 親 OU の関連ユーザを M2M なしでローカル User として確保
            self._provision_related_users(conn, entry, user, cfg, username)
            conn.unbind()
            logger.info(
                "LDAP auth success | user=%s attempt=%s bind_user=%s host=%s",
                username, label, bind_user, host,
                extra={'ldap': {'attempt': label, 'bind_user': bind_user, 'host': host}}
            )
            return user, None
        except Exception as e:  # noqa: BLE001
            logger.debug(
                "LDAP attempt exception | user=%s label=%s error=%s", username, label, e,
                extra={'ldap': {'attempt': label}}
            )
            last_errors.append((label, str(e), {'description': 'exception'}))
            return None, "認証処理中にエラーが発生しました。"
            
    def _generate_user_friendly_error(self, last_errors):
        """エラーの詳細からユーザーに表示するメッセージを生成"""
        if not last_errors:
            return "認証に失敗しました。"
            
        # 直近のエラー (最後) を抽出
        _, last_error, last_result = last_errors[-1]

        def any_error_contains(*keywords):
            """蓄積された last_errors の文字列/description に指定キーワードのいずれかが含まれるか。"""
            for _label, le_msg, res in last_errors:
                texts = [le_msg or ""]
                if isinstance(res, dict):
                    texts.append(str(res.get('description') or ''))
                    texts.append(str(res.get('message') or ''))
                joined = ' '.join(texts).lower()
                if any(k.lower() in joined for k in keywords):
                    return True
            return False

        # ========== 分類ポリシー ==========
        # カテゴリ1 (ユーザ自己解決): 資格情報誤り
        # カテゴリ2 (運用窓口対応): ネットワーク不通 / LDAP接続はできたがユーザ未登録（このケースは呼び出し側で直接返却されるが保険）
        # カテゴリ3 (保守SE): DNS解決不可 / 設定不足 / TLS失敗 (自己解決不可) / 想定外例外

        # --- 1) invalidCredentials ---
        if isinstance(last_result, dict) and last_result.get('description') == 'invalidCredentials':
            return (
                "【資格情報誤り】ユーザー名またはパスワードが正しくありません。 "  # カテゴリ1
                "入力を再確認し、CapsLock/VPN/IME状態を確認して再試行してください。"
            )

        # --- 2) ネットワーク / 接続不可 ---
        if any_error_contains(
            "can't contact ldap server", "connect error", "socket connection error", "timeout", "timed out",
            "unreachable", "connection refused", "10060"
        ):
            return (
                "【接続不可/タイムアウト】LDAPサーバーに到達できません (ネットワーク/接続エラー)。 "
                "LAN/無線/VPN を確認し問題なければ、運用窓口へ『LDAPサーバーに接続不可 (ネットワーク不通/タイムアウト)』と連絡してください。"
            )

        # --- 2b) サーバーアドレス不正 / DNS 解決不能 ---
        if any_error_contains("invalid server address", "unknown host", "name or service not known", "nodename nor servname provided"):
            return (
                "【DNS解決不可】LDAPサーバーのホスト名/アドレスを解決できません。 "
                "運用窓口へ『LDAPサーバー設定(ホスト名/ポート)要確認』と連絡してください。"
            )

        # --- 3) StartTLS / TLS 関連 (ユーザ操作では解決困難) ---
        if any_error_contains("starttls", "tls", "ssl"):
            return (
                "【暗号化初期化失敗】セキュア接続の初期化に失敗しました。 "  # カテゴリ3
                "運用窓口経由で保守担当へ『LDAP StartTLS/SSL 失敗』と連絡してください。"
            )

        # --- 4) その他の例外 (設定不足・不明) ---
        return "【分類不能】認証に失敗しました。運用窓口へ状況を報告し、必要に応じて保守担当へエスカレーションしてください。"

    # -------- 認証補助 (分割) --------
    def _generate_bind_candidates(self, username: str, cfg: LDAPRuntimeConfig) -> Iterable[Tuple[str, str, Optional[str]]]:
        """与えられた `username` と設定から bind 候補を優先順位付きで生成する。

        生成ルール (重複排除 / 上から順に試行):
          1. 入力に `\\` が含まれる → そのまま: "NTLM(as-is)" (auth_kind='NTLM')
          2. 入力に `@` が含まれる  → そのまま: "UPN(as-is)" (auth_kind=None ⇒ SIMPLE)
          3. `\\` も `@` も無く cfg.domain があれば "NTLM(domain)": `domain\\username`
          4. (3 の条件後) UPN サフィックスを決定できれば "UPN(constructed)": `username@suffix`
             (suffix は cfg.upn_suffix 優先 / 無ければ cfg.domain が FQDN(ドット含む) の場合に流用)

        auth_kind:
          'NTLM' → ldap3 の NTLM 認証を使用 / None → SIMPLE (UPN) 認証。

        例:
          - 入力: "corp\\alice" domain=EXAMPLE upn_suffix=None
              → [ ("NTLM(as-is)", "corp\\alice", 'NTLM') ]  (すでに \\ を含むため他生成無し)
          - 入力: "alice@example.com" domain=EXAMPLE
              → [ ("UPN(as-is)", "alice@example.com", None) ]
          - 入力: "alice" domain=EXAMPLE upn_suffix=None
              → [ ("NTLM(domain)", "EXAMPLE\\alice", 'NTLM') ]  (domain にドット無く UPN 構築不可)
          - 入力: "alice" domain=example upn_suffix=example.local
              → [ ("NTLM(domain)", "example\\alice", 'NTLM'), 
                  ("UPN(constructed)", "alice@example.local", None) ]
          - 入力: "alice" domain=corp.example.com upn_suffix=None
              → [ ("NTLM(domain)", "corp.example.com\\alice", 'NTLM'),
                  ("UPN(constructed)", "alice@corp.example.com", None) ]
          - 入力: "alice" domain="" upn_suffix=example.com
              → [ ("UPN(constructed)", "alice@example.com", None) ]

        戻り値: 各要素 (label:説明, user:bindユーザー文字列, auth_kind:'NTLM' or None)
        """
        original = username
        yielded = set()
        def push(item):
            if item[1] in yielded:
                return
            yielded.add(item[1])
            yield item
        if '\\' in original:
            yield from push(("NTLM(as-is)", original, 'NTLM'))
        if '@' in original:
            yield from push(("UPN(as-is)", original, None))
        if '\\' not in original and '@' not in original and cfg.domain:
            yield from push(("NTLM(domain)", f"{cfg.domain}\\{original}", 'NTLM'))
        if '\\' not in original and '@' not in original:
            suffix = cfg.upn_suffix or (cfg.domain if cfg.domain and '.' in cfg.domain else None)
            if suffix:
                yield from push(("UPN(constructed)", f"{original}@{suffix}", None))

    def _prepare_connection(self, server, bind_user, password, auth_kind):
        """ldap3 Connection をまだ bind せず生成 (auto_bind=False)."""
        from ldap3 import Connection, NTLM, SIMPLE
        auth_method = NTLM if auth_kind == 'NTLM' else SIMPLE
        return Connection(
            server,
            user=bind_user,
            password=password,
            authentication=auth_method,
            auto_bind=False,
            raise_exceptions=False,
        )

    # ===== Helper methods (読みやすさ向上用) =====
    def _parse_host_port(self, url, use_ssl):
        """LDAP URL から host/port を抽出 (port なければ 636/389 既定)."""
        parsed = urlparse(url)
        host = parsed.hostname or url
        port = parsed.port or (636 if use_ssl else 389)
        return host, port

    def _build_tls(self, use_ssl, force_starttls, ssl_mod):
        """LDAPS/StartTLS 用 Tls オブジェクト (不要なら None)."""
        if not (use_ssl or force_starttls):
            return None
        try:
            from ldap3 import Tls  # 局所 import
            validate_mode = ssl_mod.CERT_NONE if getattr(settings, 'LDAP_TLS_INSECURE', False) else ssl_mod.CERT_REQUIRED
            return Tls(validate=validate_mode)
        except Exception:  # noqa: BLE001
            return None

    def _is_ipv4_like(self, host: str) -> bool:
        """ホスト文字列が単純な IPv4 形式か判定 (証明書検証ログ用途)."""
        try:
            if host.count('.') != 3:
                return False
            return all(part.isdigit() and 0 <= int(part) <= 255 for part in host.split('.'))
        except Exception:  # noqa: BLE001
            return False

    # 互換: 旧メソッド名 (内部では新方式に委譲)
    def _build_candidate_credentials(self, username: str, domain: str, upn_suffix: Optional[str]):  # pragma: no cover - 互換維持
        """互換: 旧 API 名で候補列挙を返す (新実装へ委譲)."""
        cfg = LDAPRuntimeConfig(
            server_url='', search_base='', domain=domain, upn_suffix=upn_suffix,
            use_ssl=False, force_starttls=False, allow_plain=True
        )
        return list(self._generate_bind_candidates(username, cfg))

    def _log_no_candidates(self, username, domain, upn_suffix, use_ssl, force_starttls, allow_plain):
        """候補が 0 件だった状況と生成ルールヒントを警告ログ出力."""
        logger.warning(
            "LDAP no credential candidates | user=%s original=%s domain=%s upn_suffix=%s use_ssl=%s force_starttls=%s allow_plain=%s",
            username, username, domain or '', upn_suffix or '', use_ssl, force_starttls, allow_plain
        )
        logger.warning(
            "LDAP candidate generation hint | conditions: (has \\ => NTLM(as-is)) (has @ => UPN(as-is)) (domain set => NTLM(domain)) (suffix/domain with dot => UPN(constructed))"
        )

    def _start_tls_if_needed(self, conn, host, bind_user, label, last_errors):
        """必要条件を満たす場合に StartTLS を実行 (失敗時は記録して False)."""
        if conn.start_tls():
            return True
        logger.warning(
            "LDAP StartTLS failed | host=%s user=%s label=%s last_error=%s result=%s",
            host, bind_user, label, conn.last_error, conn.result,
            # ログ構造キー統一: ldap_params -> ldap
            extra={'ldap': {'attempt': label, 'user': bind_user, 'stage': 'starttls'}}
        )
        last_errors.append((label, conn.last_error, conn.result))
        conn.unbind()
        return False

    def _bind_connection(self, conn, host, host_is_ip, use_ssl, force_starttls, label, auth_method, last_errors):
        """Connection.bind を実行し成功可否 (失敗時詳細を蓄積)."""
        if conn.bind():
            return True
        result_dict = conn.result if isinstance(conn.result, dict) else {}
        result_code = result_dict.get('result')
        result_desc = result_dict.get('description') or getattr(conn.result, 'description', None)
        result_msg = result_dict.get('message')
        logger.warning(
            "LDAP bind failed | host=%s ip=%s secure_ssl=%s starttls=%s label=%s auth=%s code=%s desc=%s message=%s last_error=%s",
            host, host_is_ip, use_ssl, force_starttls, label, auth_method, result_code, result_desc, result_msg, conn.last_error,
            extra={'ldap': {
                'host': host, 
                'is_ip': host_is_ip, 
                'use_ssl': use_ssl, 
                'starttls': force_starttls, 
                'auth_method': auth_method, 
                'error_code': result_code, 
                'description': result_desc,
                'message': result_msg,
                'attempt': label
            }}
        )
        last_errors.append((label, conn.last_error, conn.result))
        conn.unbind()
        return False

    def _search_user_entry(self, conn, username, host, label, search_base, last_errors):
        """sAMAccountName でユーザ検索し最初のエントリ (無ければ None)."""
        from ldap3 import SUBTREE  # 局所 import (既に本体で import されているが保険)
        search_filter = f'(sAMAccountName={username})'
        attributes = ['cn', 'mail', 'distinguishedName', 'department', 'title', 'memberOf', 'givenName', 'sn', 'displayName']
        if not conn.search(search_base=search_base, search_filter=search_filter, search_scope=SUBTREE, attributes=attributes):
            logger.warning(
                "LDAP search returned no entries | host=%s bind_user=%s filter=%s base=%s",
                host, conn.user, search_filter, search_base,
                # ログ構造キー統一: ldap_params -> ldap
                extra={'ldap': {'attempt': label, 'filter': search_filter, 'base': search_base}}
            )
            return None
        if not conn.entries:
            logger.warning("LDAP search empty entries | host=%s bind_user=%s", host, conn.user)
            return None
        return conn.entries[0]

    def _ensure_local_user(self, username, entry, upn_suffix, domain):
        """ローカルユーザを取得/新規作成し返す (作成時は最小属性設定)."""
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            display_name = str(getattr(entry, 'displayName', '') or getattr(entry, 'cn', '') or username)
            first_name, last_name = (display_name, '')
            if ' ' in display_name:
                first_name, last_name = display_name.split(' ', 1)
            email_attr = str(getattr(entry, 'mail', '') or f"{username}@{(upn_suffix or domain or 'local')}")
            # Django の UserManager (BaseUserManager) には create_user が定義されているが
            # 型チェッカがカスタムユーザ経由で解決できず警告を出すケースがあるため明示的に cast。
            manager = cast(Any, UserModel.objects)
            user = manager.create_user(  # type: ignore[attr-defined]
                username=username,
                email=email_attr,
                first_name=first_name,
                last_name=last_name,
            )
            user.set_unusable_password()
            user.save()
            return user

    def _sync_profile_from_ldap(self, user, entry):
        """LDAP 属性差分を同期し、DN から OU コードを自動抽出 (失敗しても例外抑止).

        要件対応:
          1. DN 最下層 OU (ユーザ直下) を所属コード (department_code) として保存
          2. その 1 階層上の OU を parent_department_code として保存
          (従来手動だった parent_department_code を自動化 / OU が不足する場合は空のまま)
        """
        try:
            from .models import UserSource  # 遅延 import
            from django.utils import timezone
            new_dn = str(getattr(entry, 'distinguishedName', '') or '')
            changed: list[str] = []

            if user.source != UserSource.LDAP:
                user.source = UserSource.LDAP
                changed.append('source')
            if new_dn and user.ldap_dn != new_dn:
                user.ldap_dn = new_dn
                changed.append('ldap_dn')

            # DN 解析: "CN=...,OU=Child,OU=Parent,DC=example,DC=com"
            def extract_ou_levels(dn: str) -> tuple[str, str]:
                try:
                    parts = [p.strip() for p in dn.split(',') if p]
                    # 最初に出現する OU= が最下層 (ユーザーに最も近い OU)
                    first_ou_index = None
                    for i, p in enumerate(parts):
                        if p.upper().startswith('OU='):
                            first_ou_index = i
                            break
                    if first_ou_index is None:
                        return '', ''
                    # same level OU 名
                    same_ou_name = parts[first_ou_index][3:]
                    # 1 階層上 OU 名 (連続して OU= が続く場合のみ)
                    upper_ou_name = ''
                    if first_ou_index + 1 < len(parts) and parts[first_ou_index + 1].upper().startswith('OU='):
                        upper_ou_name = parts[first_ou_index + 1][3:]
                    return same_ou_name, upper_ou_name
                except Exception:  # noqa: BLE001
                    return '', ''

            same_ou_name, upper_ou_name = extract_ou_levels(new_dn)
            if same_ou_name and user.department_code != same_ou_name:
                user.department_code = same_ou_name
                changed.append('department_code')
            if upper_ou_name and user.parent_department_code != upper_ou_name:
                user.parent_department_code = upper_ou_name
                changed.append('parent_department_code')

            user.last_synced_at = timezone.now()
            if changed:
                user.save(update_fields=list(set(changed + ['last_synced_at'])))
                logger.info(
                    "LDAP user fields changed | user=%s changed=%s", user.username, ','.join(changed)
                )
        except Exception:  # noqa: BLE001
            logger.debug("User LDAPフィールド同期失敗をスキップ")

    def _provision_related_users(self, conn, primary_entry, primary_user, cfg, current_username):
        """同一 OU / 1階層上 OU の LDAP ユーザを検索しローカル User を必要に応じて生成。

        モデル変更なしで後続の承認者選択候補を増やす目的。
        再帰なし / 1階層のみ。
        """
        try:
            dn = str(getattr(primary_entry, 'distinguishedName', '') or '')
            if not dn:
                return
            parts = [p.strip() for p in dn.split(',') if p.strip()]
            first_ou_idx = None
            for i, p in enumerate(parts):
                if p.upper().startswith('OU='):
                    first_ou_idx = i
                    break
            if first_ou_idx is None:
                return
            same_ou_base = ','.join(parts[first_ou_idx:])  # OU=Child,OU=Parent,...
            parent_ou_base = ''
            if first_ou_idx + 1 < len(parts) and parts[first_ou_idx + 1].upper().startswith('OU='):
                parent_ou_base = ','.join(parts[first_ou_idx + 1:])

            from ldap3 import SUBTREE
            # 検索共通定義
            related_specs = [("same", same_ou_base), ("upper", parent_ou_base)]
            for kind, base in related_specs:
                if not base or 'OU=' not in base:
                    continue
                try:
                    # 性能抑制: サイズ制限 (必要なら設定化) 50 ユーザまで
                    if not conn.search(
                        search_base=base,
                        search_filter='(sAMAccountName=*)',
                        search_scope=SUBTREE,
                        attributes=['sAMAccountName', 'displayName', 'mail', 'distinguishedName', 'givenName', 'sn'],
                        size_limit=50,
                    ):
                        continue
                except Exception:  # noqa: BLE001
                    continue
                entries = getattr(conn, 'entries', [])
                if not entries:
                    continue
                UserModel = get_user_model()
                created = 0
                for e in entries:
                    try:
                        uname = str(getattr(e, 'sAMAccountName', '') or '')
                        if not uname or uname.lower() == current_username.lower():
                            continue
                        if UserModel.objects.filter(username=uname).exists():
                            # 既存ユーザも DN 情報があれば同期
                            u = UserModel.objects.get(username=uname)
                            self._sync_profile_from_ldap(u, e)
                            continue
                        # 新規作成 → 最低限フィールド埋める
                        u = self._ensure_local_user(uname, e, cfg.upn_suffix, cfg.domain)
                        self._sync_profile_from_ldap(u, e)
                        created += 1
                    except Exception:  # noqa: BLE001
                        continue
                if created:
                    logger.info(
                        "LDAP related users provisioned | user=%s kind=%s created=%d base=%s", \
                        current_username, kind, created, base
                    )
        except Exception:  # noqa: BLE001
            logger.debug("関連ユーザ自動生成をスキップ (例外発生)")

    def _log_all_attempt_fail(self, username, host, host_is_ip, domain, last_errors, use_ssl, force_starttls):
        """全候補失敗時に試行概要と各試行詳細を詳細ログ出力."""
        attempt_count = len(last_errors)
        logger.warning(
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
            
            # エラーの詳細情報をわかりやすく出力
            logger.warning(
                "LDAP auth failure | user=%s attempt=%s error_code=%s description=%s message=%s last_error=%s", 
                username, l, code, desc, msg, le,
                extra={'ldap': {'attempt': l, 'error_code': code, 'description': desc, 'message': msg}}
            )
