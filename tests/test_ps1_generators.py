"""
Tests for the PowerShell .ps1 template generators in core.py:
make_run_ps1, make_pip_ps1, make_shell_ps1, make_sync_ps1,
make_doctor_ps1, make_test_ps1, make_setup_ps1.
"""

from __future__ import annotations

from venv_bat_gen.core import (
    make_doctor_ps1,
    make_pip_ps1,
    make_run_ps1,
    make_setup_ps1,
    make_shell_ps1,
    make_sync_ps1,
    make_test_ps1,
)

ALL_PS1_GENERATORS = [
    make_run_ps1, make_pip_ps1, make_shell_ps1,
    make_sync_ps1, make_doctor_ps1, make_test_ps1, make_setup_ps1,
]


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------

def test_all_ps1_generators_start_with_requires_directive(base_cfg):
    for gen in ALL_PS1_GENERATORS:
        assert gen(base_cfg).startswith("#Requires -Version 5.1")


def test_all_ps1_generators_include_attribution_line(base_cfg):
    for gen in ALL_PS1_GENERATORS:
        content = gen(base_cfg)
        assert "Leon Priest" in content
        assert "7h3v01d" in content


def test_all_ps1_generators_cd_to_script_dir(base_cfg):
    for gen in ALL_PS1_GENERATORS:
        assert "Set-Location -Path $PSScriptRoot" in gen(base_cfg)


def test_no_curly_brace_placeholders_leak_through(base_cfg):
    # Regression guard: templates are built with raw strings + token
    # substitution specifically to avoid f-string brace-escaping mistakes.
    # If a __TOKEN__ placeholder were ever left unreplaced, it would show
    # up literally in the output — this catches that class of bug directly.
    for gen in ALL_PS1_GENERATORS:
        content = gen(base_cfg)
        assert "__" not in content, f"{gen.__name__} left an unreplaced token"


# ---------------------------------------------------------------------------
# make_run_ps1
# ---------------------------------------------------------------------------

class TestMakeRunPs1:
    def test_uses_join_path_for_python_exe(self, base_cfg):
        content = make_run_ps1(base_cfg)
        assert r'Join-Path $PSScriptRoot "$VENV_DIR\Scripts\python.exe"' in content

    def test_file_mode_invokes_entry_directly(self, base_cfg):
        content = make_run_ps1(base_cfg)
        assert "default { & $PY $APP_ENTRY @args }" in content

    def test_module_mode_uses_dash_m(self, module_cfg):
        content = make_run_ps1(module_cfg)
        assert '"module" { & $PY -m $APP_ENTRY @args }' in content
        assert "mypackage" in content

    def test_runner_mode_splits_args_via_named_splat(self, runner_cfg):
        content = make_run_ps1(runner_cfg)
        assert "$RunnerArgsArray = $RUNNER_ARGS -split" in content
        assert "@RunnerArgsArray @args" in content
        assert "app.main:app --host 0.0.0.0 --port 8000 --reload" in content

    def test_pause_on_exit_true_adds_read_host(self, cfg_factory):
        cfg = cfg_factory(pause_on_exit=True)
        assert 'Read-Host "Press Enter to continue" | Out-Null' in make_run_ps1(cfg)

    def test_pause_on_exit_false_omits_read_host(self, cfg_factory):
        cfg = cfg_factory(pause_on_exit=False)
        content = make_run_ps1(cfg)
        assert 'Read-Host "Press Enter to continue"' not in content

    def test_venv_dir_is_reflected(self, cfg_factory):
        cfg = cfg_factory(venv_dir="env_custom")
        assert "$VENV_DIR     = 'env_custom'" in make_run_ps1(cfg)

    def test_missing_venv_produces_helpful_error(self, base_cfg):
        content = make_run_ps1(base_cfg)
        assert "[ERROR] Local venv not found" in content

    def test_output_uses_crlf_friendly_literal_newlines(self, base_cfg):
        assert "\r" not in make_run_ps1(base_cfg)

    def test_sets_window_title(self, base_cfg):
        content = make_run_ps1(base_cfg)
        assert '$Host.UI.RawUI.WindowTitle = "$PROJECT_NAME - RUN"' in content


# ---------------------------------------------------------------------------
# make_pip_ps1
# ---------------------------------------------------------------------------

class TestMakePipPs1:
    def test_pip_mode_checks_venv_exists(self, base_cfg):
        content = make_pip_ps1(base_cfg)
        assert "Test-Path -LiteralPath $PY" in content
        assert "& $PY -m pip @args" in content

    def test_uv_mode_checks_uv_on_path(self, uv_cfg):
        content = make_pip_ps1(uv_cfg)
        assert "Get-Command uv -ErrorAction SilentlyContinue" in content
        assert "uv pip --python" in content
        assert "& $PY -m pip @args" not in content

    def test_uv_and_pip_modes_differ(self, base_cfg, uv_cfg):
        assert make_pip_ps1(base_cfg) != make_pip_ps1(uv_cfg)


# ---------------------------------------------------------------------------
# make_shell_ps1
# ---------------------------------------------------------------------------

class TestMakeShellPs1:
    def test_dot_sources_activate_ps1(self, base_cfg):
        content = make_shell_ps1(base_cfg)
        assert r"Scripts\Activate.ps1" in content
        assert ". $ACTIVATE" in content

    def test_handles_execution_policy_failure_gracefully(self, base_cfg):
        content = make_shell_ps1(base_cfg)
        assert "try {" in content
        assert "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass" in content

    def test_keeps_session_open_via_nested_powershell(self, base_cfg):
        content = make_shell_ps1(base_cfg)
        assert "powershell -NoExit" in content


# ---------------------------------------------------------------------------
# make_sync_ps1
# ---------------------------------------------------------------------------

class TestMakeSyncPs1:
    def test_pip_mode_upgrades_pip_and_installs_requirements(self, base_cfg):
        content = make_sync_ps1(base_cfg)
        assert "pip install --upgrade pip" in content
        assert "requirements.txt" in content
        assert "pip check" in content

    def test_uv_mode_prefers_lockfile_then_pyproject_then_requirements(self, uv_cfg):
        content = make_sync_ps1(uv_cfg)
        assert "uv.lock" in content
        assert "pyproject.toml" in content
        assert "uv sync" in content
        assert "uv pip check" in content

    def test_always_pauses_regardless_of_pause_on_exit(self, cfg_factory):
        # Matches make_sync_bat/make_sync_sh: sync always waits for a
        # keypress, independent of the run.ps1-only pause_on_exit setting.
        cfg = cfg_factory(pause_on_exit=False)
        assert 'Read-Host "Press Enter to continue"' in make_sync_ps1(cfg)


# ---------------------------------------------------------------------------
# make_doctor_ps1
# ---------------------------------------------------------------------------

class TestMakeDoctorPs1:
    def test_reports_python_environment(self, base_cfg):
        content = make_doctor_ps1(base_cfg)
        assert "Python Environment" in content
        assert "pip list" in content

    def test_uv_block_only_present_when_use_uv(self, base_cfg, uv_cfg):
        assert "uv status" not in make_doctor_ps1(base_cfg)
        assert "uv status" in make_doctor_ps1(uv_cfg)

    def test_webengine_block_only_present_when_flagged(self, cfg_factory):
        without = cfg_factory(include_webengine_check=False)
        with_flag = cfg_factory(include_webengine_check=True)
        assert "WebEngine" not in make_doctor_ps1(without)
        assert "WebEngine" in make_doctor_ps1(with_flag)

    def test_file_mode_checks_entry_file_exists(self, base_cfg):
        content = make_doctor_ps1(base_cfg)
        assert "Entry file found" in content
        assert "Entry file NOT found" in content

    def test_module_mode_passes_entry_as_argument_not_interpolated(self, module_cfg):
        # Passed via `$APP_ENTRY` as a script argument (sys.argv[1]) rather
        # than interpolated into the -c code string, so odd characters in
        # the module name can't break out of the inline Python snippet.
        content = make_doctor_ps1(module_cfg)
        assert "importlib.util.find_spec" in content
        assert "sys.argv[1]" in content

    def test_checks_common_project_files(self, base_cfg):
        content = make_doctor_ps1(base_cfg)
        for marker in ("uv.lock", "pyproject.toml", "requirements.txt"):
            assert marker in content


# ---------------------------------------------------------------------------
# make_test_ps1
# ---------------------------------------------------------------------------

class TestMakeTestPs1:
    def test_invokes_pytest_via_local_python(self, base_cfg):
        content = make_test_ps1(base_cfg)
        assert "& $PY -m pytest -v @args" in content

    def test_forwards_exit_code(self, base_cfg):
        content = make_test_ps1(base_cfg)
        assert "$EXITCODE = $LASTEXITCODE" in content
        assert "exit $EXITCODE" in content

    def test_reports_pass_and_fail_states(self, base_cfg):
        content = make_test_ps1(base_cfg)
        assert "TESTS PASSED" in content
        assert "TESTS FAILED" in content


# ---------------------------------------------------------------------------
# make_setup_ps1
# ---------------------------------------------------------------------------

class TestMakeSetupPs1:
    def test_pip_mode_creates_venv_with_stdlib(self, base_cfg):
        content = make_setup_ps1(base_cfg)
        assert "python -m venv $VENV_DIR" in content

    def test_uv_mode_creates_venv_with_uv(self, uv_cfg):
        content = make_setup_ps1(uv_cfg)
        assert "uv venv $VENV_DIR" in content
        assert "Get-Command uv -ErrorAction SilentlyContinue" in content

    def test_skips_if_venv_already_exists(self, base_cfg):
        content = make_setup_ps1(base_cfg)
        assert "already exists" in content


# ---------------------------------------------------------------------------
# Escaping
# ---------------------------------------------------------------------------

def test_project_name_with_single_quote_is_doubled(cfg_factory):
    cfg = cfg_factory(project_name="Bob's App")
    content = make_run_ps1(cfg)
    # _ps1_escape doubles embedded single quotes so they can't terminate
    # the surrounding '...' string literal early.
    assert "$PROJECT_NAME = 'Bob''s App'" in content


def test_project_name_with_dollar_and_backtick_is_left_alone(cfg_factory):
    # Single-quoted PowerShell strings don't interpolate $ or backticks,
    # so unlike bat/sh, these need no special escaping at all.
    cfg = cfg_factory(project_name="Cost: $5 `back`")
    content = make_run_ps1(cfg)
    assert "$PROJECT_NAME = 'Cost: $5 `back`'" in content
