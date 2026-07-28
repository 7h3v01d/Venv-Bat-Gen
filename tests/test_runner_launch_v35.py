"""
Regression tests for the v3.5.0 runner-launch overhaul.

v3.4.0 defects locked down here (each test named for the bug it catches):

  1. run.sh expanded $RUNNER_ARGS unquoted -> word-splitting AND pathname
     glob expansion against the project directory. An argument of ``*.py``
     was replaced by whatever .py files happened to exist next to run.sh.
  2. bat_escape() silently DELETED double quotes from runner args, and
     validation banned them anyway -> arguments containing spaces were
     impossible in run.bat.
  3. run.ps1 re-split the arg string on '\\s+' at runtime -> same limitation.
  4. run.bat enabled delayed expansion it never needed -> any '!' in
     passthrough %* arguments (or in runner args) was corrupted.
  5. [project.scripts] entries were suggested as `python -m <module>`,
     which silently does nothing when the module has no __main__ guard.

The .sh tests execute the generated script for real (POSIX host); the .bat
and .ps1 tests are static template assertions — verify on Windows hardware
before release.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import make_config
from venv_bat_gen import cli
from venv_bat_gen.core import (
    build_previews,
    make_doctor_bat,
    make_doctor_ps1,
    make_doctor_sh,
    make_run_bat,
    make_run_ps1,
    make_run_sh,
    scan_project_folder,
)

IS_POSIX = sys.platform != "win32"

# The arg string every test uses: one glob token, one quoted spaced token,
# one '!' token, one '%' token — everything v3.4 mangled somewhere.
HOSTILE_ARGS = '--include *.py --name "My App" --bang up! --pct 100%'
HOSTILE_PARSED = ["--include", "*.py", "--name", "My App", "--bang", "up!", "--pct", "100%"]


def _fake_venv_python(project: Path) -> Path:
    """Create .venv/bin/python that prints each argv token on its own line."""
    bin_dir = project / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    py = bin_dir / "python"
    py.write_text('#!/usr/bin/env bash\nprintf \'ARG:%s\\n\' "$@"\n')
    py.chmod(0o755)
    return py


def _fake_console_script(project: Path, name: str) -> Path:
    bin_dir = project / ".venv" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = bin_dir / name
    exe.write_text('#!/usr/bin/env bash\nprintf \'ARG:%s\\n\' "$@"\n')
    exe.chmod(0o755)
    return exe


def _run_sh(project: Path, script: str, extra: list[str] | None = None) -> list[str]:
    path = project / "run.sh"
    path.write_text(script)
    path.chmod(0o755)
    result = subprocess.run(
        ["bash", str(path)] + (extra or []),
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return [line[4:] for line in result.stdout.splitlines() if line.startswith("ARG:")]


# ---------------------------------------------------------------------------
# run.sh — live execution
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not IS_POSIX, reason="executes bash")
class TestRunShLive:
    def test_args_survive_globs_spaces_bang_percent(self, tmp_path):
        """Bug 1: v3.4 glob-expanded *.py and split 'My App' into two args."""
        _fake_venv_python(tmp_path)
        # Decoy files the v3.4 unquoted expansion globbed against:
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        cfg = make_config(tmp_path, entry_mode="runner", app_entry="mytool",
                          runner_args=HOSTILE_ARGS, pause_on_exit=False)
        argv = _run_sh(tmp_path, make_run_sh(cfg))
        assert argv == ["-m", "mytool"] + HOSTILE_PARSED

    def test_passthrough_args_untouched(self, tmp_path):
        _fake_venv_python(tmp_path)
        cfg = make_config(tmp_path, entry_mode="runner", app_entry="mytool",
                          runner_args="--port 8000", pause_on_exit=False)
        argv = _run_sh(tmp_path, make_run_sh(cfg),
                       extra=["--user-arg", "with space", "bang!"])
        assert argv == ["-m", "mytool", "--port", "8000",
                        "--user-arg", "with space", "bang!"]

    def test_empty_args_no_unbound_error_under_set_u(self, tmp_path):
        """The ${arr[@]+...} guard must keep set -u happy with zero args."""
        _fake_venv_python(tmp_path)
        cfg = make_config(tmp_path, entry_mode="runner", app_entry="mytool",
                          runner_args="", pause_on_exit=False)
        argv = _run_sh(tmp_path, make_run_sh(cfg))
        assert argv == ["-m", "mytool"]

    def test_script_mode_runs_console_binary(self, tmp_path):
        _fake_venv_python(tmp_path)
        _fake_console_script(tmp_path, "adp-server")
        cfg = make_config(tmp_path, entry_mode="script", app_entry="adp-server",
                          runner_args='--config "conf dir/app.json"',
                          pause_on_exit=False)
        argv = _run_sh(tmp_path, make_run_sh(cfg), extra=["--verbose"])
        assert argv == ["--config", "conf dir/app.json", "--verbose"]

    def test_script_mode_missing_binary_fails_closed(self, tmp_path):
        _fake_venv_python(tmp_path)  # venv exists, script does not
        cfg = make_config(tmp_path, entry_mode="script", app_entry="ghost-tool",
                          runner_args="", pause_on_exit=False)
        path = tmp_path / "run.sh"
        path.write_text(make_run_sh(cfg))
        path.chmod(0o755)
        result = subprocess.run(["bash", str(path)], capture_output=True,
                                text=True, timeout=30, check=False)
        assert result.returncode == 1
        assert "Console script not found" in result.stdout


# ---------------------------------------------------------------------------
# run.bat — static template assertions (execute on Windows before release)
# ---------------------------------------------------------------------------

class TestRunBatStatic:
    def test_no_delayed_expansion(self, cfg_factory):
        """Bug 4: delayed expansion corrupted '!' in passthrough args."""
        content = make_run_bat(cfg_factory())
        assert "EnableDelayedExpansion" not in content
        assert not re.search(r"!\w+!", content)

    def test_spaced_arg_survives_as_quoted_token(self, tmp_path):
        """Bug 2: v3.4 deleted the quotes -> 'My App' became two tokens."""
        cfg = make_config(tmp_path, entry_mode="runner", app_entry="mytool",
                          runner_args=HOSTILE_ARGS)
        content = make_run_bat(cfg)
        assert '"My App"' in content
        assert '"*.py"' in content          # quoted: cmd does not glob, tool receives literal
        assert '"up!"' in content           # '!' literal without delayed expansion
        assert '"100%%"' in content         # '%' doubled for batch parsing
        # launch line carries the literal vector before passthrough %*
        assert '-m %APP_ENTRY% "--include" "*.py" "--name" "My App"' in content

    def test_script_mode_uses_scripts_exe_with_existence_check(self, tmp_path):
        cfg = make_config(tmp_path, entry_mode="script", app_entry="adp-server",
                          runner_args="--port 8080")
        content = make_run_bat(cfg)
        assert 'set "SCRIPT_EXE=%CD%\\%VENV_DIR%\\Scripts\\%APP_ENTRY%.exe"' in content
        assert '"%SCRIPT_EXE%" "--port" "8080" %*' in content
        assert 'if /I "%ENTRY_MODE%"=="script" if not exist "%SCRIPT_EXE%"' in content


# ---------------------------------------------------------------------------
# run.ps1 — static template assertions
# ---------------------------------------------------------------------------

class TestRunPs1Static:
    def test_spaced_arg_survives_in_array_literal(self, tmp_path):
        """Bug 3: v3.4 re-split on whitespace at runtime."""
        cfg = make_config(tmp_path, entry_mode="runner", app_entry="mytool",
                          runner_args=HOSTILE_ARGS)
        content = make_run_ps1(cfg)
        assert "'My App'" in content
        assert "'*.py'" in content
        assert "-split '\\s+'" not in content

    def test_script_mode_branch_present(self, tmp_path):
        cfg = make_config(tmp_path, entry_mode="script", app_entry="adp-server",
                          runner_args="")
        content = make_run_ps1(cfg)
        assert '$SCRIPT_EXE = Join-Path $PSScriptRoot "$VENV_DIR\\Scripts\\$APP_ENTRY.exe"' in content
        assert '"script" { & $SCRIPT_EXE @RUNNER_ARGS @args }' in content
        assert "Console script not found" in content


# ---------------------------------------------------------------------------
# doctor.* — script-mode entry checks exist in all three shells
# ---------------------------------------------------------------------------

class TestDoctorScriptMode:
    def test_all_three_doctors_check_console_script(self, tmp_path):
        cfg = make_config(tmp_path, entry_mode="script", app_entry="adp-server",
                          runner_args="--port 8080")
        assert "Console script" in make_doctor_bat(cfg)
        assert "Console script" in make_doctor_sh(cfg)
        assert "Console script" in make_doctor_ps1(cfg)


# ---------------------------------------------------------------------------
# Scanner — bug 5
# ---------------------------------------------------------------------------

class TestScannerConsoleScripts:
    def test_project_scripts_suggests_script_mode_with_name(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "adp"\n'
            "[project.scripts]\n"
            'ADP-Server = "adp.server.cli:main"\n'
        )
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_entry_mode == "script"
        # Case preserved (v3.4 lowercased the whole pyproject before matching):
        assert scan.suggested_app_entry == "ADP-Server"
        assert scan.suggested_runner_args == ""

    def test_quoted_script_name_supported(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project.scripts]\n"
            '"my-tool" = "pkg.cli:main"\n'
        )
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_app_entry == "my-tool"


# ---------------------------------------------------------------------------
# CLI — --script flag and quoted args end-to-end
# ---------------------------------------------------------------------------

def _run_cli(argv):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    return excinfo.value.code


class TestCliScriptAndQuoting:
    def test_script_mode_generates(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        code = _run_cli(["generate", str(proj), "--script", "--entry", "adp-server",
                         "--runner-args", '--config "conf dir/app.json"'])
        assert code == 0
        content = (proj / "run.bat").read_text(encoding="utf-8")
        assert "SCRIPT_EXE" in content
        assert '"conf dir/app.json"' in content

    def test_quoted_spaced_args_now_accepted(self, tmp_path):
        """Regression: v3.4 hard-rejected any double quote in runner args."""
        proj = tmp_path / "proj"
        proj.mkdir()
        code = _run_cli(["generate", str(proj), "--runner", "--entry", "uvicorn",
                         "--runner-args", 'app:app --header "X-App: My App"'])
        assert code == 0

    def test_invalid_script_name_rejected(self, tmp_path, capsys):
        proj = tmp_path / "proj"
        proj.mkdir()
        code = _run_cli(["generate", str(proj), "--script",
                         "--entry", "Scripts/../evil"])
        assert code == 1
        assert "Invalid console-script name" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Previews build for every mode without error
# ---------------------------------------------------------------------------

class TestPreviewsAllModes:
    @pytest.mark.parametrize("mode,entry", [
        ("file", "main.py"),
        ("module", "mypkg"),
        ("runner", "uvicorn"),
        ("script", "adp-server"),
    ])
    def test_build_previews_smoke(self, tmp_path, mode, entry):
        cfg = make_config(tmp_path, entry_mode=mode, app_entry=entry,
                          runner_args=(HOSTILE_ARGS if mode in ("runner", "script") else ""),
                          include_posix=True, include_powershell=True,
                          include_setup=True, include_test_bat=True)
        previews = build_previews(cfg)
        assert "run.bat" in previews and "run.sh" in previews and "run.ps1" in previews
