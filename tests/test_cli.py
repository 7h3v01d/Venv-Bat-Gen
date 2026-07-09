"""
Tests for venv_bat_gen.cli — the argparse wiring around core.py.

cli.main() always calls sys.exit(), even on success, so every test goes
through the run_cli() helper below and asserts on (exit_code, stdout, stderr).
"""

from __future__ import annotations

import re

import pytest

from venv_bat_gen import cli


def _strip_ansi(text: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", text)


def run_cli(argv):
    """Invoke cli.main(argv) and return its sys.exit() code."""
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    return excinfo.value.code


@pytest.fixture
def project(tmp_path):
    """An empty project folder, as a string path (like real argv)."""
    folder = tmp_path / "proj"
    folder.mkdir()
    return folder


# ---------------------------------------------------------------------------
# Top-level: --version, no command, --help
# ---------------------------------------------------------------------------

class TestTopLevel:
    def test_version_prints_and_exits_zero(self, capsys):
        code = run_cli(["--version"])
        assert code == 0
        out = capsys.readouterr().out
        assert "venv-bat-gen" in out

    def test_no_command_prints_help_and_exits_zero(self, capsys):
        code = run_cli([])
        assert code == 0
        out = capsys.readouterr().out
        assert "usage" in out.lower()

    def test_unknown_subcommand_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["bogus-command"])
        assert excinfo.value.code != 0


# ---------------------------------------------------------------------------
# generate: --list-presets
# ---------------------------------------------------------------------------

class TestListPresets:
    def test_list_presets_exits_zero(self, project, capsys):
        code = run_cli(["generate", str(project), "--list-presets"])
        assert code == 0

    def test_list_presets_shows_builtins(self, project, capsys):
        run_cli(["generate", str(project), "--list-presets"])
        out = _strip_ansi(capsys.readouterr().out)
        assert "FastAPI / Uvicorn" in out
        assert "(built-in)" in out

    def test_list_presets_does_not_write_files(self, project, capsys):
        run_cli(["generate", str(project), "--list-presets"])
        capsys.readouterr()
        assert list(project.iterdir()) == []


# ---------------------------------------------------------------------------
# generate: mutual exclusion
# ---------------------------------------------------------------------------

class TestMutuallyExclusiveFlags:
    def test_self_unpack_and_setup_together_is_an_error(self, project, capsys):
        code = run_cli(["generate", str(project), "--self-unpack", "--setup"])
        assert code == 1
        err = _strip_ansi(capsys.readouterr().err)
        assert "mutually exclusive" in err

    def test_self_unpack_and_setup_together_writes_nothing(self, project, capsys):
        run_cli(["generate", str(project), "--self-unpack", "--setup"])
        capsys.readouterr()
        assert list(project.iterdir()) == []

    def test_file_module_runner_are_mutually_exclusive_via_argparse(self, project, capsys):
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["generate", str(project), "--file", "--module"])
        assert excinfo.value.code == 2  # argparse's own usage-error code


# ---------------------------------------------------------------------------
# generate: preset loading
# ---------------------------------------------------------------------------

class TestPresetLoading:
    def test_unknown_preset_warns_but_still_generates(self, project, capsys):
        code = run_cli(["generate", str(project), "--entry", "main.py",
                         "--preset", "Nonexistent Preset"])
        assert code == 0
        out = _strip_ansi(capsys.readouterr().out)
        assert "not found" in out
        assert (project / "run.bat").exists()

    def test_known_preset_applies_its_settings(self, project, capsys):
        code = run_cli(["generate", str(project), "--preset", "FastAPI / Uvicorn"])
        assert code == 0
        capsys.readouterr()
        run_bat = (project / "run.bat").read_text()
        assert "uvicorn" in run_bat

    def test_explicit_cli_flag_overrides_preset(self, project, capsys):
        # FastAPI preset suggests entry_mode=runner/app_entry=uvicorn; an
        # explicit --file --entry app.py on the command line should win.
        run_cli(["generate", str(project), "--preset", "FastAPI / Uvicorn",
                  "--file", "--entry", "app.py"])
        capsys.readouterr()
        run_bat = (project / "run.bat").read_text()
        assert '"%PY%" "%APP_ENTRY%" %*' in run_bat
        assert "app.py" in run_bat


# ---------------------------------------------------------------------------
# generate: priority resolution (CLI > preset > scan > default)
# ---------------------------------------------------------------------------

class TestPriorityResolution:
    def test_scan_suggestion_used_when_no_cli_flag_or_preset(self, project, capsys):
        (project / "pyproject.toml").write_text('[project]\ndependencies=["fastapi"]\n')
        code = run_cli(["generate", str(project)])
        assert code == 0
        out = _strip_ansi(capsys.readouterr().out)
        assert "fastapi" in out.lower() or "uvicorn" in out.lower()
        run_bat = (project / "run.bat").read_text()
        assert "uvicorn" in run_bat

    def test_cli_flag_overrides_scan_suggestion(self, project, capsys):
        (project / "pyproject.toml").write_text('[project]\ndependencies=["fastapi"]\n')
        run_cli(["generate", str(project), "--file", "--entry", "main.py"])
        capsys.readouterr()
        run_bat = (project / "run.bat").read_text()
        assert '"%PY%" "%APP_ENTRY%" %*' in run_bat

    def test_default_used_when_nothing_else_available(self, project, capsys):
        run_cli(["generate", str(project)])
        capsys.readouterr()
        run_bat = (project / "run.bat").read_text()
        assert "main.py" in run_bat


# ---------------------------------------------------------------------------
# generate: validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_invalid_module_name_rejected(self, project, capsys):
        code = run_cli(["generate", str(project), "--module", "--entry", "not-a-module"])
        assert code == 1
        err = _strip_ansi(capsys.readouterr().err)
        assert "Invalid module name" in err
        assert list(project.iterdir()) == []

    def test_unsafe_runner_args_rejected(self, project, capsys):
        code = run_cli(["generate", str(project), "--runner", "--entry", "uvicorn",
                         "--runner-args", "app:app & del *.*"])
        assert code == 1
        err = _strip_ansi(capsys.readouterr().err)
        assert "unsafe characters" in err

    def test_safe_runner_args_accepted(self, project, capsys):
        code = run_cli(["generate", str(project), "--runner", "--entry", "uvicorn",
                         "--runner-args", "app:app --port 8000"])
        assert code == 0


# ---------------------------------------------------------------------------
# generate: --preview
# ---------------------------------------------------------------------------

class TestPreview:
    def test_preview_does_not_write_files(self, project, capsys):
        code = run_cli(["generate", str(project), "--preview"])
        assert code == 0
        capsys.readouterr()
        assert list(project.iterdir()) == []

    def test_preview_prints_script_contents(self, project, capsys):
        run_cli(["generate", str(project), "--preview"])
        out = _strip_ansi(capsys.readouterr().out)
        assert "run.bat" in out
        assert "@echo off" in out


# ---------------------------------------------------------------------------
# generate: successful run
# ---------------------------------------------------------------------------

class TestGenerateSuccess:
    def test_writes_expected_files(self, project, capsys):
        code = run_cli(["generate", str(project), "--entry", "main.py"])
        assert code == 0
        capsys.readouterr()
        for name in ("run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat"):
            assert (project / name).exists()

    def test_reports_done_message(self, project, capsys):
        run_cli(["generate", str(project), "--entry", "main.py"])
        out = _strip_ansi(capsys.readouterr().out)
        assert "Done" in out
        assert str(project) in out

    def test_posix_flag_adds_sh_files(self, project, capsys):
        run_cli(["generate", str(project), "--posix"])
        capsys.readouterr()
        assert (project / "run.sh").exists()

    def test_creates_folder_if_missing(self, tmp_path, capsys):
        folder = tmp_path / "not_yet_created"
        code = run_cli(["generate", str(folder), "--entry", "main.py"])
        assert code == 0
        capsys.readouterr()
        assert folder.is_dir()

    def test_existing_file_without_overwrite_errors(self, project, capsys):
        (project / "run.bat").write_text("old")
        code = run_cli(["generate", str(project), "--entry", "main.py"])
        assert code == 1
        err = _strip_ansi(capsys.readouterr().err)
        assert "ERROR" in err

    def test_overwrite_flag_allows_replacing_files(self, project, capsys):
        (project / "run.bat").write_text("old")
        code = run_cli(["generate", str(project), "--entry", "main.py", "--overwrite"])
        assert code == 0
        capsys.readouterr()
        assert "old" not in (project / "run.bat").read_text()

    def test_unexpected_generate_files_error_is_caught(self, project, capsys, monkeypatch):
        def _boom(cfg):
            raise PermissionError("simulated disk failure")

        monkeypatch.setattr("venv_bat_gen.cli.generate_files", _boom)
        code = run_cli(["generate", str(project), "--entry", "main.py"])
        assert code == 1
        err = _strip_ansi(capsys.readouterr().err)
        assert "ERROR" in err
        assert "simulated disk failure" in err


# ---------------------------------------------------------------------------
# generate: self-unpack tip block
# ---------------------------------------------------------------------------

class TestSelfUnpackTip:
    def test_tip_lists_default_companions(self, project, capsys):
        run_cli(["generate", str(project), "--self-unpack"])
        out = _strip_ansi(capsys.readouterr().out)
        assert "gitignore" in out.lower()
        for name in ("run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat"):
            assert name in out

    def test_tip_includes_test_bat_when_flagged(self, project, capsys):
        run_cli(["generate", str(project), "--self-unpack", "--test"])
        out = _strip_ansi(capsys.readouterr().out)
        assert "test.bat" in out

    def test_tip_includes_posix_when_flagged(self, project, capsys):
        run_cli(["generate", str(project), "--self-unpack", "--posix"])
        out = _strip_ansi(capsys.readouterr().out)
        assert "run.sh" in out

    def test_self_unpack_only_writes_setup_bat(self, project, capsys):
        run_cli(["generate", str(project), "--self-unpack"])
        capsys.readouterr()
        assert [p.name for p in project.iterdir()] == ["setup.bat"]


# ---------------------------------------------------------------------------
# generate: --create-venv (subprocess mocked)
# ---------------------------------------------------------------------------

class TestCreateVenvFlag:
    def test_skips_with_message_when_venv_already_exists(self, project, capsys):
        (project / ".venv").mkdir()
        code = run_cli(["generate", str(project), "--entry", "main.py", "--create-venv"])
        assert code == 0
        out = _strip_ansi(capsys.readouterr().out)
        assert "already exists" in out

    def test_creates_venv_and_reports_success(self, project, capsys, monkeypatch):
        monkeypatch.setattr("venv_bat_gen.core.subprocess.run", lambda *a, **kw: None)
        code = run_cli(["generate", str(project), "--entry", "main.py", "--create-venv"])
        assert code == 0
        out = _strip_ansi(capsys.readouterr().out)
        assert "created" in out.lower()

    def test_venv_creation_failure_is_reported_but_does_not_fail_the_command(
        self, project, capsys, monkeypatch
    ):
        def _boom(cfg):
            raise RuntimeError("simulated venv failure")

        monkeypatch.setattr("venv_bat_gen.cli.create_venv", _boom)
        code = run_cli(["generate", str(project), "--entry", "main.py", "--create-venv"])
        # Script generation itself still succeeded; only venv creation failed.
        assert code == 0
        err = _strip_ansi(capsys.readouterr().err)
        assert "venv creation failed" in err
        assert "simulated venv failure" in err


# ---------------------------------------------------------------------------
# scan subcommand
# ---------------------------------------------------------------------------

class TestScanCommand:
    def test_exits_zero(self, project, capsys):
        code = run_cli(["scan", str(project)])
        assert code == 0

    def test_prints_hints(self, project, capsys):
        run_cli(["scan", str(project)])
        out = _strip_ansi(capsys.readouterr().out)
        assert "No venv" in out

    def test_reflects_custom_venv_dir(self, project, capsys):
        bindir = project / "custom_env" / "bin"
        bindir.mkdir(parents=True)
        (bindir / "python").write_text("")
        run_cli(["scan", str(project), "--venv-dir", "custom_env"])
        out = _strip_ansi(capsys.readouterr().out)
        assert "venv" in out.lower()
        assert "No venv" not in out


# ---------------------------------------------------------------------------
# presets subcommand
# ---------------------------------------------------------------------------

class TestPresetsCommand:
    def test_exits_zero(self, capsys):
        code = run_cli(["presets"])
        assert code == 0

    def test_lists_builtin_presets(self, capsys):
        run_cli(["presets"])
        out = _strip_ansi(capsys.readouterr().out)
        assert "PyQt6 Desktop App" in out
        assert "(built-in)" in out
