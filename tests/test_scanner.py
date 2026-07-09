"""
Tests for scan_project_folder(): the folder auto-detection heuristics used
by both the GUI ("Folder auto-detect") and the CLI (`venv-bat-gen scan`).
"""

from __future__ import annotations

from venv_bat_gen.core import scan_project_folder


class TestVenvDetection:
    def test_no_venv_reports_not_found(self, tmp_path):
        scan = scan_project_folder(tmp_path)
        assert scan.venv_found is False
        assert scan.venv_path is None

    def test_windows_style_venv_detected(self, tmp_path):
        scripts = tmp_path / ".venv" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "python.exe").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.venv_found is True
        assert scan.venv_path == tmp_path / ".venv"

    def test_posix_style_venv_detected(self, tmp_path):
        bindir = tmp_path / ".venv" / "bin"
        bindir.mkdir(parents=True)
        (bindir / "python").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.venv_found is True

    def test_custom_venv_dir_name_respected(self, tmp_path):
        bindir = tmp_path / "env" / "bin"
        bindir.mkdir(parents=True)
        (bindir / "python").write_text("")
        scan = scan_project_folder(tmp_path, venv_dir="env")
        assert scan.venv_found is True


class TestProjectFileDetection:
    def test_requirements_txt_detected(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.has_requirements is True

    def test_pyproject_toml_detected(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        scan = scan_project_folder(tmp_path)
        assert scan.has_pyproject is True

    def test_setup_py_detected(self, tmp_path):
        (tmp_path / "setup.py").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.has_setup_py is True

    def test_setup_cfg_also_satisfies_has_setup_py(self, tmp_path):
        (tmp_path / "setup.cfg").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.has_setup_py is True

    def test_uv_lock_detected(self, tmp_path):
        (tmp_path / "uv.lock").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.has_uv_lock is True


class TestUvSuggestion:
    def test_uv_lock_present_suggests_uv(self, tmp_path):
        (tmp_path / "uv.lock").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_use_uv is True

    def test_tool_uv_section_in_pyproject_suggests_uv(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_use_uv is True

    def test_plain_pyproject_does_not_suggest_uv(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_use_uv is False

    def test_no_pyproject_or_lock_does_not_suggest_uv(self, tmp_path):
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_use_uv is False


class TestEntryPointSuggestion:
    def test_project_scripts_entry_point_takes_priority(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project.scripts]\n'
            'mytool = "mytool.cli:main"\n'
        )
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_entry_mode == "module"
        assert scan.suggested_app_entry == "mytool.cli"

    def test_fastapi_keyword_suggests_uvicorn_runner(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\ndependencies = ["fastapi"]\n'
        )
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_entry_mode == "runner"
        assert scan.suggested_app_entry == "uvicorn"

    def test_streamlit_keyword_suggests_streamlit_runner(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\ndependencies = ["streamlit"]\n'
        )
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_entry_mode == "runner"
        assert scan.suggested_app_entry == "streamlit"
        assert scan.suggested_runner_args == "run app.py"

    def test_pyqt6_keyword_suggests_file_mode(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\ndependencies = ["pyqt6"]\n'
        )
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_entry_mode == "file"
        assert scan.suggested_app_entry == "main.py"

    def test_falls_back_to_common_entry_filenames(self, tmp_path):
        (tmp_path / "app.py").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_entry_mode == "file"
        assert scan.suggested_app_entry == "app.py"

    def test_prefers_main_py_over_app_py_when_both_present(self, tmp_path):
        (tmp_path / "main.py").write_text("")
        (tmp_path / "app.py").write_text("")
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_app_entry == "main.py"

    def test_no_hints_available_suggests_nothing(self, tmp_path):
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_entry_mode is None
        assert scan.suggested_app_entry is None


class TestHintsMessages:
    def test_hints_is_nonempty_list(self, tmp_path):
        scan = scan_project_folder(tmp_path)
        assert isinstance(scan.hints, list)
        assert len(scan.hints) >= 1

    def test_hints_mention_missing_venv(self, tmp_path):
        scan = scan_project_folder(tmp_path)
        assert any("No venv" in h for h in scan.hints)

    def test_hints_mention_found_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("")
        scan = scan_project_folder(tmp_path)
        assert any("requirements.txt" in h for h in scan.hints)


class TestMalformedPyproject:
    def test_does_not_crash_on_unreadable_pyproject(self, tmp_path):
        # A directory named pyproject.toml would fail a plain read_text();
        # scan_project_folder should not raise.
        bad = tmp_path / "pyproject.toml"
        bad.mkdir()
        scan = scan_project_folder(tmp_path)
        assert scan.has_pyproject is True
        assert scan.suggested_entry_mode is None
