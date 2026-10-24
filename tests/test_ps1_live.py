# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Leon Priest (7h3v01d)
"""
Live execution of generated .ps1 scripts with PowerShell 7 (pwsh).

Runs anywhere pwsh is installed (GitHub's ubuntu/macos/windows runners all
ship it). On Linux/macOS a fake venv with a Windows-style layout
(<venv>/Scripts/python.exe as an executable shim) lets the real templates
run unmodified. Skipped when pwsh is not available.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from venv_bat_gen.core import generate_files

from conftest import make_config
from helpers import find_pwsh, make_fake_windows_layout_venv

PWSH = find_pwsh()
pytestmark = pytest.mark.skipif(PWSH is None, reason="needs PowerShell 7 (pwsh)")

ARGV_DUMP = "import sys, json; print('ARGV=' + json.dumps(sys.argv[1:])); sys.exit(int(__import__('os').environ.get('APP_EXIT', '0')))\n"


def _run(script, *args, ci=True, extra_env=None, interactive=False):
    env = {k: v for k, v in os.environ.items() if k not in {"CI", "VBG_NO_PAUSE"}}
    if ci:
        env["CI"] = "1"
    env.update(extra_env or {})
    cmd = [PWSH, "-NoProfile"] + ([] if interactive else ["-NonInteractive"])
    cmd += ["-ExecutionPolicy", "Bypass", "-File", str(script), *args] if sys.platform == "win32" \
        else ["-File", str(script), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120,
                          check=False, stdin=subprocess.DEVNULL)


def _argv(stdout: str) -> list[str]:
    line = next(ln for ln in stdout.splitlines() if ln.startswith("ARGV="))
    return json.loads(line[5:])


@pytest.fixture
def ps_project(tmp_path):
    def _make(**kw):
        d = tmp_path / kw.pop("folder", "proj")
        d.mkdir(exist_ok=True)
        cfg = make_config(d, include_powershell=True, include_test_bat=True, **kw)
        generate_files(cfg)
        if sys.platform != "win32":
            make_fake_windows_layout_venv(d, cfg.venv_dir)
        else:  # real venv on Windows
            subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(d / cfg.venv_dir)],
                           check=True)
        return d
    return _make


HOSTILE = ['C:\\out dir\\', 'R&D', '50%', '!bang!', "it's", 'a b']
# PowerShell 7 on Linux/macOS glob-expands splatted *native* arguments
# ('*.py' arrives as the matching file names); Windows PowerShell does not.
# The .ps1 variant targets Windows, so wildcards are only asserted there —
# use run.sh on POSIX, which passes them literally.
if sys.platform == "win32":
    HOSTILE.append("*.py")


def test_run_ps1_file_mode_passes_args_and_exit_code(ps_project):
    d = ps_project(project_name="Tom & Jerry's 100%", folder="Tom & Jerry (x86)")
    (d / "main.py").write_text(ARGV_DUMP)
    r = _run(d / "run.ps1", "x y", "--flag", extra_env={"APP_EXIT": "5"})
    assert r.returncode == 5, r.stdout + r.stderr
    assert _argv(r.stdout) == ["x y", "--flag"]
    assert "Tom & Jerry's 100%" in r.stdout


def test_run_ps1_runner_mode_bakes_literal_arg_vector(ps_project):
    import shlex
    d = ps_project(entry_mode="runner", app_entry="appmod", runner_args=shlex.join(HOSTILE),
                   pause_on_exit=False)
    (d / "appmod.py").write_text(ARGV_DUMP)
    r = _run(d / "run.ps1", "--extra", extra_env={"PYTHONPATH": str(d)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert _argv(r.stdout) == HOSTILE + ["--extra"]


def test_run_ps1_pause_skipped_under_ci_and_used_otherwise(ps_project):
    d = ps_project(pause_on_exit=True)
    (d / "main.py").write_text("pass\n")
    assert _run(d / "run.ps1", ci=True).returncode == 0
    # Without CI, the pause calls Read-Host; in -NonInteractive mode that is
    # an error PowerShell reports — proof the pause is really there.
    r = _run(d / "run.ps1", ci=False)
    assert "NonInteractive" in (r.stdout + r.stderr) or "Read-Host" in (r.stdout + r.stderr) \
        or "Press Enter" in r.stdout


def test_ps1_scripts_work_in_folders_with_wildcard_characters(ps_project):
    # v3.5.0 used `Set-Location -Path`, which treats [ ] as wildcards, so
    # every .ps1 failed inside a folder such as "proj [v2]".
    d = ps_project(folder="proj [v2]")
    (d / "main.py").write_text("print('RAN OK')\n")
    r = _run(d / "run.ps1")
    assert r.returncode == 0 and "RAN OK" in r.stdout, r.stdout + r.stderr


def test_run_ps1_missing_venv_exits_1(ps_project, tmp_path):
    d = ps_project()
    import shutil
    shutil.rmtree(d / ".venv")
    r = _run(d / "run.ps1")
    assert r.returncode == 1 and "Local venv not found" in r.stdout


FAKE_PY = r'''case "$*" in
  *"pip install -r"*) exit "${FAIL_REQS:-0}" ;;
  *"pip check"*) exit "${FAIL_CHECK:-0}" ;;
  *"find_spec"*) exit 0 ;;
esac
echo "$*" >> "$(dirname "$0")/../../calls.log"
exit 0
'''


@pytest.mark.skipif(sys.platform == "win32", reason="uses a sh shim for python.exe")
def test_sync_ps1_exit_code_and_pyproject_install(ps_project):
    d = ps_project()
    make_fake_windows_layout_venv(d, ".venv", FAKE_PY)
    (d / "requirements.txt").unlink()
    (d / "pyproject.toml").write_text('[project]\nname = "x"\n')
    r = _run(d / "sync.ps1")
    assert r.returncode == 0 and "SYNC COMPLETE" in r.stdout, r.stdout + r.stderr
    assert "-m pip install -e ." in (d / "calls.log").read_text()
    (d / "requirements.txt").write_text("x\n")
    r = _run(d / "sync.ps1", extra_env={"FAIL_REQS": "1"})
    assert r.returncode == 1 and "SYNC FAILED" in r.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="uses a sh shim for python.exe")
def test_doctor_ps1_exit_code(ps_project):
    d = ps_project()
    make_fake_windows_layout_venv(d, ".venv", FAKE_PY)
    (d / "main.py").write_text("")
    r = _run(d / "doctor.ps1")
    assert r.returncode == 0 and "all checks passed" in r.stdout, r.stdout + r.stderr
    (d / "main.py").unlink()
    r = _run(d / "doctor.ps1", extra_env={"FAIL_CHECK": "1"})
    assert r.returncode == 1 and "DOCTOR FOUND 2 PROBLEM(S)" in r.stdout
