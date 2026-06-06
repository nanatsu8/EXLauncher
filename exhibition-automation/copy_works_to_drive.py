"""copy_works_to_drive.py

ローカルの works を Drive 同期フォルダへコピー同期するツール。

目的:
- apply_update.py の rename ベース切替を Drive 側に適用しない
- ローカル works を Drive 側に安全に反映する

使い方（例）:
  python copy_works_to_drive.py --dst "C:/Users/xxx/マイドライブ/ExhibitionLauncher/works"
  python copy_works_to_drive.py --src "../exhibition-launcher/works" --dst "C:/.../works" --mirror
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import Iterable

import json5
from cli_error import describe_exception, print_error_report
from path_utils import get_runtime_base_dir, resolve_config_path

CONFIG_FILE = "config.json5"
DEFAULT_EXCLUDES = {"desktop.ini", "thumbs.db"}


def load_config(base_dir: Path) -> dict:
    config_path = base_dir / CONFIG_FILE
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json5.load(f)


def resolve_path(base_dir: Path, raw_path: str | None) -> Path | None:
    return resolve_config_path(base_dir, raw_path)


def should_skip(name: str, excludes: set[str]) -> bool:
    return name.lower() in excludes


def iter_source_files(src: Path, excludes: set[str]) -> Iterable[Path]:
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path.name, excludes):
            continue
        yield path


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def remove_readonly_and_retry(func, path, _exc_info) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree_with_retry(target: Path, retries: int = 8, delay_sec: float = 0.5) -> None:
    if not target.exists():
        return

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            shutil.rmtree(target, onerror=remove_readonly_and_retry)
            return
        except OSError as e:
            last_error = e
            if getattr(e, "winerror", None) in {5, 32} and attempt < retries:
                time.sleep(delay_sec)
                continue
            raise
    if last_error:
        raise last_error


def copy_changed_files(src: Path, dst: Path, excludes: set[str]) -> tuple[int, int]:
    copied = 0
    skipped = 0

    for src_file in iter_source_files(src, excludes):
        rel = src_file.relative_to(src)
        dst_file = dst / rel
        ensure_parent(dst_file)

        if dst_file.exists():
            src_stat = src_file.stat()
            dst_stat = dst_file.stat()
            if src_stat.st_size == dst_stat.st_size and int(src_stat.st_mtime) == int(dst_stat.st_mtime):
                skipped += 1
                continue

        shutil.copy2(src_file, dst_file)
        copied += 1

    return copied, skipped


def remove_extra_entries(src: Path, dst: Path, excludes: set[str]) -> tuple[int, int]:
    removed_files = 0
    removed_dirs = 0

    # ファイル削除
    for dst_file in sorted(
        (p for p in dst.rglob("*") if p.is_file()), key=lambda p: len(p.parts), reverse=True
    ):
        if should_skip(dst_file.name, excludes):
            continue
        rel = dst_file.relative_to(dst)
        src_file = src / rel
        if not src_file.exists():
            dst_file.unlink()
            removed_files += 1

    # 空または不要ディレクトリ削除（深い順）
    for dst_dir in sorted(
        (p for p in dst.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
    ):
        if should_skip(dst_dir.name, excludes):
            continue
        rel = dst_dir.relative_to(dst)
        src_dir = src / rel
        if not src_dir.exists():
            shutil.rmtree(dst_dir, ignore_errors=True)
            removed_dirs += 1

    return removed_files, removed_dirs


def write_sync_report(dst: Path, copied: int, skipped: int, removed_files: int, removed_dirs: int) -> None:
    report = {
        "copied_files": copied,
        "skipped_files": skipped,
        "removed_files": removed_files,
        "removed_dirs": removed_dirs,
    }
    report_path = dst / "sync_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ローカル works を Drive 側へコピー同期")
    parser.add_argument(
        "--src", help="コピー元 works パス。未指定時は config の works_dir -> ../exhibition-launcher/works"
    )
    parser.add_argument("--dst", help="コピー先 Drive パス。未指定時は config の drive_master_dir")
    parser.add_argument(
        "--mirror", action="store_true", help="コピー先の余剰ファイル/フォルダを削除して鏡像化"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="除外名を追加（複数指定可）。例: --exclude desktop.ini",
    )
    return parser.parse_args()


def main() -> int:
    script_dir = get_runtime_base_dir(__file__)

    os.chdir(script_dir)
    args = parse_args()

    config = load_config(script_dir)
    if config is None:
        print_error_report(
            "設定の読み込みに失敗しました",
            "設定ファイルを読み込めませんでした。",
            code="CONFIG_LOAD_FAILED",
            hint="config.json5 の内容と保存場所を確認してから、もう一度実行してください。",
        )
        return 1

    # src_raw = args.src or config.get("works_dir") or "../exhibition-launcher/works"
    src_raw = args.src or config.get("works_dir")
    dst_raw = args.dst or config.get("drive_master_dir")

    if dst_raw is None:
        print_error_report(
            "コピー先が未設定です",
            "Drive 側の出力先が決まっていません。",
            code="DESTINATION_NOT_SET",
            hint="--dst を指定するか、config.json5 の drive_master_dir を設定してください。",
            detail=f"config: {script_dir / CONFIG_FILE}",
        )
        return 1

    try:
        src = resolve_path(script_dir, src_raw)
        dst = resolve_path(script_dir, dst_raw)
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

    if src is None or dst is None:
        detail_lines = []
        if src is None:
            detail_lines.append(f"src_raw: {src_raw}")
        if dst is None:
            detail_lines.append(f"dst_raw: {dst_raw}")
        print_error_report(
            "src/dst の解決に失敗しました",
            "入力パスを実際のフォルダに変換できませんでした。",
            code="PATH_RESOLVE_FAILED",
            hint="--src と --dst の値を見直してから、もう一度実行してください。",
            detail="\n".join(detail_lines) if detail_lines else None,
        )
        return 1

    if not src.exists() or not src.is_dir():
        print_error_report(
            "コピー元が見つかりません",
            "指定されたコピー元フォルダが存在しません。",
            code="SOURCE_NOT_FOUND",
            hint="--src の値とフォルダの存在を確認してください。",
            detail=str(src),
        )
        return 1

    if src.resolve() == dst.resolve():
        print_error_report(
            "コピー元とコピー先が同一です",
            "同じフォルダに対してコピーしようとしています。",
            code="SAME_SOURCE_AND_DESTINATION",
            hint="--src と --dst を別のフォルダに設定してください。",
            detail=str(src.resolve()),
        )
        return 1

    excludes = set(DEFAULT_EXCLUDES)
    excludes.update(name.lower() for name in config.get("copy_exclude_names", []))
    excludes.update(name.lower() for name in args.exclude)

    print("=" * 50)
    print("copy_works_to_drive")
    print("=" * 50)
    print(f"コピー元: {src}")
    print(f"コピー先: {dst}")
    print(f"mirror  : {args.mirror}")
    print("-" * 50)

    try:
        if dst.exists():
            print(f"既存のコピー先を削除しています: {dst}")
            rmtree_with_retry(dst)
        dst.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        report = describe_exception(e)
        print_error_report(
            "コピー先の削除に失敗しました",
            report.summary,
            code=report.code,
            hint=report.hint,
            detail=report.detail,
        )
        return 1

    copied, skipped = copy_changed_files(src, dst, excludes)
    removed_files = 0
    removed_dirs = 0

    if args.mirror:
        removed_files, removed_dirs = remove_extra_entries(src, dst, excludes)

    write_sync_report(dst, copied, skipped, removed_files, removed_dirs)

    print("✅ 同期完了")
    print(f"  コピー: {copied} ファイル")
    print(f"  スキップ: {skipped} ファイル")
    if args.mirror:
        print(f"  削除(ファイル): {removed_files}")
        print(f"  削除(ディレクトリ): {removed_dirs}")
    print(f"  レポート: {dst / 'sync_report.json'}")
    input("Enter キーを押して終了します...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
