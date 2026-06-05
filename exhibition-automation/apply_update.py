"""apply_update.py — ステージング領域の整合性チェックと本番切替

使い方:
    apply_update.exe            整合性チェック + 本番へ適用
    apply_update.exe --check    整合性チェックのみ（本番に触れない）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import time
from datetime import datetime
from pathlib import Path

import json5
from path_utils import get_runtime_base_dir, resolve_config_path

CONFIG_FILE = "config.json5"
MANIFEST_FILE = "manifest.json"


# ---------------------------------------------------------------------------
# 設定読み込み
# ---------------------------------------------------------------------------


def load_config(config_path: str = CONFIG_FILE) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return json5.load(f)


def resolve_dir(config: dict, key: str, base_dir: Path) -> Path:
    """config から相対/絶対パスを解決して Path を返す"""
    raw = config.get(key, "")
    if not raw:
        raise KeyError(f"config.json5 に '{key}' が設定されていません")
    resolved = resolve_config_path(base_dir, str(raw))
    if resolved is None:
        raise KeyError(f"config.json5 に '{key}' が設定されていません")
    return resolved


def print_error_report(
    title: str,
    summary: str,
    *,
    code: str | None = None,
    hint: str | None = None,
    detail: str | None = None,
) -> None:
    print(f"❌ {title}")
    print(f"   要点: {summary}")
    if code:
        print(f"   コード: {code}")
    if hint:
        print(f"   対処: {hint}")
    if detail:
        for line in detail.splitlines():
            print(f"   詳細: {line}")


def describe_exception(error: Exception) -> dict[str, str | None]:
    detail = str(error) or None

    if isinstance(error, FileNotFoundError):
        return {
            "title": "ファイルが見つかりません",
            "summary": "必要なファイルまたはフォルダがありません。",
            "code": "FILE_NOT_FOUND",
            "hint": "config.json5 と対象フォルダの配置を確認してから、もう一度実行してください。",
            "detail": detail,
        }

    if isinstance(error, PermissionError):
        return {
            "title": "アクセスできません",
            "summary": "ファイルやフォルダを操作する権限がありません。",
            "code": "PERMISSION_DENIED",
            "hint": "開いているアプリを閉じてから再実行し、必要なら管理者権限で試してください。",
            "detail": detail,
        }

    if isinstance(error, OSError):
        if getattr(error, "winerror", None) in {5, 32}:
            return {
                "title": "別のアプリが使っています",
                "summary": "対象ファイルまたはフォルダがロックされています。",
                "code": "WIN_FILE_LOCKED",
                "hint": "ランチャーやエクスプローラーで開いている対象を閉じてから、もう一度実行してください。",
                "detail": detail,
            }

        return {
            "title": "OS エラーが発生しました",
            "summary": "ファイル操作に失敗しました。",
            "code": "OS_ERROR",
            "hint": "対象フォルダの状態を確認してから再実行してください。",
            "detail": detail,
        }

    if isinstance(error, ValueError):
        return {
            "title": "設定値に問題があります",
            "summary": "config.json5 または入力値の内容に問題があります。",
            "code": "INVALID_VALUE",
            "hint": "設定ファイルの該当項目を見直してから再実行してください。",
            "detail": detail,
        }

    return {
        "title": "処理に失敗しました",
        "summary": "予期しないエラーが発生しました。",
        "code": "UNKNOWN_ERROR",
        "hint": "表示された詳細を添えて再実行してください。",
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# 整合性チェック
# ---------------------------------------------------------------------------


def hash_file(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def build_manifest(staging_dir: Path) -> dict:
    """staging_dir 配下のファイル一覧とハッシュをまとめたマニフェストを生成"""
    files: dict[str, str] = {}
    for file_path in sorted(staging_dir.rglob("*")):
        if file_path.is_file() and file_path.name != MANIFEST_FILE:
            rel = file_path.relative_to(staging_dir).as_posix()
            files[rel] = hash_file(file_path)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "file_count": len(files),
        "files": files,
    }


def verify_manifest(staging_dir: Path, manifest: dict) -> list[str]:
    """manifest の内容と staging_dir の実ファイルを照合し、差異を返す"""
    errors: list[str] = []
    recorded: dict[str, str] = manifest.get("files", {})

    # ファイル数チェック
    actual_count = sum(1 for f in staging_dir.rglob("*") if f.is_file() and f.name != MANIFEST_FILE)
    if actual_count != manifest.get("file_count", -1):
        errors.append(
            f"ファイル数が一致しません: manifest={manifest.get('file_count')}, 実際={actual_count}"
        )

    # ハッシュチェック
    for rel, expected_hash in recorded.items():
        actual_path = staging_dir / rel
        if not actual_path.exists():
            errors.append(f"ファイルが見つかりません: {rel}")
            continue
        actual_hash = hash_file(actual_path)
        if actual_hash != expected_hash:
            errors.append(f"ハッシュ不一致: {rel}")

    # manifest に記録されていない余剰ファイルを検出
    for file_path in staging_dir.rglob("*"):
        if file_path.is_file() and file_path.name != MANIFEST_FILE:
            rel = file_path.relative_to(staging_dir).as_posix()
            if rel not in recorded:
                errors.append(f"manifest 未記録のファイル: {rel}")

    return errors


# ---------------------------------------------------------------------------
# 切替
# ---------------------------------------------------------------------------


def remove_readonly_and_retry(func, path, _exc_info) -> None:
    """rmtree 中に読み取り専用属性で失敗した場合に解除して再試行する。"""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree_with_retry(target: Path, retries: int = 8, delay_sec: float = 0.5) -> None:
    """Windows の一時ロックを考慮してディレクトリ削除を再試行する。"""
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


def copytree_with_retry(source: Path, destination: Path, retries: int = 8, delay_sec: float = 0.5) -> None:
    """Windows の一時ロックを考慮してディレクトリコピーを再試行する。"""
    if not source.exists():
        raise FileNotFoundError(f"コピー元が見つかりません: {source}")

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            if destination.exists():
                rmtree_with_retry(destination, retries=retries, delay_sec=delay_sec)
            shutil.copytree(source, destination)
            return
        except OSError as e:
            last_error = e
            if getattr(e, "winerror", None) in {5, 32} and attempt < retries:
                time.sleep(delay_sec)
                continue
            raise
    if last_error:
        raise last_error


def atomic_switch(staging_dir: Path, works_dir: Path, backup_dir: Path) -> None:
    """
    staging → works の切替（失敗時に旧 works を自動復旧）

    手順:
    1. works を一時退避
    2. staging を works にコピー
    3. 旧 backup を削除し、一時退避を backup に確定

    2 で失敗した場合は一時退避から works を復旧する。
    """

    if not staging_dir.exists():
        raise FileNotFoundError(f"ステージングが見つかりません: {staging_dir}")

    temp_backup_dir = backup_dir.parent / f"{backup_dir.name}_new"
    if temp_backup_dir.exists():
        print(f"一時バックアップを削除: {temp_backup_dir}")
        rmtree_with_retry(temp_backup_dir)

    # 前回失敗で works が消えて backup だけある状態を自動復旧
    if not works_dir.exists() and backup_dir.exists():
        print("警告: works が存在しないため、backup から復旧して続行します。")
        copytree_with_retry(backup_dir, works_dir)

    if works_dir.exists():
        print(f"現 works → 一時退避: {works_dir} → {temp_backup_dir}")
        copytree_with_retry(works_dir, temp_backup_dir)

    try:
        if works_dir.exists():
            print(f"切替前の works を削除: {works_dir}")
            rmtree_with_retry(works_dir)

        print(f"staging → works (copy): {staging_dir} → {works_dir}")
        copytree_with_retry(staging_dir, works_dir)

        manifest_path = staging_dir / MANIFEST_FILE
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            errors = verify_manifest(works_dir, manifest)
            if errors:
                preview = "\n".join(f"   - {e}" for e in errors[:10])
                if len(errors) > 10:
                    preview += f"\n   - ... 他 {len(errors) - 10} 件"
                raise RuntimeError(f"works 側の整合性チェックに失敗しました:\n{preview}")

        print(f"反映済みステージングを削除: {staging_dir}")
        rmtree_with_retry(staging_dir)
    except Exception:
        # 失敗時は旧 works を復旧する
        if works_dir.exists():
            rmtree_with_retry(works_dir)
        if temp_backup_dir.exists():
            print("切替に失敗したため、旧 works を復旧します。")
            copytree_with_retry(temp_backup_dir, works_dir)
        raise

    if temp_backup_dir.exists():
        if backup_dir.exists():
            print(f"旧バックアップを削除: {backup_dir}")
            rmtree_with_retry(backup_dir)
        print(f"一時退避を backup に確定: {temp_backup_dir} → {backup_dir}")
        copytree_with_retry(temp_backup_dir, backup_dir)
        rmtree_with_retry(temp_backup_dir)


# ---------------------------------------------------------------------------
# サブコマンド実装
# ---------------------------------------------------------------------------


def cmd_check(staging_dir: Path) -> bool:
    """整合性チェックのみ。True = 問題なし"""
    manifest_path = staging_dir / MANIFEST_FILE
    if not manifest_path.exists():
        print_error_report(
            "整合性チェックに失敗しました",
            "manifest.json が見つかりません。",
            code="MANIFEST_MISSING",
            hint="先に build_works_from_csv.exe または copy_drive_master_to_staging.exe を実行してください。",
            detail=str(manifest_path),
        )
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"manifest: {manifest.get('generated_at')}  ファイル数: {manifest.get('file_count')}")
    print("整合性チェック中...")

    errors = verify_manifest(staging_dir, manifest)
    if errors:
        preview = "\n".join(f"- {err}" for err in errors[:10])
        if len(errors) > 10:
            preview += f"\n- ... 他 {len(errors) - 10} 件"
        print_error_report(
            "整合性チェックに失敗しました",
            f"差分が {len(errors)} 件見つかりました。",
            code="MANIFEST_MISMATCH",
            hint="staging の内容を更新してから、もう一度実行してください。",
            detail=preview,
        )
        return False

    print("✅ 整合性チェック OK")
    return True


def cmd_apply(staging_dir: Path, works_dir: Path, backup_dir: Path) -> None:
    """チェック → 適用"""
    if not cmd_check(staging_dir):
        print_error_report(
            "本番切替を中止しました",
            "先に整合性チェックで問題が見つかりました。",
            hint="表示された差分を解消してから、もう一度実行してください。",
        )
        sys.exit(1)

    print("\n本番切替を開始します...")
    try:
        atomic_switch(staging_dir, works_dir, backup_dir)
    except OSError as e:
        report = describe_exception(e)
        print_error_report(
            "本番切替に失敗しました",
            str(report["summary"]),
            code=report["code"],
            hint=report["hint"],
            detail=report["detail"],
        )
        sys.exit(1)

    print("✅ 切替完了")
    print(f"   本番: {works_dir}")
    print(f"   バックアップ: {backup_dir}")


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------


def main() -> int:
    script_dir = str(get_runtime_base_dir(__file__))
    os.chdir(script_dir)
    print(f"作業ディレクトリ: {script_dir}")

    parser = argparse.ArgumentParser(description="ステージング領域の整合性チェックと本番切替")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="整合性チェックのみ（本番に触れない）")
    args = parser.parse_args()

    print("=" * 50)
    print("apply_update — 本番切替ツール")
    print("=" * 50)

    try:
        config = load_config()
    except Exception as e:
        report = describe_exception(e)
        print_error_report(
            "設定の読み込みに失敗しました",
            str(report["summary"]),
            code=report["code"],
            hint=report["hint"],
            detail=report["detail"],
        )
        return 1

    try:
        base_dir = Path(script_dir)
        staging_dir = resolve_dir(config, "staging_dir", base_dir)
        works_dir = resolve_dir(config, "works_dir", base_dir)
        backup_dir = resolve_dir(config, "backup_dir", base_dir)
    except (KeyError, ValueError) as e:
        report = describe_exception(e)
        print_error_report(
            "設定値の解決に失敗しました",
            str(report["summary"]),
            code=report["code"],
            hint=report["hint"],
            detail=str(e),
        )
        return 1

    print(f"ステージング: {staging_dir}")
    print(f"本番        : {works_dir}")
    print(f"バックアップ: {backup_dir}")
    print("-" * 50)

    try:
        if args.check:
            ok = cmd_check(staging_dir)
            return 0 if ok else 1
        else:
            cmd_apply(staging_dir, works_dir, backup_dir)
            return 0
    finally:
        try:
            input("\nEnterキーを押すと終了します...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    sys.exit(main())
