"""リアルタイム通知(将来拡張) / 現状はロングポーリング同期用 no-op フック。

将来 WebSocket / SSE / Push を再導入する際はここの実装を差し替えるだけで
呼び出し側 (state_machine / views) を変更せずに済むよう抽象化している。
"""
from __future__ import annotations
from typing import Any

def broadcast_application_state(_application: Any) -> None:  # pragma: no cover - no-op
    """申請更新をクライアントへ即時反映するためのブロードキャスト (現状 no-op)。

    Long Polling ではクライアントが差分取得する pull モデルのため push 不要。
    テスト (patch) しやすさ + 今後の拡張余地確保のため関数として残す。
    """
    return None
