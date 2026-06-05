from __future__ import annotations

import os
import sys

from build_works_from_csv import (
    Config,
    CSVDataClient,
    LauncherStructureGenerator,
    get_runtime_base_dir,
)
from cli_error import describe_exception, print_error_report


def main() -> int:
    """Driveマスター構造をステージングへコピーするメイン処理"""
    try:
        config = Config.from_file()
        data_client = CSVDataClient(config)
        generator = LauncherStructureGenerator(config, data_client)

        print("=" * 50)
        print("ランチャー構造コピー (Drive -> staging)")
        print("=" * 50)
        print(f"Driveマスター構造: {config.drive_master_dir}")
        print(f"出力先: {config.download_dir}")
        print("-" * 50)

        if generator.copy_drive_master_to_staging():
            print("✅ Driveマスター構造のコピーが完了しました")
            return 0

        print_error_report(
            "Driveマスター構造のコピーに失敗しました",
            "コピー処理が完了しませんでした。",
            code="COPY_FAILED",
            hint="Drive 側のフォルダ構成と権限を確認してから、もう一度実行してください。",
        )
        return 1

    except Exception as e:
        report = describe_exception(e)
        print_error_report(
            "Driveマスター構造のコピーに失敗しました",
            report.summary,
            code=report.code,
            hint=report.hint,
            detail=report.detail,
        )
        return 1

    finally:
        try:
            input("\nEnterキーを押すと終了します...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    os.chdir(str(get_runtime_base_dir()))
    sys.exit(main())
