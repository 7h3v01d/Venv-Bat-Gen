"""
Tests for the Windows .bat template generators in core.py:
make_run_bat, make_pip_bat, make_shell_bat, make_sync_bat,
make_doctor_bat, make_test_bat, make_setup_bat.
"""

from __future__ import annotations


from venv_bat_gen.core import (
    make_doctor_bat,
    make_pip_bat,
    make_run_bat,
    make_setup_bat,
    make_shell_bat,
    make_sync_bat,
    make_test_bat,
)


# ---------------------------------------------------------------------------
# make_run_bat
# ---------------------------------------------------------------------------

class TestMakeRunBat:
    def test_starts_with_echo_off(self, base_cfg):
        assert make_run_bat(base_cfg).startswith("@echo off")

    def test_cds_to_script_directory(self, base_cfg):
        assert 'cd /d "%~dp0"' in make_run_bat(base_cfg)

    def test_calls_venv_python_directly_not_activate(self, base_cfg):
        content = make_run_bat(base_cfg)
        assert r"\Scripts\python.exe" in content
        assert "activate" not in content.lower()

    def test_file_mode_invokes_entry_directly(self, base_cfg):
        content = make_run_bat(base_cfg)
        assert '"%PY%" "%APP_ENTRY%" %*' in content

    def test_module_mode_uses_dash_m(self, module_cfg):
        content = make_run_bat(module_cfg)
        assert '"%PY%" -m %APP_ENTRY% %*' in content
        assert "mypackage" in content

    def test_runner_mode_includes_runner_args(self, runner_cfg):
        content = make_run_bat(runner_cfg)
        assert "uvicorn" in content
        assert "app.main:app --host 0.0.0.0 --port 8000 --reload" in content

    def test_pause_on_exit_true_adds_pause(self, cfg_factory):
        cfg = cfg_factory(pause_on_exit=True)
        assert "pause\nexit /b !EXITCODE!" in make_run_bat(cfg)

    def test_pause_on_exit_false_omits_pause(self, cfg_factory):
        cfg = cfg_factory(pause_on_exit=False)
        content = make_run_bat(cfg)
        assert "pause\nexit /b !EXITCODE!" not in content
        assert "exit /b !EXITCODE!" in content

    def test_venv_dir_is_reflected(self, cfg_factory):
        cfg = cfg_factory(venv_dir="env_custom")
        assert 'set "VENV_DIR=env_custom"' in make_run_bat(cfg)

    def test_project_name_is_reflected(self, cfg_factory):
        cfg = cfg_factory(project_name="Widgets")
        assert 'set "PROJECT_NAME=Widgets"' in make_run_bat(cfg)

    def test_missing_venv_produces_helpful_error(self, base_cfg):
        content = make_run_bat(base_cfg)
        assert "[ERROR] Local venv not found" in content

    def test_output_uses_crlf_friendly_literal_newlines(self, base_cfg):
        # The generator returns \n internally; CRLF conversion happens at
        # write time in generate_files(). Just confirm no stray \r here.
        assert "\r" not in make_run_bat(base_cfg)


# ---------------------------------------------------------------------------
# make_pip_bat
# ---------------------------------------------------------------------------

class TestMakePipBat:
    def test_pip_mode_checks_venv_exists(self, base_cfg):
        content = make_pip_bat(base_cfg)
        assert "if not exist" in content
        assert '"%PY%" -m pip %*' in content

    def test_uv_mode_checks_uv_on_path(self, uv_cfg):
        content = make_pip_bat(uv_cfg)
        assert "where uv" in content
        assert "uv pip --python" in content
        assert '"%PY%" -m pip %*' not in content

    def test_uv_and_pip_modes_differ(self, base_cfg, uv_cfg):
        assert make_pip_bat(base_cfg) != make_pip_bat(uv_cfg)


# ---------------------------------------------------------------------------
# make_shell_bat
# ---------------------------------------------------------------------------

class TestMakeShellBat:
    def test_calls_activate_bat_for_interactive_shell(self, base_cfg):
        content = make_shell_bat(base_cfg)
        assert r"Scripts\\activate.bat" in content or r"Scripts\activate.bat" in content

    def test_ends_in_interactive_cmd(self, base_cfg):
        assert content_ends_with_cmd_k(make_shell_bat(base_cfg))


def content_ends_with_cmd_k(content: str) -> bool:
    return "cmd /k" in content


# ---------------------------------------------------------------------------
# make_sync_bat
# ---------------------------------------------------------------------------

class TestMakeSyncBat:
    def test_pip_mode_upgrades_pip_and_installs_requirements(self, base_cfg):
        content = make_sync_bat(base_cfg)
        assert "pip install --upgrade pip" in content
        assert "requirements.txt" in content
        assert "pip check" in content

    def test_uv_mode_prefers_lockfile_then_pyproject_then_requirements(self, uv_cfg):
        content = make_sync_bat(uv_cfg)
        assert "uv.lock" in content
        assert "pyproject.toml" in content
        assert "requirements.txt" in content
        assert "uv sync" in content
        assert "uv pip check" in content

    def test_uv_mode_checks_uv_on_path(self, uv_cfg):
        content = make_sync_bat(uv_cfg)
        assert "where uv" in content


# ---------------------------------------------------------------------------
# make_doctor_bat
# ---------------------------------------------------------------------------

class TestMakeDoctorBat:
    def test_reports_python_environment(self, base_cfg):
        content = make_doctor_bat(base_cfg)
        assert "Python Environment" in content
        assert "pip list" in content or "-m pip list" in content

    def test_uv_block_only_present_when_use_uv(self, base_cfg, uv_cfg):
        assert "uv status" not in make_doctor_bat(base_cfg)
        assert "uv status" in make_doctor_bat(uv_cfg)

    def test_webengine_block_only_present_when_flagged(self, cfg_factory):
        without = cfg_factory(include_webengine_check=False)
        with_flag = cfg_factory(include_webengine_check=True)
        assert "WebEngine" not in make_doctor_bat(without)
        assert "WebEngine" in make_doctor_bat(with_flag)

    def test_file_mode_checks_entry_file_exists(self, base_cfg):
        content = make_doctor_bat(base_cfg)
        assert "Entry file found" in content
        assert "Entry file NOT found" in content

    def test_module_mode_checks_importable(self, module_cfg):
        content = make_doctor_bat(module_cfg)
        assert "importlib.util.find_spec" in content

    def test_checks_common_project_files(self, base_cfg):
        content = make_doctor_bat(base_cfg)
        for marker in ("uv.lock", "pyproject.toml", "requirements.txt"):
            assert marker in content


# ---------------------------------------------------------------------------
# make_test_bat
# ---------------------------------------------------------------------------

class TestMakeTestBat:
    def test_invokes_pytest_via_local_python(self, base_cfg):
        content = make_test_bat(base_cfg)
        assert '"%PY%" -m pytest -v %*' in content

    def test_forwards_exit_code(self, base_cfg):
        content = make_test_bat(base_cfg)
        assert "set \"EXITCODE=%ERRORLEVEL%\"" in content
        assert "exit /b %EXITCODE%" in content

    def test_reports_pass_and_fail_states(self, base_cfg):
        content = make_test_bat(base_cfg)
        assert "TESTS PASSED" in content
        assert "TESTS FAILED" in content


# ---------------------------------------------------------------------------
# make_setup_bat (standalone, non-self-unpacking)
# ---------------------------------------------------------------------------

class TestMakeSetupBat:
    def test_pip_mode_creates_venv_with_stdlib(self, base_cfg):
        content = make_setup_bat(base_cfg)
        assert "python -m venv" in content

    def test_uv_mode_creates_venv_with_uv(self, uv_cfg):
        content = make_setup_bat(uv_cfg)
        assert "uv venv" in content
        assert "where uv" in content

    def test_skips_if_venv_already_exists(self, base_cfg):
        content = make_setup_bat(base_cfg)
        assert "already exists" in content


# ---------------------------------------------------------------------------
# Cross-cutting: generator line / attribution appears in every script
# ---------------------------------------------------------------------------

def test_all_bat_generators_include_attribution_line(base_cfg):
    generators = [
        make_run_bat, make_pip_bat, make_shell_bat,
        make_sync_bat, make_doctor_bat, make_test_bat, make_setup_bat,
    ]
    for gen in generators:
        content = gen(base_cfg)
        assert "Leon Priest" in content
        assert "7h3v01d" in content


def test_project_name_containing_percent_is_escaped(cfg_factory):
    # cmd.exe treats a bare % as the start of a variable reference; a raw
    # 50%-style name would corrupt the generated batch file.
    cfg = cfg_factory(project_name="50% Done")
    content = make_run_bat(cfg)
    assert "%%" in content
    assert "50%%" in content or "50% %" not in content


def test_project_name_containing_quote_is_stripped(cfg_factory):
    cfg = cfg_factory(project_name='My "Cool" App')
    content = make_run_bat(cfg)
    # bat_escape() strips embedded quotes so they can't break the
    # surrounding set "VAR=..." assignment.
    assert 'set "PROJECT_NAME=My Cool App"' in content
