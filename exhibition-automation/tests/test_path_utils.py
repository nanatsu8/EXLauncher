import importlib.util
from pathlib import Path


def load_path_utils():
    spec = importlib.util.spec_from_file_location(
        "path_utils",
        Path(__file__).resolve().parent.parent / "path_utils.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_japanese_suffix(tmp_path):
    pu = load_path_utils()

    # 構成: tmp/user/マイドライブ/ExhibitionLauncher を作る
    real = tmp_path / "user" / "マイドライブ" / "ExhibitionLauncher"
    real.mkdir(parents=True)

    # 存在しないが括弧付きのパスを作る
    raw = tmp_path / "user" / "マイドライブ（me@gmail.com）" / "ExhibitionLauncher"

    res = pu.normalize_drive_local_folder(raw)
    assert res == real


def test_normalize_english_suffix(tmp_path):
    pu = load_path_utils()

    real = tmp_path / "user" / "My Drive" / "ExhibitionLauncher"
    real.mkdir(parents=True)

    raw = tmp_path / "user" / "My Drive (me@gmail.com)" / "ExhibitionLauncher"

    res = pu.normalize_drive_local_folder(raw)
    assert res == real


def test_no_change_if_not_exist(tmp_path):
    pu = load_path_utils()

    raw = tmp_path / "user" / "SomeDrive (notreal)" / "ExhibitionLauncher"

    res = pu.normalize_drive_local_folder(raw)
    # 存在しない場合は元の Path を返す
    assert res == raw
