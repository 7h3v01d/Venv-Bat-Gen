# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Leon Priest (7h3v01d)
"""
Windows-only live tests: run the generated .bat scripts with the real
cmd.exe, and the .ps1 scripts with the real Windows PowerShell 5.1.

These cover what no other platform can: cmd.exe's parsing of names and
paths containing & ( ) ! % ^, the batch → CRT argv round trip, the
certutil self-unpack, and PS 5.1's ANSI decoding + legacy argument
passing. They run in CI on windows-latest and locally via test.bat.
Each test builds a real venv (python -m venv --without-pip, ~1–2 s).
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from venv_bat_gen.core import file_bytes, generate_files, make_run_bat

from conftest import make_config

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

ARGV_DUMP = ("import sys, json; print('ARGV=' + json.dumps(sys.argv[1:]));"
             " sys.exit(int(__import__('os').environ.get('APP_EXIT', '0')))\n")

# Folder and project names that break unquoted cmd.exe expansions.
HOSTILE_FOLDER = "Tom & Jerry (x86) 100%"
HOSTILE_NAME = "R&D (Tom's) 100%"
HOSTILE_ARGS = ["C:\\out dir\\", "C:\\nospace\\", "R&D", "50%", "!bang!", "^caret",
                "a|b", "<lt>", "*.py", "it's", "(paren)"]


def _env(**extra) -> dict:
    env = dict(os.environ, CI="1", PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    env.update(extra)
    return env


def _cmd(script: Path, *args: str, **env):
    """Run a .bat through cmd.exe exactly as a user typing it would.

    The command line is built by hand (a str, not a list) because Python's
    list quoting escapes quotes as \\" which cmd.exe does not understand.
    /s /c "..." makes cmd strip only the outer quote pair. The script is
    referenced by name from its own folder, so hostile folder names (& ( ) %)
    never appear on the command line itself. Args must not contain quotes.
    """
    quoted = "".join(f' "{a}"' for a in args)
    line = f'cmd.exe /d /s /c ""{script.name}"{quoted}"'
    return subprocess.run(line, capture_output=True, text=True, env=_env(**env),
                          timeout=300, check=False, cwd=script.parent)


def _ps51(script: Path, *args: str, **env):
    exe = shutil.which("powershell") or "powershell.exe"
    return subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-File", str(script), *args], capture_output=True, text=True,
                          env=_env(**env), timeout=180, check=False)


def _argv(stdout: str) -> list[str]:
    line = next(ln for ln in stdout.splitlines() if ln.startswith("ARGV="))
    return json.loads(line[5:])


@pytest.fixture
def project(tmp_path):
    def _make(folder=HOSTILE_FOLDER, **kw):
        d = tmp_path / folder
        d.mkdir()
        cfg = make_config(d, **{"project_name": HOSTILE_NAME, "pause_on_exit": True, **kw})
        generate_files(cfg)
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(d / cfg.venv_dir)],
                       check=True)
        return d, cfg
    return _make


def test_run_bat_file_mode_hostile_folder_and_name(project):
    d, _ = project(include_test_bat=True)
    (d / "main.py").write_text(ARGV_DUMP)
    r = _cmd(d / "run.bat", "x y", "R&D", APP_EXIT="4")
    assert r.returncode == 4, r.stdout + r.stderr
    assert _argv(r.stdout) == ["x y", "R&D"]
    assert HOSTILE_NAME in r.stdout
    assert "is not recognized" not in r.stderr


def test_run_bat_runner_args_reach_python_exactly(project):
    d, _ = project(entry_mode="runner", app_entry="appmod",
                   runner_args=shlex.join(HOSTILE_ARGS), pause_on_exit=False)
    (d / "appmod.py").write_text(ARGV_DUMP)
    r = _cmd(d / "run.bat", PYTHONPATH=str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    assert _argv(r.stdout) == HOSTILE_ARGS


def test_doctor_bat_exit_codes(project):
    d, _ = project()
    (d / "main.py").write_text("")
    # pip is not installed in the --without-pip venv, so pip check fails:
    # doctor must report that rather than exit 0.
    r = _cmd(d / "doctor.bat")
    assert r.returncode == 1 and "PROBLEM" in r.stdout, r.stdout + r.stderr
    assert "is not recognized" not in r.stderr


def test_sync_bat_fails_when_install_fails(project):
    d, _ = project()
    (d / "requirements.txt").write_text("this-package-does-not-exist-vbg==0.0.0\n")
    r = _cmd(d / "sync.bat")
    assert r.returncode == 1 and "SYNC FAILED" in r.stdout, r.stdout + r.stderr


def test_shell_bat_and_test_bat_parse_cleanly(project):
    d, _ = project(include_test_bat=True)
    r = _cmd(d / "test.bat")  # pytest isn't installed in the venv -> non-zero, but no syntax error
    assert "TESTS FAILED" in r.stdout and "was unexpected at this time" not in r.stderr


def test_self_unpack_setup_bat_writes_byte_identical_companions(tmp_path):
    d = tmp_path / HOSTILE_FOLDER
    d.mkdir()
    cfg = make_config(d, project_name="Yahoo! R&D", self_unpack=True, include_posix=True,
                      include_powershell=True, include_test_bat=True)
    generate_files(cfg)
    r = _cmd(d / "setup.bat")
    assert "[FAIL]" not in r.stdout, r.stdout + r.stderr
    assert 'set "PROJECT_NAME=Yahoo! R&D"' in (d / "run.bat").read_text()
    from venv_bat_gen.core import _MAKERS, companion_names, normalize_content
    for name in companion_names(cfg):
        on_disk = (d / name).read_bytes()
        assert normalize_content(on_disk.decode("utf-8")) == \
            normalize_content(file_bytes(name, _MAKERS[name](cfg)).decode("utf-8")), name
        if name.endswith(".ps1"):
            assert on_disk.startswith(b"\xef\xbb\xbf")
    assert "is not recognized" not in r.stderr


def test_every_ps1_parses_in_real_windows_powershell_51(tmp_path):
    cfg = make_config(tmp_path, project_name="Café — R&D", include_powershell=True,
                      include_test_bat=True, include_setup=True, include_webengine_check=True)
    generate_files(cfg)
    exe = shutil.which("powershell") or "powershell.exe"
    for ps1 in tmp_path.glob("*.ps1"):
        cmd = ("$t=$null;$e=$null;[void][System.Management.Automation.Language.Parser]::"
               f"ParseFile('{ps1}',[ref]$t,[ref]$e);$e.Count")
        r = subprocess.run([exe, "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                           check=False)
        assert r.stdout.strip() == "0", (ps1.name, r.stdout, r.stderr)


def test_run_ps1_in_windows_powershell_51_passes_args_exactly(project):
    args = ["C:\\out dir\\", "", "R&D", "a b"]
    d, _ = project(include_powershell=True, entry_mode="runner", app_entry="appmod",
                   runner_args=" ".join(f"'{a}'" for a in args), pause_on_exit=False)
    (d / "appmod.py").write_text(ARGV_DUMP)
    r = _ps51(d / "run.ps1", PYTHONPATH=str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    assert _argv(r.stdout) == args


def test_run_bat_is_crlf_and_has_no_delayed_expansion():
    content = file_bytes("run.bat", make_run_bat(make_config(Path("."))))
    assert b"\r\n" in content and b"EnableDelayedExpansion" not in content
