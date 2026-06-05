from __future__ import annotations

import sys
from pathlib import Path

RUNTIME_PATH_ERROR_MESSAGE = (
    "実行ファイル（またはスクリプト）の配置先が C:/Users/{user_name}/... ではないため実行できません"
)


def get_runtime_base_dir(caller_file: str | None = None) -> Path:
    """スクリプト実行時/EXE実行時で共通の基準ディレクトリを返す。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    if caller_file:
        return Path(caller_file).resolve().parent
    return Path(__file__).resolve().parent


def extract_user_name_from_base_dir(base_dir: Path) -> str:
    """C:/Users/{user_name}/... 形式のパスから user_name を抽出する。"""
    resolved = base_dir.resolve()
    parts = resolved.parts

    if len(parts) < 3:
        raise ValueError(f"{RUNTIME_PATH_ERROR_MESSAGE}: {resolved}")

    drive = parts[0].rstrip("\\/").lower()
    users = parts[1].lower()
    user_name = parts[2].strip()

    if drive != "c:" or users != "users" or not user_name:
        raise ValueError(f"{RUNTIME_PATH_ERROR_MESSAGE}: {resolved}")

    return user_name


def format_user_placeholders(raw_path: str, user_name: str) -> str:
    """{user_name} を str.format() で置換し、未知プレースホルダを検出する。"""
    try:
        return raw_path.format(user_name=user_name)
    except KeyError as e:
        placeholder = e.args[0]
        raise ValueError(f"未対応プレースホルダ '{{{placeholder}}}' が見つかりました: {raw_path}") from e
    except ValueError as e:
        raise ValueError(f"プレースホルダ置換に失敗しました: {raw_path} ({e})") from e


def resolve_config_path(base_dir: Path, raw_path: str | None) -> Path | None:
    """config 文字列パスを user_name 置換後に絶対パスへ解決する。"""
    if raw_path is None:
        return None

    trimmed = str(raw_path).strip()
    if not trimmed:
        return None

    user_name = extract_user_name_from_base_dir(base_dir)
    formatted = format_user_placeholders(trimmed, user_name)
    path = Path(formatted)

    # 絶対パス/相対パスいずれでも、まず存在する実パスの候補を試す。
    if path.is_absolute():
        return normalize_drive_local_folder(path)

    resolved = (base_dir / path).resolve()
    return normalize_drive_local_folder(resolved)


def normalize_drive_local_folder(raw_path: Path) -> Path:
    """
    Google Drive のローカル同期フォルダ名の揺れに対応するための補助関数。

    挙動:
    - raw_path が既に存在すればそのまま返す。
    - 存在しない場合、フォルダ名に付くアカウントサフィックス（例: マイドライブ（a@b）やMy Drive (a@b)）を
      削除した候補を作成して存在チェックし、存在するものがあれば返す。
    - どれも存在しなければ元の raw_path を返す（破壊的変更を避ける）。

    これは非破壊的なフォールバックであり、将来的により詳細な環境検出ロジックに置き換え可能です。
    """
    try:
        # 既に存在するならそのまま
        if raw_path.exists():
            return raw_path

        # パーツごとに "マイドライブ(アドレス)" や "My Drive (addr)" を検出し、括弧を取り除いた候補を試す
        import re

        drive_part = raw_path.parts[0] if raw_path.parts else ""
        parts = list(raw_path.parts)

        # 英語表記や余分な空白のバリエーションを許容する
        pattern = re.compile(r"^(?P<base>マイドライブ|My Drive)\s*(?:[（(].+?[）)])?$", flags=re.I)

        # Windows のドライブレター部 (例: 'C:\') を含むことを想定して先頭から走査
        for i in range(len(parts)):
            part = parts[i]
            m = pattern.match(part.strip())
            if not m:
                continue

            new_part = m.group("base")

            # candidate を組み立て
            cand = Path(parts[0])
            for j in range(1, len(parts)):
                if j == i:
                    cand = cand / new_part
                else:
                    cand = cand / parts[j]

            if cand.exists():
                return cand

        # 上の単純候補で見つからなければ、さらにパス文字列全体から括弧付きサフィックスを1回だけ取り除いて試す
        s = str(raw_path)
        s2 = re.sub(r"([\u3000-\u303F\w\s\-]+?)[（\(].+?[）\)]", r"\1", s, count=1)
        if s2 != s:
            cand2 = Path(s2)
            if cand2.exists():
                return cand2

    except Exception:
        # 正規化は補助的処理なので失敗してもフォールバックする
        pass

    return raw_path
