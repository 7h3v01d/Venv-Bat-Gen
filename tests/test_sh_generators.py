"""
Tests for the POSIX .sh template generators in core.py:
make_run_sh, make_pip_sh, make_shell_sh, make_sync_sh,
make_doctor_sh, make_test_sh, make_setup_sh.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from venv_bat_gen.core import (
    make_doctor_sh,
    make_pip_sh,
    make_run_sh,
    make_setup_sh,
    make_shell_sh,
    make_sync_sh,
    make_test_sh,
)

ALL_SH_GENERATORS = [
    make_run_sh, make_pip_sh, make_shell_sh,
    make_sync_sh, make_doctor_sh, make_test_sh, make_setup_sh,
]


# ---------------------------------------------------------------------------
# Cross-cutting shebang / attribution checks
# ---------------------------------------------------------------------------

def test_all_sh_generators_start_with_bash_shebang(base_cfg):
    for gen in ALL_SH_GENERATORS:
        assert gen(base_cfg).startswith("#!/usr/bin/env bash")


def test_all_sh_generators_include_attribution_line(base_cfg):
    for gen in ALL_SH_GENERATORS:
        content = gen(base_cfg)
        assert "Leon Priest" in content
        assert "7h3v01d" in content


def test_all_sh_generators_cd_to_script_dir(base_cfg):
    for gen in ALL_SH_GENERATORS:
        assert 'cd "$(dirname "$0")"' in gen(base_cfg)


# ---------------------------------------------------------------------------
# make_run_sh
# ---------------------------------------------------------------------------

class TestMakeRunSh:
    def test_calls_venv_python_directly(self, base_cfg):
        content = make_run_sh(base_cfg)
        assert '$VENV_DIR/bin/python' in content
        assert "source" not in content  # no manual activation

    def test_file_mode_invokes_entry_directly(self, base_cfg):
        content = make_run_sh(base_cfg)
        assert '"$PY" "$APP_ENTRY" "$@"' in content

    def test_module_mode_uses_dash_m(self, module_cfg):
        content = make_run_sh(module_cfg)
        assert '"$PY" -m "$APP_ENTRY" "$@"' in content

    def test_runner_mode_includes_runner_args_unquoted_for_word_splitting(self, runner_cfg):
        content = make_run_sh(runner_cfg)
        assert "$PY" in content
        assert '$RUNNER_ARGS "$@"' in content

    def test_pause_on_exit_true_adds_read_prompt(self, cfg_factory):
        cfg = cfg_factory(pause_on_exit=True)
        assert "read -r -p" in make_run_sh(cfg)

    def test_pause_on_exit_false_omits_read_prompt(self, cfg_factory):
        cfg = cfg_factory(pause_on_exit=False)
        assert "read -r -p" not in make_run_sh(cfg)

    def test_uses_lf_only_no_crlf(self, base_cfg):
        assert "\r" not in make_run_sh(base_cfg)

    def test_sets_strict_mode(self, base_cfg):
        assert "set -euo pipefail" in make_run_sh(base_cfg)


# ---------------------------------------------------------------------------
# make_pip_sh
# ---------------------------------------------------------------------------

class TestMakePipSh:
    def test_pip_mode_checks_executable_exists(self, base_cfg):
        content = make_pip_sh(base_cfg)
        assert "[[ ! -x " in content
        assert '"$PY" -m pip "$@"' in content

    def test_uv_mode_checks_uv_command(self, uv_cfg):
        content = make_pip_sh(uv_cfg)
        assert "command -v uv" in content
        assert "uv pip --python" in content


# ---------------------------------------------------------------------------
# make_shell_sh
# ---------------------------------------------------------------------------

class TestMakeShellSh:
    def test_sources_activate_script(self, base_cfg):
        content = make_shell_sh(base_cfg)
        assert "bin/activate" in content
        assert "source" in content


# ---------------------------------------------------------------------------
# make_sync_sh
# ---------------------------------------------------------------------------

class TestMakeSyncSh:
    def test_pip_mode_installs_requirements_and_checks(self, base_cfg):
        content = make_sync_sh(base_cfg)
        assert "pip install --upgrade pip" in content
        assert "requirements.txt" in content
        assert "pip check" in content

    def test_uv_mode_prefers_lockfile(self, uv_cfg):
        content = make_sync_sh(uv_cfg)
        assert "uv.lock" in content
        assert "uv sync" in content
        assert "uv pip check" in content


# ---------------------------------------------------------------------------
# make_doctor_sh
# ---------------------------------------------------------------------------

class TestMakeDoctorSh:
    def test_uv_block_only_present_when_use_uv(self, base_cfg, uv_cfg):
        assert "uv status" not in make_doctor_sh(base_cfg)
        assert "uv status" in make_doctor_sh(uv_cfg)

    def test_webengine_block_only_present_when_flagged(self, cfg_factory):
        without = cfg_factory(include_webengine_check=False)
        with_flag = cfg_factory(include_webengine_check=True)
        assert "WebEngine" not in make_doctor_sh(without)
        assert "WebEngine" in make_doctor_sh(with_flag)

    def test_module_mode_checks_importable(self, module_cfg):
        content = make_doctor_sh(module_cfg)
        assert "importlib.util.find_spec" in content


# ---------------------------------------------------------------------------
# make_test_sh
# ---------------------------------------------------------------------------

class TestMakeTestSh:
    def test_invokes_pytest_via_local_python(self, base_cfg):
        content = make_test_sh(base_cfg)
        assert '"$PY" -m pytest -v "$@"' in content

    def test_reports_pass_and_fail_states(self, base_cfg):
        content = make_test_sh(base_cfg)
        assert "TESTS PASSED" in content
        assert "TESTS FAILED" in content

    def test_pytest_invocation_is_guarded_against_set_e_early_exit(self, base_cfg):
        # Regression test: `set -euo pipefail` is active in this script. An
        # unguarded `"$PY" -m pytest ...` followed by a bare `EXITCODE=$?`
        # on the next line would make bash abort the *entire script* the
        # instant pytest returns non-zero — before EXITCODE=$? or the
        # PASSED/FAILED banner below it ever runs. The `|| EXITCODE=$?`
        # guard (with EXITCODE pre-declared) is what prevents that.
        content = make_test_sh(base_cfg)
        assert "EXITCODE=0" in content
        assert '"$PY" -m pytest -v "$@" || EXITCODE=$?' in content

    @pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
    def test_failed_tests_still_print_banner_and_propagate_exit_code(self, cfg_factory, tmp_path):
        # End-to-end proof the guard actually works at runtime, not just
        # that the right-looking text is present in the template.
        bin_dir = tmp_path / ".venv" / "bin"
        bin_dir.mkdir(parents=True)
        fake_python = bin_dir / "python"
        fake_python.write_text("#!/usr/bin/env bash\necho 'pretend pytest run'\nexit 1\n")
        fake_python.chmod(0o755)

        cfg = cfg_factory(pause_on_exit=False)
        test_sh = tmp_path / "test.sh"
        test_sh.write_text(make_test_sh(cfg))
        test_sh.chmod(0o755)

        result = subprocess.run(
            ["bash", str(test_sh)], cwd=tmp_path, capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "TESTS FAILED" in result.stdout
        assert "(exit code: 1)" in result.stdout


# ---------------------------------------------------------------------------
# make_setup_sh
# ---------------------------------------------------------------------------

class TestMakeSetupSh:
    def test_pip_mode_creates_venv_with_stdlib(self, base_cfg):
        content = make_setup_sh(base_cfg)
        assert "-m venv" in content

    def test_uv_mode_creates_venv_with_uv(self, uv_cfg):
        content = make_setup_sh(uv_cfg)
        assert "uv venv" in content


# ---------------------------------------------------------------------------
# Escaping
# ---------------------------------------------------------------------------

def test_project_name_with_shell_metacharacters_is_escaped(cfg_factory):
    cfg = cfg_factory(project_name='My $(rm -rf) "App"')
    content = make_run_sh(cfg)
    # _sh_escape backslash-escapes $, `, ", and \ so the value can't break
    # out of its surrounding double-quoted assignment.
    assert r'\$(rm -rf)' in content
    assert r'\"App\"' in content
