"""update_manifest.py

ローカルの works フォルダの manifest.json を再生成するツール。

目的:
- ローカルの works を直接編集した後、manifest を更新する
- apply_update.py のチェック対象を整える

使い方（例）:
  python update_manifest.py --dir ../exhibition-launcher/works
  python update_manifest.py                      # works_dir を config から使用
  python update_manifest.py --dir ../exhibition-launcher/dist/win-unpacked/resources/works
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import json5
from cli_error import describe_exception, print_error_report
from path_utils import get_runtime_base_dir, resolve_config_path

CONFIG_FILE = "config.json5"
MANIFEST_FILE = "manifest.json"


def hash_file(path: Path) -> str:
    """ファイルの SHA-256 ハッシュを計算"""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def build_manifest(target_dir: Path) -> dict:
    """target_dir 配下のファイル一覧とハッシュをまとめたマニフェストを生成"""
    files: dict[str, str] = {}
    for file_path in sorted(target_dir.rglob("*")):
        if file_path.is_file() and file_path.name != MANIFEST_FILE:
            rel = file_path.relative_to(target_dir).as_posix()
            files[rel] = hash_file(file_path)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "file_count": len(files),
        "files": files,
    }


def load_config(base_dir: Path) -> dict:
    config_path = base_dir / CONFIG_FILE
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json5.load(f)


def resolve_path(base_dir: Path, raw_path: str | None) -> Path | None:
    return resolve_config_path(base_dir, raw_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="works フォルダの manifest.json を再生成")
    parser.add_argument("--dir", help="対象ディレクトリ。未指定時は config の works_dir を使用")
    return parser.parse_args()


def main() -> int:
    script_dir = get_runtime_base_dir(__file__)

    os.chdir(script_dir)

    args = parse_args()

    config = load_config(script_dir)

    try:
        if args.dir:
            target_dir = resolve_path(script_dir, args.dir)
        else:
            raw_path = config.get("works_dir")
            target_dir = resolve_path(script_dir, raw_path)
    except ValueError as e:
        report = describe_exception(e)
        print_error_report(
            "パス解決エラー",
            report.summary,
            code=report.code,
            hint=report.hint,
            detail=report.detail,
        )
        return 1

    if target_dir is None:
        print_error_report(
            "対象ディレクトリが解決できませんでした",
            "manifest を作る対象フォルダが決まっていません。",
            code="TARGET_NOT_RESOLVED",
            hint="--dir オプションで明示的に指定してください。",
            detail="\n".join(
                [
                    f"script_dir: {script_dir}",
                    f"args.dir: {args.dir}",
                    f"config.works_dir: {config.get('works_dir')}",
                    "例: update_manifest.exe --dir ../exhibition-launcher/works",
                ]
            ),
        )
        return 1

    if not target_dir.exists():
        print_error_report(
            "対象ディレクトリが見つかりません",
            "指定されたフォルダが存在しません。",
            code="TARGET_NOT_FOUND",
            hint="--dir の値とフォルダの存在を確認してください。",
            detail=str(target_dir),
        )
        return 1

    if not target_dir.is_dir():
        print_error_report(
            "対象がディレクトリではありません",
            "指定された対象はフォルダではありません。",
            code="TARGET_NOT_DIRECTORY",
            hint="--dir にはフォルダを指定してください。",
            detail=str(target_dir),
        )
        return 1

    print("=" * 50)
    print("update_manifest")
    print("=" * 50)
    print(f"対象ディレクトリ: {target_dir}")
    print("-" * 50)
    print("manifest を生成中...")

    manifest = build_manifest(target_dir)
    manifest_path = target_dir / MANIFEST_FILE

    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    except Exception as e:
        report = describe_exception(e)
        print_error_report(
            "manifest 出力エラー",
            report.summary,
            code=report.code,
            hint=report.hint,
            detail=report.detail,
        )
        return 1

    print("✅ manifest 生成完了")
    print(f"  ファイル数: {manifest['file_count']}")
    print(f"  生成時刻: {manifest['generated_at']}")
    print(f"  出力先: {manifest_path}")
    print("\n次のステップ:")
    print("  必要に応じて apply_update.exe でコピー側に反映してください")
    input("\nEnterキーを押すと終了します...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
