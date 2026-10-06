import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest


def load_build_works_module():
    module_path = Path(__file__).resolve().parent.parent / "build_works_from_csv.py"
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location("build_works_from_csv_html", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_work(module, work_type="その他(.html)", **overrides):
    values = {
        "timestamp": "2026-01-01T00:00:00",
        "title": "Local HTML Work",
        "handle_name": "author",
        "full_name": "",
        "work_type": work_type,
        "genre": "Web",
        "description": "description",
        "qa": "",
        "credit": "",
        "external_materials": "",
        "license_check": "",
        "display_permission": "",
        "intro_permission": "",
        "thumbnail_check": "",
        "thumbnail_file": "",
        "thumbnail_url": "",
        "work_file": "",
        "work_url": "",
        "upload_check": "",
        "description_check": "",
        "walkthrough": "",
        "build_check": "",
        "control_type": "",
        "play_time": "",
        "executable_name": "",
        "remarks": "",
        "opinion": "",
        "extra_column": "",
        "priority": "",
        "skip_build": "1",
        "show_in_launcher": "1",
        "thumbnail_file_name": "",
        "work_file_name": "",
    }
    values.update(overrides)
    return module.WorkData(**values)


def make_generator(module, tmp_path):
    config = module.Config(
        download_dir=str(tmp_path / "out"),
        mirror_root_dir=str(tmp_path / "mirror"),
        column_mapping={},
    )
    data_client = module.CSVDataClient(config)
    return module.LauncherStructureGenerator(config, data_client)


@pytest.mark.parametrize("work_type", ["ゲーム(.html)", "その他(.html)"])
def test_html_form_types_use_local_html_processing(tmp_path, work_type):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)
    work = make_work(module, work_type=work_type)

    assert generator.determine_processing_type(work) == "local_html"
    assert generator.determine_work_type(work) == "html"


def test_prepare_local_html_zip_preserves_site_tree(tmp_path):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)
    archive = tmp_path / "site.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("demo/index.html", '<link rel="stylesheet" href="styles/main.css">')
        zip_file.writestr("demo/styles/main.css", "body { color: green; }")
        zip_file.writestr("demo/scripts/main.js", "document.body.dataset.ready = 'yes';")
        zip_file.writestr("demo/pages/about.html", "About")
        zip_file.writestr("demo/data/message.json", '{"message":"ok"}')

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    success, file_info = generator.prepare_local_html_sources(
        [str(archive)], work_dir, make_work(module)
    )

    assert success is True
    assert file_info == {
        "displayMode": "local-html",
        "htmlPath": "work_file/demo/index.html",
    }
    assert (work_dir / "work_file/demo/styles/main.css").read_text(encoding="utf-8")
    assert (work_dir / "work_file/demo/scripts/main.js").exists()
    assert (work_dir / "work_file/demo/pages/about.html").exists()
    assert (work_dir / "work_file/demo/data/message.json").exists()


def test_prepare_single_html_file(tmp_path):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)
    source = tmp_path / "作品.html"
    source.write_text("<!doctype html><title>作品</title>", encoding="utf-8")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    success, file_info = generator.prepare_local_html_sources(
        [str(source)], work_dir, make_work(module)
    )

    assert success is True
    assert file_info["htmlPath"] == "work_file/作品.html"
    assert (work_dir / "work_file/作品.html").exists()


def test_prepare_local_html_rejects_zip_slip(tmp_path):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("index.html", "safe")
        zip_file.writestr("../escape.txt", "unsafe")

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    success, file_info = generator.prepare_local_html_sources(
        [str(archive)], work_dir, make_work(module)
    )

    assert success is False
    assert file_info == {}
    assert not (tmp_path / "escape.txt").exists()
    assert not (work_dir / "work_file").exists()


def test_prepare_local_html_rejects_public_url(tmp_path):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    success, file_info = generator.prepare_local_html_sources(
        ["https://example.com/work"], work_dir, make_work(module)
    )

    assert success is False
    assert file_info == {}


def test_generate_local_html_config_contains_entry_and_boolean_visible(tmp_path):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)

    config_text = generator.generate_config_json5(
        make_work(module, work_type="ゲーム(.html)"),
        10,
        {
            "thumbnail": "thumbnail/thumb.svg",
            "visible": "True",
            "htmlPath": "work_file\\demo\\index.html",
            "sourceFingerprint": "abc123",
        },
    )
    config = json.loads(config_text)

    assert config["type"] == "html"
    assert config["displayMode"] == "local-html"
    assert config["htmlPath"] == "work_file/demo/index.html"
    assert config["visible"] is True
    assert config["buildSchemaVersion"] == 2
    assert config["sourceFingerprint"] == "abc123"


def test_process_works_builds_local_html_and_manifest(tmp_path):
    module = load_build_works_module()
    archive = tmp_path / "site.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("site/index.html", '<script type="module" src="scripts/app.js"></script>')
        zip_file.writestr("site/scripts/app.js", "document.body.dataset.ready = 'yes';")
    thumbnail = tmp_path / "thumb.svg"
    thumbnail.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("header\n", encoding="utf-8")

    config = module.Config(
        download_dir=str(tmp_path / "out"),
        csv_input_path=str(csv_path),
        mirror_root_dir=str(tmp_path),
        use_incremental_build=False,
        column_mapping={},
    )
    generator = module.LauncherStructureGenerator(config, module.CSVDataClient(config))
    work = make_work(
        module,
        thumbnail_file=str(thumbnail),
        work_file=str(archive),
        priority="7",
    )

    assert generator.process_works([work]) is True

    work_dir = tmp_path / "out/001-Local HTML Work"
    generated_config = json.loads((work_dir / "config.json5").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "out/manifest.json").read_text(encoding="utf-8"))
    assert generated_config["displayMode"] == "local-html"
    assert generated_config["htmlPath"] == "work_file/site/index.html"
    assert generated_config["visible"] is True
    assert (work_dir / "work_file/site/scripts/app.js").exists()
    assert "001-Local HTML Work/work_file/site/index.html" in manifest["files"]
    assert "001-Local HTML Work/work_file/site/scripts/app.js" in manifest["files"]
