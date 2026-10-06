import importlib.util
import sys
from pathlib import Path


def load_build_works_module():
    module_path = Path(__file__).resolve().parent.parent / "build_works_from_csv.py"
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location("build_works_from_csv", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_work(module, **overrides):
    values = {
        "timestamp": "2026-01-01T00:00:00",
        "title": "PDF Work",
        "handle_name": "author",
        "full_name": "",
        "work_type": "映像作品",
        "genre": "資料",
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
        "skip_build": "",
        "show_in_launcher": "1",
        "thumbnail_file_name": "",
        "work_file_name": "",
    }
    values.update(overrides)
    return module.WorkData(**values)


def make_generator(module, tmp_path):
    config = module.Config(download_dir=str(tmp_path / "out"), column_mapping={})
    data_client = module.CSVDataClient(config)
    return module.LauncherStructureGenerator(config, data_client)


def test_handle_media_file_collects_pdf_paths(tmp_path):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)
    work_dir = tmp_path / "work"
    nested_dir = work_dir / "work_file"
    nested_dir.mkdir(parents=True)
    (nested_dir / "book.pdf").write_bytes(b"%PDF-1.4\n")

    result = generator._handle_media_file(work_dir, make_work(module))

    assert result["PdfPaths"] == ["book.pdf"]
    assert (work_dir / "book.pdf").exists()
    assert not nested_dir.exists()


def test_handle_media_file_keeps_existing_media_classification(tmp_path):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "movie.mp4").write_bytes(b"movie")
    (work_dir / "image.png").write_bytes(b"image")
    (work_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    result = generator._handle_media_file(work_dir, make_work(module))

    assert result["MoviePaths"] == ["movie.mp4"]
    assert result["ImagePaths"] == ["image.png"]
    assert "htmlPath" not in result


def test_generate_config_json5_outputs_pdf_paths(tmp_path):
    module = load_build_works_module()
    generator = make_generator(module, tmp_path)

    config_text = generator.generate_config_json5(
        make_work(module),
        1,
        {"thumbnail": "thumbnail/thumbnail.png", "visible": "True", "PdfPaths": ["docs\\book.pdf"]},
    )

    assert '"type": "html"' in config_text
    assert '"PdfPaths": [' in config_text
    assert '"docs/book.pdf"' in config_text
