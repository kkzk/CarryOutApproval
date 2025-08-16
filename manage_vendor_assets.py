#!/usr/bin/env python
"""Vendor asset manager

機能:
    - vendor_assets.json を読み取りライブラリを一括ダウンロード
    - すべてのアーカイブ / 単一ファイルを download_dir (設定) に保存
    - static/vendor/<name>/<version>/ 以下へ必要ファイル/ディレクトリを展開
    - 既存があり --force 指定なしならスキップ（ダウンロードファイルは再利用）
    - --extract-only でネットワーク非依存再展開 (download_dir 内成果物必須)
    - 展開後 CSS/JS の SHA256 を表示

使い方:
  uv run python manage_vendor_assets.py              # 初回 / 追加
  uv run python manage_vendor_assets.py --force      # 再取得
  uv run python manage_vendor_assets.py --verify     # ハッシュ表示のみ
  uv run python manage_vendor_assets.py --extract-only  # 既存ダウンロードを再展開（オフライン対応）

設定ファイル: vendor_assets.json
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import urllib.request
import zipfile

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / 'vendor_assets.json'

@dataclass
class FileEntry:
    src: str
    dest: str

@dataclass
class LibrarySpec:
    name: str
    version: str
    type: str  # 'zip' or 'single'
    url: str
    zip_root: str | None = None
    files: List[FileEntry] | None = None
    extra_dirs: List[str] | None = None
    single_file_name: str | None = None

@dataclass
class Config:
    download_dir: Path
    static_vendor_root: Path
    libraries: List[LibrarySpec]

def load_config() -> Config:
    if not CONFIG_FILE.exists():
        print(f"設定ファイルが見つかりません: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    libs: List[LibrarySpec] = []
    for raw in data.get('libraries', []):
        files = [FileEntry(**f) for f in raw.get('files', [])]
        libs.append(LibrarySpec(
            name=raw['name'],
            version=raw['version'],
            type=raw['type'],
            url=raw['url'],
            zip_root=raw.get('zip_root'),
            files=files if files else None,
            extra_dirs=raw.get('extra_dirs'),
            single_file_name=raw.get('single_file_name')
        ))
    return Config(
        download_dir=BASE_DIR / data['download_dir'],
        static_vendor_root=BASE_DIR / data['static_vendor_root'],
        libraries=libs
    )

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def download(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r, dest.open('wb') as f:
        shutil.copyfileobj(r, f)

def ensure_library(spec: LibrarySpec, cfg: Config, force: bool, extract_only: bool):
    out_dir = cfg.static_vendor_root / spec.name / spec.version
    if out_dir.exists() and not force:
        print(f"[SKIP] {spec.name} {spec.version} already exists.")
        return
    if out_dir.exists() and force:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ダウンロード格納
    dl_dir = cfg.download_dir / f"{spec.name}-{spec.version}"
    dl_dir.mkdir(parents=True, exist_ok=True)

    if spec.type == 'single':
        target_file = dl_dir / (spec.single_file_name or 'file')
        if not target_file.exists():
            if extract_only:
                raise FileNotFoundError(f"[MISS] {spec.name} の既存ダウンロードがありません: {target_file}")
            print(f"[DL ] {spec.name} -> {target_file}")
            download(spec.url, target_file)
        else:
            if force and not extract_only:
                # 強制再取得
                print(f"[REDL] {spec.name} -> {target_file}")
                download(spec.url, target_file)
            else:
                print(f"[REUSE] {spec.name} existing file {target_file}")
        shutil.copy2(target_file, out_dir / (spec.single_file_name or target_file.name))
    elif spec.type == 'zip':
        zip_path = dl_dir / 'archive.zip'
        if not zip_path.exists():
            if extract_only:
                raise FileNotFoundError(f"[MISS] {spec.name} の既存ZIPがありません: {zip_path}")
            print(f"[DL ] {spec.name} -> {zip_path}")
            download(spec.url, zip_path)
        else:
            if force and not extract_only:
                print(f"[REDL] {spec.name} -> {zip_path}")
                download(spec.url, zip_path)
            else:
                print(f"[REUSE] {spec.name} existing archive {zip_path}")
        # ZIP シグネチャ確認
        with zip_path.open('rb') as f:
            sig = f.read(2)
            if sig != b'PK':
                raise RuntimeError(f"Invalid ZIP signature for {spec.name} (got {sig!r})")
        with tempfile.TemporaryDirectory() as td:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(td)
            root = Path(td)
            if spec.zip_root:
                candidate = root / spec.zip_root
                if candidate.exists():
                    root = candidate
            # ファイルコピー
            if spec.files:
                for fe in spec.files:
                    src_path = root / fe.src
                    if not src_path.exists():
                        print(f"[WARN] missing {fe.src} for {spec.name}")
                        continue
                    dest_path = out_dir / fe.dest
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dest_path)
            # extra dirs
            if spec.extra_dirs:
                for d in spec.extra_dirs:
                    src_dir = root / d
                    if src_dir.exists():
                        shutil.copytree(src_dir, out_dir / d, dirs_exist_ok=True)
                    else:
                        print(f"[WARN] missing dir {d} for {spec.name}")
    else:
        raise ValueError(f"Unknown type: {spec.type}")

    # ハッシュ表示
    hashes = []
    for p in out_dir.rglob('*'):
        if p.is_file() and p.suffix in {'.css', '.js'}:
            hashes.append((p.relative_to(cfg.static_vendor_root), sha256(p)))
    if hashes:
        print(f"[HASH] {spec.name}")
        for rel, h in hashes:
            print(f"  {rel}  {h[:16]}...")


def verify(cfg: Config):
    ok = True
    for spec in cfg.libraries:
        out_dir = cfg.static_vendor_root / spec.name / spec.version
        if not out_dir.exists():
            print(f"[MISS] {spec.name} {spec.version}")
            ok = False
    if ok:
        print("All vendor assets present.")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true', help='再取得')
    ap.add_argument('--verify', action='store_true', help='存在確認のみ (ダウンロードや展開は行わない)')
    ap.add_argument('--extract-only', action='store_true', help='既存ダウンロードを再展開 (ネットワークアクセスしない)')
    args = ap.parse_args()

    cfg = load_config()
    cfg.download_dir.mkdir(parents=True, exist_ok=True)
    cfg.static_vendor_root.mkdir(parents=True, exist_ok=True)

    if args.verify:
        ok = verify(cfg)
        sys.exit(0 if ok else 1)

    for spec in cfg.libraries:
        ensure_library(spec, cfg, force=args.force, extract_only=args.extract_only)

    print('完了')

if __name__ == '__main__':
    main()
