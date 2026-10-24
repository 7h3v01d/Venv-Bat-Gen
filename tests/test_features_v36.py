# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Leon Priest (7h3v01d)
"""
Tests for the v3.6.0 features: the .vbg.json manifest, `update` (safe
regeneration with backups, legacy adoption, pruning), settings recovery
from older scripts, the managed .gitignore block, the smarter scanner,
input validation, CI-safe pauses, and honest sync/doctor exit codes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from venv_bat_gen import cli
from venv_bat_gen.core import (
    MANIFEST_NAME,
    ManifestError,
    config_problem,
    fingerprint,
    gitignore_entries,
    infer_settings_from_scripts,
    make_doctor_sh,
    make_run_sh,
    make_sync_sh,
    read_manifest,
    scan_project_folder,
    update_gitignore,
    venv_dir_problem,
)

from conftest import make_config
from helpers import make_fake_posix_venv

FIXTURES = Path(__file__).parent / "fixtures"
BASH = "/bin/bash" if Path("/bin/bash").exists() else None
needs_bash = pytest.mark.skipif(BASH is None or sys.platform == "win32", reason="needs POSIX bash")


def run_cli(argv) -> int:
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    return e.value.code


@pytest.fixture
def proj(tmp_path) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    (p / "main.py").write_text("print('hi')\n")
    return p


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class TestManifest:
    def test_cli_generate_writes_manifest_with_settings_and_hashes(self, proj, capsys):
        assert run_cli(["generate", str(proj), "--entry", "main.py", "--posix", "--test"]) == 0
        data = json.loads((proj / MANIFEST_NAME).read_text())
        assert data["generator"] == "venv-bat-gen" and data["schema"] == 1
        assert data["settings"]["include_posix"] is True
        assert data["settings"]["include_test_bat"] is True
        assert "overwrite_existing" not in data["settings"]       # write-behaviour, not content
        assert set(data["files"]) >= {"run.bat", "run.sh", "test.sh"}
        assert data["files"]["run.bat"] == fingerprint((proj / "run.bat").read_text())

    def test_no_manifest_flag(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py", "--no-manifest"])
        assert not (proj / MANIFEST_NAME).exists()

    def test_fingerprint_ignores_timestamp_line_endings_and_bom(self):
        a = "rem  Generated on: 2020-01-01 00:00\nrem x\n"
        b = "\ufeffrem  Generated on: 2031-12-31 23:59\r\nrem x\r\n"
        assert fingerprint(a) == fingerprint(b)
        assert fingerprint(a) != fingerprint(a + "echo changed\n")

    @pytest.mark.parametrize("content,match", [
        ("{not json", "could not be read"),
        ('{"generator": "something-else", "schema": 1, "settings": {}}', "not a venv-bat-gen"),
        ('{"generator": "venv-bat-gen", "schema": 99, "settings": {}}', "schema 99"),
        ('{"generator": "venv-bat-gen", "schema": 1, "settings": {"use_uv": "yes"}}', "use_uv"),
        ('{"generator": "venv-bat-gen", "schema": 1, "settings": {}, "files": [1]}', "files"),
    ])
    def test_invalid_manifest_fails_closed(self, tmp_path, content, match):
        (tmp_path / MANIFEST_NAME).write_text(content)
        with pytest.raises(ManifestError, match=match):
            read_manifest(tmp_path)

    def test_cli_reports_invalid_manifest_instead_of_ignoring_it(self, proj, capsys):
        (proj / MANIFEST_NAME).write_text("{oops")
        assert run_cli(["check", str(proj)]) == 1
        assert "could not be read" in capsys.readouterr().err

    def test_check_uses_manifest_with_no_flags_on_any_platform(self, proj, capsys):
        with mock.patch.object(sys, "platform", "win32"):
            assert run_cli(["generate", str(proj), "--runner", "--entry", "uvicorn",
                            "--runner-args", "app:app --port 8000", "--uv", "--powershell",
                            "--name", "Svc"]) == 0
        for plat in ("linux", "darwin", "win32"):
            with mock.patch.object(sys, "platform", plat):
                assert run_cli(["check", str(proj)]) == 0, plat

    def test_cli_flag_overrides_manifest(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py", "--posix"])
        capsys.readouterr()
        assert run_cli(["check", str(proj), "--no-posix"]) == 0
        out = capsys.readouterr().out
        assert "run.sh" not in out

    def test_generate_reuses_manifest_settings(self, proj, capsys):
        run_cli(["generate", str(proj), "--module", "--entry", "mypkg", "--venv-dir", "venv311"])
        assert run_cli(["generate", str(proj), "--overwrite"]) == 0
        assert 'set "VENV_DIR=venv311"' in (proj / "run.bat").read_text()
        assert 'set "ENTRY_MODE=module"' in (proj / "run.bat").read_text()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_refreshes_untouched_files_and_backs_them_up(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py"])
        old_run = (proj / "run.bat").read_bytes()
        assert run_cli(["update", str(proj), "--no-pause"]) == 0
        assert "%VBG_PAUSE%\r\nexit /b %EXITCODE%" not in (proj / "run.bat").read_text(newline="")
        backups = list((proj / ".vbg-backup").iterdir())
        assert len(backups) == 1 and (backups[0] / "run.bat").read_bytes() == old_run
        assert read_manifest(proj).settings["pause_on_exit"] is False

    def test_never_clobbers_hand_edits_without_force(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py"])
        edited = (proj / "doctor.bat").read_text() + "rem my local tweak\n"
        (proj / "doctor.bat").write_text(edited)
        assert run_cli(["update", str(proj), "--webengine"]) == 1  # doctor would change
        assert (proj / "doctor.bat").read_text() == edited
        out = capsys.readouterr().out
        assert "doctor.bat" in out and "edited since last generate" in out
        # still flagged as edited on the next run (old hash kept)
        assert run_cli(["update", str(proj), "--webengine"]) == 1

    def test_force_overwrites_hand_edits_with_backup(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py"])
        (proj / "doctor.bat").write_text("rem mine\n")
        assert run_cli(["update", str(proj), "--webengine", "--force"]) == 0
        assert "WebEngine" in (proj / "doctor.bat").read_text()
        (backup,) = (proj / ".vbg-backup").iterdir()
        assert (backup / "doctor.bat").read_text() == "rem mine\n"

    def test_foreign_file_is_reported_as_not_ours(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py"])
        (proj / "sync.bat").write_text("@echo off\nrem written by hand\n")
        assert run_cli(["update", str(proj), "--uv"]) == 1
        assert "not generated by venv-bat-gen" in capsys.readouterr().out

    def test_dry_run_writes_nothing(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py"])
        before = {p.name: p.read_bytes() for p in proj.iterdir()}
        assert run_cli(["update", str(proj), "--uv", "--dry-run"]) == 0
        assert {p.name: p.read_bytes() for p in proj.iterdir()} == before
        assert "would change" in capsys.readouterr().out

    def test_prune_removes_only_untouched_stale_files(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py", "--posix"])
        (proj / "sync.sh").write_text((proj / "sync.sh").read_text() + "# edited\n")
        assert run_cli(["update", str(proj), "--no-posix"]) == 0
        assert (proj / "run.sh").exists()            # stale, kept without --prune
        assert run_cli(["update", str(proj), "--no-posix", "--prune"]) == 0
        assert not (proj / "run.sh").exists()        # untouched -> pruned (backed up)
        assert (proj / "sync.sh").exists()           # edited -> left alone
        assert any((b / "run.sh").exists() for b in (proj / ".vbg-backup").iterdir())

    def test_nothing_to_update(self, proj, capsys):
        assert run_cli(["update", str(proj)]) == 1
        assert "generate" in capsys.readouterr().err

    def test_self_unpack_project_round_trip(self, proj, capsys):
        run_cli(["generate", str(proj), "--entry", "main.py", "--self-unpack", "--posix"])
        assert run_cli(["update", str(proj)]) == 0
        assert run_cli(["check", str(proj)]) == 0


# ---------------------------------------------------------------------------
# Legacy adoption (real v3.5.0 output in tests/fixtures/v350_project)
# ---------------------------------------------------------------------------

EXPECTED_V350 = {
    "project_name": "R&D Tool 100%", "venv_dir": "venv311", "entry_mode": "runner",
    "app_entry": "uvicorn", "runner_args": "app.main:app --name 'My App' --port 8000",
    "include_webengine_check": True, "pause_on_exit": False, "include_test_bat": True,
    "use_uv": True, "include_posix": True, "include_powershell": True,
    "include_setup": False, "self_unpack": False,
}


@pytest.fixture
def legacy(tmp_path) -> Path:
    dst = tmp_path / "legacy"
    shutil.copytree(FIXTURES / "v350_project", dst)
    return dst


class TestLegacyAdoption:
    def test_settings_recovered_from_v350_scripts(self, legacy):
        assert infer_settings_from_scripts(legacy) == EXPECTED_V350

    def test_recovered_settings_round_trip_for_v36_output(self, tmp_path, capsys):
        for kw in (dict(), dict(use_uv=True, include_posix=True, include_test_bat=True),
                   dict(entry_mode="script", app_entry="my-tool", runner_args="serve --x 'a b'",
                        include_powershell=True, pause_on_exit=False, project_name="It's 50%"),
                   dict(self_unpack=True, include_posix=True, include_powershell=True,
                        include_webengine_check=True)):
            d = tmp_path / f"p{len(list(tmp_path.iterdir()))}"
            cfg = make_config(d, **kw)
            from venv_bat_gen.core import MANIFEST_SETTINGS, generate_files
            generate_files(cfg)
            want = {k: getattr(cfg, k) for k in MANIFEST_SETTINGS}
            assert infer_settings_from_scripts(d) == want, kw

    def test_check_on_legacy_project_needs_no_flags(self, legacy, capsys):
        # every file drifts (new templates), but nothing is "missing": the
        # settings — including posix/powershell/test — were recovered.
        assert run_cli(["check", str(legacy)]) == 1
        out = capsys.readouterr().out
        assert "recovered from existing scripts" in out
        assert "missing" not in out and "drifted" in out

    def test_update_without_adopt_refuses(self, legacy, capsys):
        before = {p.name: p.read_bytes() for p in legacy.iterdir()}
        assert run_cli(["update", str(legacy)]) == 1
        assert {p.name: p.read_bytes() for p in legacy.iterdir() if p.name != MANIFEST_NAME} == before
        assert "--adopt" in capsys.readouterr().out

    def test_update_adopt_upgrades_everything_and_backs_up(self, legacy, capsys):
        assert run_cli(["update", str(legacy), "--adopt"]) == 0
        assert "v3.6.0" in (legacy / "run.bat").read_text()
        (backup,) = (legacy / ".vbg-backup").iterdir()
        assert len(list(backup.iterdir())) == 18
        assert read_manifest(legacy).settings == EXPECTED_V350
        assert run_cli(["check", str(legacy)]) == 0


# ---------------------------------------------------------------------------
# .gitignore managed block
# ---------------------------------------------------------------------------

class TestGitignore:
    def test_self_unpack_gitignore_block(self, proj, capsys):
        (proj / ".gitignore").write_text("*.log\n")
        assert run_cli(["generate", str(proj), "--self-unpack", "--test", "--gitignore"]) == 0
        text = (proj / ".gitignore").read_text()
        assert text.startswith("*.log\n")
        for line in ("/.venv/", "/.vbg-backup/", "/run.bat", "/test.bat"):
            assert line + "\n" in text

    def test_block_is_idempotent_and_refreshed_in_place(self, tmp_path):
        cfg = make_config(tmp_path, self_unpack=True)
        assert update_gitignore(tmp_path, gitignore_entries(cfg)) is True
        assert update_gitignore(tmp_path, gitignore_entries(cfg)) is False
        (tmp_path / ".gitignore").write_text((tmp_path / ".gitignore").read_text() + "user-after\n")
        cfg2 = make_config(tmp_path, self_unpack=True, include_posix=True)
        assert update_gitignore(tmp_path, gitignore_entries(cfg2)) is True
        text = (tmp_path / ".gitignore").read_text()
        assert text.count("venv-bat-gen (managed block") == 1
        assert "/run.sh\n" in text and text.endswith("user-after\n")

    def test_update_refreshes_existing_block(self, proj, capsys):
        run_cli(["generate", str(proj), "--self-unpack", "--gitignore"])
        run_cli(["update", str(proj), "--posix"])
        assert "/run.sh\n" in (proj / ".gitignore").read_text()


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class TestScanner:
    def test_finds_venv_under_another_name(self, tmp_path):
        (tmp_path / "venv311").mkdir()
        (tmp_path / "venv311" / "pyvenv.cfg").write_text("home = x\n")
        (tmp_path / "data").mkdir()
        scan = scan_project_folder(tmp_path)
        assert scan.suggested_venv_dir == "venv311"
        assert scan.venv_found is False

    def test_prefers_conventional_venv_names(self, tmp_path):
        for name in ("zz_env", "venv"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "pyvenv.cfg").write_text("")
        assert scan_project_folder(tmp_path).suggested_venv_dir == "venv"

    def test_cli_generate_uses_discovered_venv(self, tmp_path, capsys):
        (tmp_path / "env").mkdir()
        (tmp_path / "env" / "pyvenv.cfg").write_text("")
        assert run_cli(["generate", str(tmp_path), "--no-requirements"]) == 0
        assert 'set "VENV_DIR=env"' in (tmp_path / "run.bat").read_text()

    def test_src_layout_main_package_suggests_module(self, tmp_path):
        (tmp_path / "src" / "mytool").mkdir(parents=True)
        (tmp_path / "src" / "mytool" / "__main__.py").write_text("")
        scan = scan_project_folder(tmp_path)
        assert (scan.suggested_entry_mode, scan.suggested_app_entry) == ("module", "mytool")
        assert any("src layout" in h for h in scan.hints)

    def test_main_package_beats_entry_file_and_cli_guess(self, tmp_path):
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__main__.py").write_text("")
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\ndependencies=["typer"]\n')
        scan = scan_project_folder(tmp_path)
        assert (scan.suggested_entry_mode, scan.suggested_app_entry) == ("module", "pkg")

    def test_invalid_pyproject_is_reported_not_fatal(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project\nname=")
        scan = scan_project_folder(tmp_path)
        assert any("could not be parsed" in h for h in scan.hints)

    def test_reports_manifest_and_installability(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / MANIFEST_NAME).write_text("{}")
        scan = scan_project_folder(tmp_path)
        assert scan.manifest_found and scan.pyproject_installable

    def test_scan_json(self, tmp_path, capsys):
        (tmp_path / "main.py").write_text("")
        assert run_cli(["scan", str(tmp_path), "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["suggested_app_entry"] == "main.py"

    def test_no_requirements_stub_for_installable_pyproject(self, tmp_path, capsys):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "main.py").write_text("")
        run_cli(["generate", str(tmp_path)])
        assert not (tmp_path / "requirements.txt").exists()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    @pytest.mark.parametrize("bad", ["", "C:\\venvs\\x", "/abs/venv", "../outside", "a/../../b",
                                     'q"uote', "50%", "bang!", "a&b", "new\nline"])
    def test_bad_venv_dirs(self, bad):
        assert venv_dir_problem(bad) is not None

    @pytest.mark.parametrize("good", [".venv", "venv", "envs/py311", "My Venv", "venv-3.11"])
    def test_good_venv_dirs(self, good):
        assert venv_dir_problem(good) is None

    def test_cli_rejects_bad_venv_dir(self, proj, capsys):
        assert run_cli(["generate", str(proj), "--venv-dir", "..\\shared"]) == 1
        assert "inside the project" in capsys.readouterr().err
        assert not (proj / "run.bat").exists()

    def test_project_name_newline_rejected(self, tmp_path):
        assert config_problem(make_config(tmp_path, project_name="a\nb")) is not None

    def test_file_entry_with_quote_rejected(self, tmp_path):
        assert config_problem(make_config(tmp_path, app_entry='ma"in.py')) is not None


# ---------------------------------------------------------------------------
# Console output must never crash (Windows redirected stdout = cp1252)
# ---------------------------------------------------------------------------

def test_cli_survives_cp1252_redirected_output(tmp_path):
    (tmp_path / "main.py").write_text("")
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    for argv in (["scan", str(tmp_path)], ["generate", str(tmp_path)], ["check", str(tmp_path)]):
        r = subprocess.run([sys.executable, "-m", "venv_bat_gen", *argv], capture_output=True,
                           env=env, check=False)
        assert b"UnicodeEncodeError" not in r.stderr, argv
        assert r.returncode == 0, (argv, r.stderr)


@needs_bash
def test_cli_output_piped_into_head_exits_quietly(tmp_path):
    cp = tmp_path / "proj"
    shutil.copytree(FIXTURES / "v350_project", cp)
    r = subprocess.run([BASH, "-c", f'"{sys.executable}" -m venv_bat_gen update "{cp}" --dry-run | head -1'],
                       capture_output=True, text=True, check=False)
    assert "Traceback" not in r.stderr and "BrokenPipeError" not in r.stderr


# ---------------------------------------------------------------------------
# Live POSIX behaviour: exit codes, pyproject install, CI-safe pauses
# ---------------------------------------------------------------------------

FAKE_PY_LOGGING = '''LOG="$(dirname "$0")/../../calls.log"
echo "$*" >> "$LOG"
case "$*" in
  *"pip install -r"*) exit "${FAIL_REQS:-0}" ;;
  *"pip install -e ."*) exit 0 ;;
  *"pip check"*) exit "${FAIL_CHECK:-0}" ;;
  *"find_spec"*) exit "${FAIL_SPEC:-0}" ;;
esac
exit 0
'''


@needs_bash
class TestPosixLiveBehaviour:
    def _write(self, cfg, maker, name):
        (cfg.project_dir / name).write_text(maker(cfg))
        return cfg.project_dir / name

    def test_sync_sh_fails_loudly_when_install_fails(self, tmp_path):
        cfg = make_config(tmp_path, include_posix=True)
        script = self._write(cfg, make_sync_sh, "sync.sh")
        make_fake_posix_venv(tmp_path, python_script=FAKE_PY_LOGGING)
        (tmp_path / "requirements.txt").write_text("nope\n")
        ok = subprocess.run([BASH, str(script)], capture_output=True, text=True, check=False)
        assert ok.returncode == 0 and "SYNC COMPLETE" in ok.stdout
        bad = subprocess.run([BASH, str(script)], capture_output=True, text=True, check=False,
                             env=dict(os.environ, FAIL_REQS="1"))
        assert bad.returncode == 1 and "SYNC FAILED" in bad.stdout

    def test_sync_sh_installs_pyproject_project_when_no_requirements(self, tmp_path):
        cfg = make_config(tmp_path, include_posix=True)
        script = self._write(cfg, make_sync_sh, "sync.sh")
        make_fake_posix_venv(tmp_path, python_script=FAKE_PY_LOGGING)
        (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nline-length = 100\n')
        subprocess.run([BASH, str(script)], capture_output=True, check=False)
        assert "install -e ." not in (tmp_path / "calls.log").read_text()  # tool-only pyproject
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        subprocess.run([BASH, str(script)], capture_output=True, check=False)
        assert "-m pip install -e ." in (tmp_path / "calls.log").read_text()

    def test_doctor_sh_exit_code_reflects_failures(self, tmp_path):
        cfg = make_config(tmp_path, include_posix=True)
        script = self._write(cfg, make_doctor_sh, "doctor.sh")
        make_fake_posix_venv(tmp_path, python_script=FAKE_PY_LOGGING)
        (tmp_path / "main.py").write_text("")
        good = subprocess.run([BASH, str(script)], capture_output=True, text=True, check=False)
        assert good.returncode == 0 and "all checks passed" in good.stdout
        (tmp_path / "main.py").unlink()
        bad = subprocess.run([BASH, str(script)], capture_output=True, text=True, check=False)
        assert bad.returncode == 1 and "PROBLEM(S)" in bad.stdout
        broken = subprocess.run([BASH, str(script)], capture_output=True, text=True, check=False,
                                env=dict(os.environ, FAIL_CHECK="1"))
        assert "DOCTOR FOUND 2 PROBLEM(S)" in broken.stdout

    def test_doctor_sh_uv_mode_does_not_need_pip(self, tmp_path):
        content = make_doctor_sh(make_config(tmp_path, use_uv=True))
        assert "-m pip" not in content
        assert 'uv pip check --python "$PY"' in content

    @pytest.mark.parametrize("ci", [False, True])
    def test_run_sh_pause_only_for_humans(self, tmp_path, ci):
        import pty
        import select
        import time
        cfg = make_config(tmp_path, include_posix=True, pause_on_exit=True)
        script = self._write(cfg, make_run_sh, "run.sh")
        make_fake_posix_venv(tmp_path)
        (tmp_path / "main.py").write_text("")
        env = {k: v for k, v in os.environ.items() if k not in {"CI", "VBG_NO_PAUSE"}}
        if ci:
            env["CI"] = "true"
        pid, fd = pty.fork()
        if pid == 0:  # child: run the script on a real terminal
            os.execve(BASH, [BASH, str(script)], env)
        out, deadline = b"", time.time() + 20
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    chunk = os.read(fd, 1024)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk
                if b"Press Enter" in out:
                    os.write(fd, b"\n")
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
        assert (b"Press Enter" in out) is (not ci)


def test_uv_sync_targets_custom_venv_dir(tmp_path):
    uv = shutil.which("uv")
    if not uv or BASH is None or sys.platform == "win32":
        pytest.skip("needs uv + bash")
    cfg = make_config(tmp_path, include_posix=True, use_uv=True, venv_dir="venv311")
    (tmp_path / "sync.sh").write_text(make_sync_sh(cfg))
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1"\nrequires-python = ">=3.8"\ndependencies = []\n')
    r = subprocess.run([BASH, str(tmp_path / "sync.sh")], capture_output=True, text=True,
                       check=False, env=dict(os.environ, UV_OFFLINE="1", UV_PYTHON=sys.executable))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "venv311" / "pyvenv.cfg").exists()
    assert not (tmp_path / ".venv").exists()


# ---------------------------------------------------------------------------
# Remaining main-path coverage
# ---------------------------------------------------------------------------

def test_update_recreates_a_deleted_script(proj, capsys):
    run_cli(["generate", str(proj), "--entry", "main.py"])
    (proj / "doctor.bat").unlink()
    assert run_cli(["update", str(proj)]) == 0
    assert (proj / "doctor.bat").exists()
    assert "create" in capsys.readouterr().out


def test_generate_files_rejects_invalid_config_and_writes_nothing(tmp_path):
    from venv_bat_gen.core import generate_files
    with pytest.raises(ValueError, match="inside the project"):
        generate_files(make_config(tmp_path, venv_dir="../shared"))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kw,match", [
    (dict(project_name="  "), "Project name cannot be empty"),
    (dict(entry_mode="banana"), "Unknown entry mode"),
    (dict(app_entry=" "), "Entry value is required"),
])
def test_config_problem_messages(tmp_path, kw, match):
    assert match in (config_problem(make_config(tmp_path, **kw)) or "")


def test_corrupt_embedded_payload_reads_as_drift_not_crash(tmp_path):
    from venv_bat_gen.core import check_drift, generate_files
    cfg = make_config(tmp_path, self_unpack=True)
    generate_files(cfg)
    setup = tmp_path / "setup.bat"
    lines = setup.read_text().splitlines(keepends=True)
    i = next(n for n, ln in enumerate(lines) if ln.strip().startswith("echo ") and
             len(ln.strip()) > 60)
    lines[i] = "        echo AAAA" + "=" * 3 + "A\n"  # invalid base64 (padding mid-string)
    setup.write_text("".join(lines))
    (entry,) = check_drift(cfg)
    assert entry.status == "drifted"
    assert infer_settings_from_scripts(tmp_path)["self_unpack"] is True
