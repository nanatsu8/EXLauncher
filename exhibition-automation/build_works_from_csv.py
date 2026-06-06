from __future__ import annotations

import csv
import json
import os
import re
import shutil
import stat
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import json5
from cli_error import describe_exception, print_error_report
from path_utils import get_runtime_base_dir as _get_runtime_base_dir
from path_utils import resolve_config_path


def get_runtime_base_dir() -> Path:
    """スクリプト実行時/EXE実行時で共通の基準ディレクトリを返す"""
    return _get_runtime_base_dir(__file__)


@dataclass
class Config:
    download_dir: str
    csv_input_path: str = "data.csv"
    mirror_root_dir: str = "mirror"
    drive_master_dir: str = ""
    copy_exclude_names: Optional[List[str]] = None

    # 読み込み行範囲（CSVの行番号, 1-based, 閉区間）
    # None の場合は全行（ヘッダー行は自動で除外）
    start_row: Optional[int] = None
    end_row: Optional[int] = None

    # 作品タイプ判定
    exe_type_identifier: str = "ゲーム(.exe)"

    # デフォルト値
    default_thumbnail_path: str = "thumbnail/thumbnail.png"
    default_genre: str = "その他"

    # URL分割設定
    url_separator: str = ", "

    # Googleフォームのファイル回答サブフォルダ名
    thumbnail_subdir: str = "サムネイルファイル (File responses)"
    work_file_subdir: str = "作品ファイル (File responses)"

    # フォルダ/ファイル名設定
    thumbnail_folder_name: str = "thumbnail"
    work_file_folder_name: str = "work_file"
    config_file_name: str = "config.json5"
    temp_file_prefix: str = "temp"

    # 列マッピング設定
    column_mapping: Dict[str, int] = None

    @classmethod
    def from_file(cls, config_path: str = "config.json5") -> Config:
        """設定ファイルから Config インスタンスを作成"""
        try:
            base_dir = get_runtime_base_dir()
            cfg_path = Path(config_path)
            candidates: List[Path] = []
            if cfg_path.is_absolute():
                candidates.append(cfg_path)
            else:
                candidates.append((Path.cwd() / cfg_path).resolve())
                candidates.append((base_dir / cfg_path).resolve())

            existing_path = next((p for p in candidates if p.exists()), None)
            if existing_path is None:
                checked = "\n".join(str(p) for p in candidates)
                raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}\n探索先:\n{checked}")

            with open(existing_path, "r", encoding="utf-8") as f:
                config_data = json5.load(f)

            path_keys = ["download_dir", "csv_input_path", "mirror_root_dir", "drive_master_dir"]
            for key in path_keys:
                if key in config_data and config_data[key]:
                    resolved = resolve_config_path(base_dir, str(config_data[key]))
                    if resolved is not None:
                        config_data[key] = str(resolved)

            if "column_mapping" not in config_data:
                print_error_report(
                    "設定ファイルに列マッピングがありません",
                    "column_mapping の設定が不足しています。",
                    code="COLUMN_MAPPING_MISSING",
                    hint="config.json5 に 'column_mapping' セクションを追加してください。",
                )
                raise ValueError("column_mapping is required in config file")

            return cls(**{k: v for k, v in config_data.items() if k in cls.__dataclass_fields__})
        except FileNotFoundError as e:
            raise FileNotFoundError(str(e))
        except Exception as e:
            raise ValueError(f"設定ファイルの読み込みエラー: {e}")
        except TypeError as e:
            raise ValueError(f"設定ファイルに必要なフィールドが不足しています: {e}")


@dataclass
class WorkData:
    """作品データを表すクラス"""

    timestamp: str
    title: str
    handle_name: str
    full_name: str
    work_type: str
    genre: str
    description: str
    qa: str
    credit: str
    external_materials: str
    license_check: str
    display_permission: str
    intro_permission: str
    thumbnail_check: str
    thumbnail_file: str
    thumbnail_url: str
    work_file: str
    work_url: str
    upload_check: str
    description_check: str
    walkthrough: str
    build_check: str
    control_type: str
    play_time: str
    executable_name: str
    remarks: str
    opinion: str
    extra_column: str
    priority: str
    skip_build: str
    show_in_launcher: str
    thumbnail_file_name: str
    work_file_name: str


class CSVDataClient:
    """手動出力されたCSVから作品データを読み込むクライアント"""

    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    def parse_show_flag(value: str) -> bool:
        """show_in_launcher列(1/0)をブール値に変換"""
        normalized = (value or "").strip()
        if normalized == "1":
            return True
        if normalized in {"0", ""}:
            return False

        print(
            "警告: show_in_launcher は 1/0 で指定してください。"
            f" 値='{normalized}' は 0(非表示)として扱います。"
        )
        return False

    @staticmethod
    def parse_skip_build(value: str) -> bool:
        """skip_build列(1/0)を解釈し、ビルドするかどうかを返す"""
        normalized = (value or "").strip()
        if normalized == "0":
            return False
        if normalized in {"", "1"}:
            return True

        print(
            "警告: skip_build は 0/1 で指定してください。"
            f" 値='{normalized}' は 1(ビルド)として扱います。"
        )
        return True

    @staticmethod
    def parse_priority(value: str, fallback: int) -> int:
        """priority列を解釈し、表示順を返す（不正値は fallback を使用）"""
        normalized = (value or "").strip()
        if not normalized:
            return fallback
        try:
            parsed = int(normalized)
        except ValueError:
            print(
                "警告: priority は整数で指定してください。"
                f" 値='{normalized}' は {fallback} を使用します。"
            )
            return fallback

        # if parsed < 0:
        #     print(
        #         "警告: priority は 0 以上で指定してください。"
        #         f" 値='{normalized}' は {fallback} を使用します。"
        #     )
        #     return fallback

        return parsed

    def _safe_get(self, row: List[str], index: Optional[int]) -> str:
        if index is None or index < 0:
            return ""
        if index >= len(row):
            return ""
        return row[index]

    def _row_to_work_data(self, padded_row: List[str]) -> WorkData:
        cm = self.config.column_mapping
        return WorkData(
            timestamp=self._safe_get(padded_row, cm.get("timestamp")),
            title=self._safe_get(padded_row, cm.get("title")),
            handle_name=self._safe_get(padded_row, cm.get("handle_name")),
            full_name=self._safe_get(padded_row, cm.get("full_name")),
            work_type=self._safe_get(padded_row, cm.get("work_type")),
            genre=self._safe_get(padded_row, cm.get("genre")),
            description=self._safe_get(padded_row, cm.get("description")),
            qa=self._safe_get(padded_row, cm.get("qa")),
            credit=self._safe_get(padded_row, cm.get("credit")),
            external_materials=self._safe_get(padded_row, cm.get("external_materials")),
            license_check=self._safe_get(padded_row, cm.get("license_check")),
            display_permission=self._safe_get(padded_row, cm.get("display_permission")),
            intro_permission=self._safe_get(padded_row, cm.get("intro_permission")),
            thumbnail_check=self._safe_get(padded_row, cm.get("thumbnail_check")),
            thumbnail_file=self._safe_get(padded_row, cm.get("thumbnail_file")),
            thumbnail_url=self._safe_get(padded_row, cm.get("thumbnail_url")),
            work_file=self._safe_get(padded_row, cm.get("work_file")),
            work_url=self._safe_get(padded_row, cm.get("work_url")),
            upload_check=self._safe_get(padded_row, cm.get("upload_check")),
            description_check=self._safe_get(padded_row, cm.get("description_check")),
            walkthrough=self._safe_get(padded_row, cm.get("walkthrough")),
            build_check=self._safe_get(padded_row, cm.get("build_check")),
            control_type=self._safe_get(padded_row, cm.get("control_type")),
            play_time=self._safe_get(padded_row, cm.get("play_time")),
            executable_name=self._safe_get(padded_row, cm.get("executable_name")),
            remarks=self._safe_get(padded_row, cm.get("remarks")),
            opinion=self._safe_get(padded_row, cm.get("opinion")),
            extra_column=self._safe_get(padded_row, cm.get("extra_column")),
            priority=self._safe_get(padded_row, cm.get("priority")),
            skip_build=self._safe_get(padded_row, cm.get("skip_build")),
            show_in_launcher=self._safe_get(padded_row, cm.get("show_in_launcher")),
            thumbnail_file_name=self._safe_get(padded_row, cm.get("thumbnail_file_name")),
            work_file_name=self._safe_get(padded_row, cm.get("work_file_name")),
        )

    def get_csv_data(self) -> List[WorkData]:
        """CSVファイルからデータを取得してWorkDataリストに変換"""
        csv_path = Path(self.config.csv_input_path)
        if not csv_path.exists():
            print_error_report(
                "CSVファイルが見つかりません",
                "入力CSVが存在しません。",
                code="CSV_NOT_FOUND",
                hint="config.json5 の csv_input_path を確認してください。",
                detail=str(csv_path),
            )
            return []

        print(f"CSVを読み込みます: {csv_path}")
        works: List[WorkData] = []

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            for row_index, row in enumerate(reader, start=1):
                # 1行目はヘッダー想定
                if row_index == 1:
                    continue

                if self.config.start_row is not None and row_index < self.config.start_row:
                    continue
                if self.config.end_row is not None and row_index > self.config.end_row:
                    continue

                required_len = 0
                if self.config.column_mapping:
                    required_len = max(self.config.column_mapping.values()) + 1
                padded_row = row + [""] * max(required_len - len(row), 0)

                try:
                    work = self._row_to_work_data(padded_row)
                    works.append(work)
                    print(f"行 {row_index}: {work.title} を処理しました")
                except Exception as e:
                    report = describe_exception(e)
                    print_error_report(
                        f"行 {row_index} の処理でエラー",
                        report.summary,
                        code=report.code,
                        hint=report.hint,
                        detail=report.detail,
                    )

        print(f"取得完了: {len(works)} 件の作品データ")
        return works


class LauncherStructureGenerator:
    """ランチャー用フォルダ構造を生成するクラス"""

    def __init__(self, config: Config, data_client: CSVDataClient):
        self.config = config
        self.data_client = data_client
        self.download_dir = Path(config.download_dir)
        self.mirror_root_dir = Path(config.mirror_root_dir)
        # 手動作業リストを追跡
        self.manual_tasks = []

    @staticmethod
    def _remove_readonly_and_retry(func, path, _exc_info) -> None:
        """rmtree中に読み取り専用で失敗した場合に属性を解除して再試行する"""
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def _rmtree_with_retry(self, target: Path, retries: int = 8, delay_sec: float = 0.5) -> None:
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                shutil.rmtree(target, onerror=self._remove_readonly_and_retry)
                return
            except OSError as e:
                last_error = e
                if getattr(e, "winerror", None) in {5, 32} and attempt < retries:
                    time.sleep(delay_sec)
                    continue
                raise
        if last_error:
            raise last_error

    def _copy_with_retry(
        self,
        source: Path,
        destination: Path,
        ignore_entries,
        retries: int = 8,
        delay_sec: float = 0.5,
    ) -> None:
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                if source.is_dir():
                    shutil.copytree(source, destination, ignore=ignore_entries)
                else:
                    shutil.copy2(source, destination)
                return
            except OSError as e:
                last_error = e
                if getattr(e, "winerror", None) in {5, 32} and attempt < retries:
                    time.sleep(delay_sec)
                    continue
                raise
        if last_error:
            raise last_error

    def copy_drive_master_to_staging(self) -> bool:
        """Driveミラー上の works 構造をステージングへそのままコピーする"""
        raw_source = (self.config.drive_master_dir or "").strip()
        if not raw_source:
            print_error_report(
                "Driveマスター構造のコピーに失敗しました",
                "drive_master_dir が未設定です。",
                code="DRIVE_MASTER_DIR_NOT_SET",
                hint="config.json5 の drive_master_dir を設定してから、もう一度実行してください。",
            )
            return False

        source_dir = Path(raw_source)
        if not source_dir.is_absolute():
            source_dir = (Path.cwd() / source_dir).resolve()

        try:
            source_resolved = source_dir.resolve()
            target_resolved = self.download_dir.resolve()
        except Exception as e:
            report = describe_exception(e)
            print_error_report(
                "Driveマスター構造のコピーに失敗しました",
                report.summary,
                code=report.code,
                hint=report.hint,
                detail=report.detail,
            )
            return False

        if source_resolved == target_resolved:
            print_error_report(
                "Driveマスター構造のコピーに失敗しました",
                "drive_master_dir と download_dir が同一です。",
                code="SAME_SOURCE_AND_DESTINATION",
                hint="Drive 側の出力先とコピー元を別のフォルダにしてください。",
                detail=str(source_resolved),
            )
            return False

        if not source_resolved.exists() or not source_resolved.is_dir():
            print_error_report(
                "Driveマスター構造のコピーに失敗しました",
                "Drive マスター構造が見つかりません。",
                code="SOURCE_NOT_FOUND",
                hint="drive_master_dir の場所とフォルダ構成を確認してください。",
                detail=str(source_resolved),
            )
            return False

        exclude_names = {"desktop.ini"}
        if self.config.copy_exclude_names:
            exclude_names.update(name.lower() for name in self.config.copy_exclude_names)

        def ignore_entries(_dir: str, names: List[str]) -> List[str]:
            return [name for name in names if name.lower() in exclude_names]

        try:
            if self.download_dir.exists():
                self._rmtree_with_retry(self.download_dir)
            self.download_dir.mkdir(parents=True, exist_ok=True)

            print(f"Driveマスター構造をコピーしています: {source_resolved}")
            for entry in source_resolved.iterdir():
                if entry.name.lower() in exclude_names:
                    continue

                destination = self.download_dir / entry.name
                self._copy_with_retry(entry, destination, ignore_entries)

            self.write_manifest()
            print("✅ Driveマスター構造のコピーが完了しました")
            print(f"出力先: {self.download_dir}")
            return True
        except Exception as e:
            report = describe_exception(e)
            print_error_report(
                "Driveマスター構造のコピーに失敗しました",
                report.summary,
                code=report.code,
                hint=report.hint,
                detail=report.detail,
            )
            return False

    def sanitize_filename(self, filename: str) -> str:
        """ファイル・フォルダ名に使用できない文字を置換"""
        # Windowsで使用できない文字を置換
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, "_", filename)
        # 末尾の空白やピリオドを削除
        sanitized = sanitized.strip(" .")
        return sanitized

    def generate_folder_name(self, index: int, title: str) -> str:
        """フォルダ名を生成（001-作品名の形式）"""
        sanitized_title = self.sanitize_filename(title)
        return f"{index:03d}-{sanitized_title}"

    def determine_work_type(self, work: WorkData) -> str:
        """作品タイプを判定"""
        if work.work_type == self.config.exe_type_identifier:
            return "exe"
        else:
            return "html"

    def split_values(self, raw_value: str) -> List[str]:
        """区切り文字で分割して空要素を除外"""
        if not raw_value:
            return []
        return [v.strip() for v in raw_value.split(self.config.url_separator) if v.strip()]

    def resolve_source_path(self, raw_path: str) -> Optional[Path]:
        """CSVのパス文字列を実在パスへ解決"""
        cleaned = (raw_path or "").strip().strip('"').strip("'")
        if not cleaned:
            return None

        source = Path(cleaned)
        candidates = []

        if source.is_absolute():
            candidates.append(source)
        else:
            candidates.append((Path.cwd() / source).resolve())
            candidates.append((self.mirror_root_dir / source).resolve())

        for candidate in candidates:
            if candidate.exists():
                return candidate

        # ファイル名だけが指定されるケース向けのフォールバック探索
        if self.mirror_root_dir.exists() and source.name:
            matches = list(self.mirror_root_dir.rglob(source.name))
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                print(f"警告: {source.name} が複数見つかりました。" f" 先頭を採用します: {matches[0]}")
                return matches[0]

        return None

    def _cleanup_extraneous_work_files(self, work_dir: Path) -> None:
        """ZIP展開後、work_file 以外の作品ファイルや zip を削除する"""
        preserve_names = {
            self.config.config_file_name,
            self.config.thumbnail_folder_name,
            self.config.work_file_folder_name,
        }

        for item in work_dir.iterdir():
            if item.name in preserve_names or item.name.startswith("."):
                continue

            try:
                if item.is_dir():
                    self._rmtree_with_retry(item)
                else:
                    item.unlink()
                print(f"不要ファイルを削除: {item.name}")
            except Exception as e:
                print(f"削除失敗: {item} ({e})")

    def _extract_zip_file(self, zip_path: Path) -> bool:
        """ZIPファイルを展開"""
        try:
            work_dir = zip_path.parent
            extract_dir = work_dir / self.config.work_file_folder_name
            extract_dir.mkdir(exist_ok=True)

            print(f"ZIPファイルを展開中: {zip_path.name}")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            print(f"展開完了: {extract_dir}")
            self._cleanup_extraneous_work_files(work_dir)
            return True
        except zipfile.BadZipFile:
            print(f"エラー: {zip_path} は無効なZIPファイルです")
            return False
        except Exception as e:
            print(f"ZIP展開エラー: {e}")
            return False

    def copy_sources(
        self, source_values: List[str], target_dir: Path, task_type: str, work: WorkData
    ) -> bool:
        """CSVで指定されたソースを target_dir 配下へコピー"""
        if not source_values:
            return False

        success_count = 0
        for raw_value in source_values:
            source_path = self.resolve_source_path(raw_value)
            if not source_path:
                self.manual_tasks.append(
                    {
                        "type": task_type,
                        "work_title": work.title,
                        "source": raw_value,
                        "save_path": str(target_dir),
                    }
                )
                print(f"警告: ソースが見つかりません: {raw_value}")
                continue

            target_dir.mkdir(parents=True, exist_ok=True)
            destination = target_dir / source_path.name

            try:
                if source_path.is_dir():
                    shutil.copytree(source_path, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(source_path, destination)
                    if destination.suffix.lower() == ".zip":
                        self._extract_zip_file(destination)

                success_count += 1
                print(f"コピー完了: {source_path} -> {destination}")
            except Exception as e:
                print(f"コピー失敗: {source_path} ({e})")

        return success_count == len(source_values)

    def extract_and_organize_files(self, work_dir: Path, work: WorkData) -> Dict[str, str]:
        """コピーしたファイルを適切に配置し、設定情報を返す"""
        # 作品ファイルを探す（thumbnailフォルダ、config.json5を除外）
        all_files = list(work_dir.glob("*"))
        work_files = [
            f
            for f in all_files
            if f.name not in [self.config.config_file_name, self.config.thumbnail_folder_name]
            and not f.name.startswith(".")
        ]

        # 作品ファイルが存在しない場合
        if not work_files:
            print(f"警告: {work.title} に作品ファイルが見つかりません")
            return {}

        work_type = self.determine_work_type(work)

        if work_type == "exe":
            return self._handle_exe_file(work_dir, work, work_files)
        else:
            return self._handle_media_file(work_dir, work)

    def _handle_exe_file(self, work_dir: Path, work: WorkData, work_files: List[Path]) -> Dict[str, str]:
        """EXEファイル（ゲーム）の処理"""
        # ZIP展開済みフォルダまたは直接配置されたEXEを探索

        if not work_files:
            print(f"警告: {work.title} に作品ファイルが見つかりません")
            return {}

        # EXEファイルを直接探す
        exe_files = [f for f in work_files if f.suffix.lower() == ".exe"]
        if exe_files:
            # EXEファイルが直接ある場合（元のファイル名を保持）
            original_name = exe_files[0].name
            return {"executablePath": original_name}

        # フォルダがある場合、その中のEXEファイルを探す
        for work_file_path in work_files:
            if work_file_path.is_dir():
                exe_files = list(work_file_path.rglob("*.exe"))
                if exe_files:
                    # 実行ファイル名が指定されている場合はそれを優先
                    if work.executable_name:
                        target_exe = None
                        for exe_file in exe_files:
                            if exe_file.name == work.executable_name:
                                target_exe = exe_file
                                break
                        if target_exe:
                            executable_path = str(target_exe.relative_to(work_dir)).replace("\\", "/")
                        else:
                            executable_path = str(exe_files[0].relative_to(work_dir)).replace("\\", "/")
                    else:
                        executable_path = str(exe_files[0].relative_to(work_dir)).replace("\\", "/")

                    return {"executablePath": executable_path}

        # EXEファイルが見つからない場合
        print(f"警告: {work.title} に実行ファイルが見つかりません")
        return {}

    def _handle_media_file(self, work_dir: Path, work: WorkData) -> Dict[str, str]:
        """メディアファイル（映像作品等）の処理"""
        # コピー済みファイルを探す（thumbnailフォルダ、config.json5を除外）
        all_files = list(work_dir.glob("*"))
        work_files = [
            f
            for f in all_files
            if f.name not in [self.config.config_file_name, self.config.thumbnail_folder_name]
            and not f.name.startswith(".")
        ]

        if not work_files:
            print(f"警告: {work.title} に作品ファイルが見つかりません")
            return {}

        # 結果を格納する辞書
        result = {}
        movie_paths = []
        image_paths = []

        # サムネイルファイルを探してImagePathsに追加
        thumbnail_dir = work_dir / self.config.thumbnail_folder_name
        if thumbnail_dir.exists():
            thumbnail_files = list(thumbnail_dir.glob("thumbnail*"))
            if thumbnail_files:
                image_paths.append(f"{self.config.thumbnail_folder_name}/{thumbnail_files[0].name}")

        # 作品ファイルとして展開されたすべてのファイルを処理
        processed_files = []

        for work_file_path in work_files:
            if work_file_path.is_dir():
                # フォルダの場合、中身のファイルをすべて処理
                for file_path in work_file_path.rglob("*"):
                    if file_path.is_file():
                        processed_files.append(file_path)
            else:
                # 単一ファイルの場合
                processed_files.append(work_file_path)

        # ファイルを拡張子別に分類して処理（元のファイル名を保持）
        for file_path in processed_files:
            original_suffix = file_path.suffix.lower()
            original_name = file_path.name

            if original_suffix in [".mp4", ".mov", ".avi", ".mkv"]:
                # 動画ファイルの処理（元のファイル名を保持）
                target_path = work_dir / original_name

                # 移動先に同名ファイルがないか確認
                if target_path.exists():
                    print(f"スキップ: {original_name} は既に存在します")
                    movie_paths.append(original_name)
                else:
                    file_path.rename(target_path)
                    movie_paths.append(original_name)

            elif original_suffix in [".jpg", ".jpeg", ".png", ".gif"]:
                # 画像ファイルの処理（サムネイル以外、元のファイル名を保持）
                # thumbnailフォルダ内のファイルはスキップ
                if not str(file_path).endswith(
                    ("thumbnail", "thumbnail.png", "thumbnail.jpg", "thumbnail.jpeg", "thumbnail.gif")
                ) and "thumbnail" not in str(file_path.parent):
                    target_path = work_dir / original_name

                    # 移動先に同名ファイルがないか確認
                    if target_path.exists():
                        print(f"スキップ: {original_name} は既に存在します")
                        image_paths.append(original_name)
                    else:
                        file_path.rename(target_path)
                        image_paths.append(original_name)

            else:
                # その他のファイル形式（元のファイル名を保持）
                target_path = work_dir / original_name

                # 移動先に同名ファイルがないか確認
                if target_path.exists():
                    print(f"スキップ: {original_name} は既に存在します")
                    result["htmlPath"] = original_name
                else:
                    file_path.rename(target_path)
                    result["htmlPath"] = original_name

        # 結果を設定
        if movie_paths:
            result["MoviePaths"] = movie_paths
        if image_paths:
            result["ImagePaths"] = image_paths

        # 元のwork_fileフォルダが空になったら削除
        for work_file_path in work_files:
            if work_file_path.is_dir() and not any(work_file_path.iterdir()):
                work_file_path.rmdir()

        return result

    def generate_config_json5(self, work: WorkData, priority: int, file_info: Dict[str, str]) -> str:
        """config.json5の内容を生成"""
        work_type = self.determine_work_type(work)

        config = {
            "title": work.title,
            "description": work.description.replace("\n", "\\n"),
            "priority": priority,
            "type": work_type,
            "thumbnail": file_info.get("thumbnail", self.config.default_thumbnail_path),
            "author": work.handle_name,
            "genre": work.genre or self.config.default_genre,
            "credit": work.credit.replace("\n", "\\n") if work.credit else "",
            "visible": file_info.get("visible", False),
        }

        # 作品タイプに応じた追加設定
        if work_type == "exe":
            if "executablePath" in file_info:
                config["executablePath"] = file_info["executablePath"]
            if work.control_type:
                config["operation"] = work.control_type
            if work.play_time:
                config["estimatedPlayTime"] = work.play_time
        else:
            if "MoviePaths" in file_info:
                config["MoviePaths"] = file_info["MoviePaths"]
            if "ImagePaths" in file_info:
                config["ImagePaths"] = file_info["ImagePaths"]
            if work.play_time:
                config["duration"] = work.play_time

        # パス区切り文字の変換とデータ型の正規化
        normalized_config = {}
        for key, value in config.items():
            if isinstance(value, str):
                # パスのみスラッシュに変換（改行文字は保護）
                if key in ["executablePath", "htmlPath", "thumbnail"] or key.endswith("Path"):
                    value = value.replace("\\", "/")
                normalized_config[key] = value
            elif isinstance(value, list):
                # リスト内の文字列もパス区切り文字を変換（パス関連のキーのみ）
                if key in ["MoviePaths", "ImagePaths"] or key.endswith("Paths"):
                    value = [item.replace("\\", "/") if isinstance(item, str) else item for item in value]
                normalized_config[key] = value
            else:
                normalized_config[key] = value

        # JSON5形式で出力
        return json.dumps(normalized_config, indent=4, ensure_ascii=False)

    def process_works(self, works: List[WorkData]) -> bool:
        """作品データを処理してランチャー構造を生成"""
        try:
            # ダウンロードディレクトリを作成
            self.download_dir.mkdir(parents=True, exist_ok=True)

            success_count = 0
            total_count = len(works)

            # タイムスタンプ順でソート
            works_sorted = sorted(works, key=lambda x: x.timestamp)

            # 開始行番号を計算
            # start_row が None または 2 以下の時は 1 から開始
            # それ以外は start_row - 1 から開始
            if self.config.start_row is None or self.config.start_row <= 2:
                base_index = 1
            else:
                base_index = self.config.start_row - 1

            for index, work in enumerate(works_sorted, 1):
                print(f"\n処理中 ({index}/{total_count}): {work.title}")

                # 実際の行番号に対応するインデックスを計算
                actual_index = base_index + index - 1

                # skip_build=0 の行は完全にスキップ（フォルダ未生成）
                if not self.data_client.parse_skip_build(work.skip_build):
                    print(f"情報: skip_build=0 のためスキップします ({work.title})")
                    continue

                # フォルダ名を生成
                folder_name = self.generate_folder_name(actual_index, work.title)
                work_dir = self.download_dir / folder_name
                work_dir.mkdir(exist_ok=True)

                if work.thumbnail_file_name.strip():
                    thumb_path = (
                        self.mirror_root_dir
                        / self.config.thumbnail_subdir
                        / work.thumbnail_file_name.strip()
                    )
                    thumbnail_values = [str(thumb_path)]
                else:
                    thumbnail_values = self.split_values(work.thumbnail_file) or self.split_values(
                        work.thumbnail_url
                    )
                thumbnail_dir = work_dir / self.config.thumbnail_folder_name
                thumbnail_success = self.copy_sources(thumbnail_values, thumbnail_dir, "サムネイル", work)
                thumbnail_filename = self.config.default_thumbnail_path
                if thumbnail_success:
                    files = list(thumbnail_dir.glob("*"))
                    if files:
                        thumbnail_filename = f"{self.config.thumbnail_folder_name}/{files[0].name}"

                if work.work_file_name.strip():
                    work_path = (
                        self.mirror_root_dir / self.config.work_file_subdir / work.work_file_name.strip()
                    )
                    work_file_values = [str(work_path)]
                else:
                    work_file_values = self.split_values(work.work_file) or self.split_values(work.work_url)
                work_file_success = self.copy_sources(work_file_values, work_dir, "作品ファイル", work)

                # ファイルを適切に配置（既存ファイルがある場合も情報を取得）
                file_info = {}

                # 作品ファイルが存在する場合（新規ダウンロード or 既存ファイル）
                all_files = list(work_dir.glob("*"))
                work_files = [
                    f
                    for f in all_files
                    if f.name not in [self.config.config_file_name]
                    and not f.name.startswith(self.config.thumbnail_folder_name)
                    and f.name != self.config.thumbnail_folder_name
                ]

                # thumbnailフォルダは除外
                work_files = [f for f in work_files if f.name != self.config.thumbnail_folder_name]

                if work_files or work_file_success:
                    file_info = self.extract_and_organize_files(work_dir, work)

                # サムネイル情報を追加
                if thumbnail_filename:
                    file_info["thumbnail"] = thumbnail_filename

                should_show = self.data_client.parse_show_flag(work.show_in_launcher)
                if not should_show:
                    print(f"情報: show_in_launcher=0 のため非表示として生成します ({work.title})")

                # visible状態を追加（show_in_launcher=1 かつ必要ファイルが揃う場合のみ true）
                file_info["visible"] = should_show and thumbnail_success and work_file_success

                priority_value = self.data_client.parse_priority(work.priority, actual_index)

                # config.json5を生成（毎回更新）
                config_path = work_dir / self.config.config_file_name
                config_content = self.generate_config_json5(work, priority_value, file_info)
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(config_content)
                print(f"config.json5を更新: {config_path.name}")

                if file_info["visible"]:
                    success_count += 1
                    print(f"✅ 完了: {work.title}")
                else:
                    print(f"⚠️  部分的に完了: {work.title}")

            # 手動タスクのサマリーを表示
            self.show_manual_tasks_summary()

            # ファイル名未入力の行がある場合、シート貼り付け用一覧を出力
            self.show_file_name_hints(works)

            # ステージング内のマニフェストを生成
            self.write_manifest()

            print(f"\n" + "=" * 50)
            print(f"処理完了: {success_count}/{total_count} 作品を正常に処理")
            print(f"出力先: {self.download_dir}")

            return success_count > 0

        except Exception as e:
            print(f"処理エラー: {e}")
            return False

    def write_manifest(self) -> None:
        """ステージング内のファイル一覧とSHA-256ハッシュをmanifest.jsonに保存"""
        import hashlib
        from datetime import datetime

        print("マニフェストを生成しています。しばらくお待ちください...")
        files: Dict[str, str] = {}
        manifest_name = "manifest.json"
        for file_path in sorted(self.download_dir.rglob("*")):
            if file_path.is_file() and file_path.name != manifest_name:
                rel = file_path.relative_to(self.download_dir).as_posix()
                sha256 = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        sha256.update(chunk)
                files[rel] = sha256.hexdigest()

        manifest = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "file_count": len(files),
            "files": files,
        }
        manifest_path = self.download_dir / manifest_name
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"✅ manifest.json を出力しました: {manifest_path}  ({len(files)} ファイル)")

    def show_manual_tasks_summary(self):
        """手動タスクのサマリーを表示"""
        if not self.manual_tasks:
            print("\n✅ すべてのファイル参照が解決しました。追加の手動作業は不要です。")
            return

        print("\n" + "=" * 60)
        print("📋 手動作業が必要なタスク一覧")
        print("=" * 60)

        # タスクタイプ別に分類
        tasks_by_type = {}
        for task in self.manual_tasks:
            task_type = task["type"]
            if task_type not in tasks_by_type:
                tasks_by_type[task_type] = []
            tasks_by_type[task_type].append(task)

        task_count = 0
        for task_type, tasks in tasks_by_type.items():
            print(f"\n【{task_type}】({len(tasks)}件)")
            for task in tasks:
                task_count += 1
                print(f"  {task_count}. 作品: {task['work_title']}")
                print(f"     参照値: {task['source']}")
                print(f"     保存先: {task['save_path']}")
                print()

        print(f"合計 {task_count} 件の手動作業が必要です。")
        print("作業手順:")
        print("1. 参照値に対応するファイルを mirror_root_dir 配下へ配置してください。")
        print("2. 必要に応じて保存先へ手動コピーしてください。")
        print(
            "3. config.json5 の MoviePaths または ImagePaths にファイル名を追加してください。(詳細は他フォルダの config.json5 を参考にしてください)"
        )
        print("4. show_in_launcher を 1 にした作品のみ visible=true になります。")
        print("5. ランチャーで作品が正しく表示されることを確認してください。")

    def show_file_name_hints(self, works: List[WorkData]) -> None:
        """シート行に対応した貼り付け用の file_name 列を出力する"""

        def normalize_key(value: str) -> str:
            return re.sub(r"\s+", " ", (value or "").strip())

        def is_upload_enabled(value: str) -> bool:
            return (value or "").strip() == "はい"

        def is_show_enabled(value: str) -> bool:
            return (value or "").strip() == "1"

        def list_files_sorted(subdir: str) -> List[str]:
            """サブフォルダ内のファイルを更新日時昇順で返す"""
            target = self.mirror_root_dir / subdir
            if not target.exists():
                print(f"警告: フォルダが見つかりません: {target}")
                return []

            files = [
                file_path
                for file_path in target.iterdir()
                if file_path.is_file() and file_path.name.lower() != "desktop.ini"
            ]
            files.sort(key=lambda file_path: file_path.stat().st_mtime)
            return [file_path.name for file_path in files]

        def build_lines(
            source_names: List[str],
            existing_attr: str,
            should_output_blank,
        ) -> List[str]:
            name_by_title: Dict[str, str] = {}
            used_names = set()

            for work in works:
                if should_output_blank(work):
                    continue

                title_key = normalize_key(work.title)
                existing_name = getattr(work, existing_attr).strip()
                if not existing_name:
                    continue

                used_names.add(existing_name)
                if title_key and title_key not in name_by_title:
                    name_by_title[title_key] = existing_name

            available_names = [name for name in source_names if name not in used_names]
            next_index = 0
            lines: List[str] = []

            for work in works:
                if should_output_blank(work):
                    lines.append("")
                    continue

                title_key = normalize_key(work.title)
                existing_name = getattr(work, existing_attr).strip()
                if existing_name:
                    value = existing_name
                    if title_key and title_key not in name_by_title:
                        name_by_title[title_key] = value
                elif title_key and title_key in name_by_title:
                    value = name_by_title[title_key]
                elif next_index < len(available_names):
                    value = available_names[next_index]
                    next_index += 1
                    if title_key:
                        name_by_title[title_key] = value
                else:
                    value = ""

                lines.append(value)

            return lines

        need_thumb = any(not work.thumbnail_file_name.strip() for work in works)
        need_work = any(
            not work.work_file_name.strip()
            and not (
                not is_upload_enabled(work.upload_check) and not is_show_enabled(work.show_in_launcher)
            )
            for work in works
        )

        if not need_thumb and not need_work:
            return

        # ファイル名未入力の行がある場合、シート貼り付け用の一覧を出力
        # 現在は性能がよくないためコメントアウト中
        """
        print("\n" + "=" * 60)
        print("📄 ファイル名未入力の行があります。以下をシートに貼り付けてください。")
        print("=" * 60)

        if need_thumb:
            thumbnail_lines = build_lines(
                list_files_sorted(self.config.thumbnail_subdir),
                "thumbnail_file_name",
                lambda work: False,
            )
            missing_count = sum(1 for line in thumbnail_lines if not line.strip())
            print(f"\n--- AD列: thumbnail_file_name ({len(thumbnail_lines)} 行 / 更新日時昇順ベース) ---")
            for line in thumbnail_lines:
                print(line)
            if missing_count:
                print(f"警告: thumbnail_file_name を割り当てられない行が {missing_count} 件あります。")

        if need_work:
            work_lines = build_lines(
                list_files_sorted(self.config.work_file_subdir),
                "work_file_name",
                lambda work: not is_upload_enabled(work.upload_check),
            )
            unresolved_count = sum(
                1
                for work, line in zip(works, work_lines)
                if is_upload_enabled(work.upload_check) and not line.strip()
            )
            print(f"\n--- AE列: work_file_name ({len(work_lines)} 行 / 更新日時昇順ベース) ---")
            for line in work_lines:
                print(line)
            if unresolved_count:
                print(f"警告: work_file_name を割り当てられない行が {unresolved_count} 件あります。")

        print("\n" + "=" * 60)
        """


def main():
    """CSVからランチャー構造を生成するメイン処理"""
    try:
        # 設定読み込み
        config = Config.from_file()

        # CSVクライアント初期化
        data_client = CSVDataClient(config)

        # ランチャー構造生成器初期化
        generator = LauncherStructureGenerator(config, data_client)

        print("=" * 50)
        print("ランチャー構造生成 (CSV)")
        print("=" * 50)
        print(f"CSV入力: {config.csv_input_path}")
        print(f"ミラー参照ルート: {config.mirror_root_dir}")
        print(f"出力先: {config.download_dir}")
        print("-" * 50)

        # CSVからデータ取得
        works = data_client.get_csv_data()

        if not works:
            print_error_report(
                "データが取得できませんでした",
                "CSV から有効な作品データを取得できませんでした。",
                code="NO_DATA",
                hint="CSV と column_mapping の内容を見直してから、もう一度実行してください。",
            )
            return 1

        # ランチャー構造を生成
        if generator.process_works(works):
            print("✅ ランチャー構造の生成が完了しました")
            return 0
        else:
            print_error_report(
                "ランチャー構造の生成に失敗しました",
                "処理は最後まで完了しませんでした。",
                code="GENERATE_FAILED",
                hint="表示された警告やエラーを確認してから、もう一度実行してください。",
            )
            return 1

    except Exception as e:
        report = describe_exception(e)
        print_error_report(
            "ランチャー構造の生成に失敗しました",
            report.summary,
            code=report.code,
            hint=report.hint,
            detail=report.detail,
        )
        return 1

    finally:
        # PyInstaller用：処理完了後にウィンドウを開いたままにする
        try:
            input("\nEnterキーを押すと終了します...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    os.chdir(str(get_runtime_base_dir()))
    sys.exit(main())
