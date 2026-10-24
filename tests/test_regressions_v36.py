# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Leon Priest (7h3v01d)
"""
Regression tests for bugs found in the v3.5.0 audit and fixed in v3.6.0.

Each test here was written first and run against the unmodified v3.5.0
code to confirm it fails, then the fix was applied. They deliberately use
only APIs that already existed in v3.5.0.
"""

from __future__ import annotations

import datetime as _dt
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from unittest import mock

import pytest

from venv_bat_gen import cli, core
from venv_bat_gen.core import (
    PresetManager,
    _bat_arg_vector,
    build_previews,
    check_drift,
    generate_files,
    make_run_ps1,
    make_run_sh,
    make_self_unpacking_setup_bat,
    make_shell_sh,
    scan_project_folder,
)

from conftest import make_config
from helpers import (
    find_pwsh,
    make_fake_posix_venv,
    ps51_decode,
    ps_parse_errors,
    unquoted_bat_refs,
    windows_argv,
)

BASH = "/bin/bash" if Path("/bin/bash").exists() else None
needs_bash = pytest.mark.skipif(BASH is None or sys.platform == "win32",
                                reason="needs a POSIX bash")
PWSH = find_pwsh()
needs_pwsh = pytest.mark.skipif(PWSH is None, reason="needs PowerShell 7 (pwsh)")

ALL_FAMILIES = dict(include_posix=True, include_powershell=True,
                    include_test_bat=True, include_webengine_check=True)


def _all_configs(tmp_path):
    """A spread of configs covering every template branch."""
    out = []
    for mode, entry, args in (("file", "main.py", ""), ("module", "pkg", ""),
                              ("runner", "uvicorn", "app:app --port 8000"),
                              ("script", "my-tool", "serve")):
        for uv in (False, True):
            for setup in (False, True):
                out.append(make_config(tmp_path, entry_mode=mode, app_entry=entry,
                                       runner_args=args, use_uv=uv, include_setup=setup,
                                       **ALL_FAMILIES))
    return out


# ---------------------------------------------------------------------------
# 1. PowerShell scripts must survive Windows PowerShell 5.1's ANSI decoding
# ---------------------------------------------------------------------------

class TestPs1Encoding:
    def test_ps1_files_are_written_with_utf8_bom(self, cfg_factory):
        cfg = cfg_factory(include_powershell=True, include_test_bat=True, include_setup=True)
        for path in generate_files(cfg):
            if path.suffix == ".ps1":
                assert path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name

    def test_non_ascii_project_name_survives_ps51_decoding(self, cfg_factory):
        name = "Café Ünïcode Tool"
        cfg = cfg_factory(project_name=name, include_powershell=True)
        generate_files(cfg)
        text = ps51_decode((cfg.project_dir / "run.ps1").read_bytes())
        assert f"$PROJECT_NAME = '{name}'" in text

    @needs_pwsh
    def test_every_ps1_parses_as_windows_powershell_51_would_read_it(self, tmp_path):
        failures = {}
        for i, cfg in enumerate(_all_configs(tmp_path / "p")):
            cfg = replace(cfg, project_dir=tmp_path / f"p{i}", project_name="Café — Demo")
            for path in generate_files(cfg):
                if path.suffix != ".ps1":
                    continue
                errs = ps_parse_errors(PWSH, ps51_decode(path.read_bytes()), tmp_path)
                if errs:
                    failures[f"{i}:{path.name}"] = errs
        assert not failures, failures

    def test_self_unpack_embeds_ps1_with_bom(self, cfg_factory):
        import base64
        import re
        cfg = cfg_factory(self_unpack=True, include_powershell=True)
        content = make_self_unpacking_setup_bat(cfg)
        start = content.index('set "OUTFILE=run.ps1"')
        block = content[start:content.find("rem ── ", start + 1)]
        b64 = "".join(ln for ln in re.findall(r"^\s*echo (\S+)\s*$", block, re.M)
                      if re.fullmatch(r"[A-Za-z0-9+/=]+", ln))
        assert base64.b64decode(b64).startswith(b"\xef\xbb\xbf")


# ---------------------------------------------------------------------------
# 2. .bat echo lines must not expand names/paths outside quotes
# ---------------------------------------------------------------------------

class TestBatEchoQuoting:
    def test_no_risky_unquoted_expansions_in_any_bat(self, tmp_path):
        problems = {}
        for i, cfg in enumerate(_all_configs(tmp_path)):
            for name, content in build_previews(cfg).items():
                if name.endswith(".bat"):
                    bad = unquoted_bat_refs(content)
                    if bad:
                        problems[f"{i}:{name}"] = bad
            su = make_self_unpacking_setup_bat(replace(cfg, include_setup=False, self_unpack=True))
            bad = unquoted_bat_refs(su)
            if bad:
                problems[f"{i}:self-unpack setup.bat"] = bad
        assert not problems, problems

    def test_self_unpack_does_not_enable_delayed_expansion(self, cfg_factory):
        # With delayed expansion on, every '!' in a %-expanded value (e.g. a
        # project called "Yahoo!") is consumed by cmd.exe.
        content = make_self_unpacking_setup_bat(cfg_factory(self_unpack=True, project_name="Yahoo!"))
        assert "enabledelayedexpansion" not in content.lower()
        assert 'set "PROJECT_NAME=Yahoo!"' in content


# ---------------------------------------------------------------------------
# 3. Runner args ending in a backslash (Windows directory paths)
# ---------------------------------------------------------------------------

class TestBatArgVectorRoundTrip:
    @pytest.mark.parametrize("args", [
        [r"C:\out dir" + "\\"],
        [r"C:\nospace" + "\\"],
        ["x\\\\"],
        [r"a\b", r"c d\e"],
        ["50%", "R&D", "a|b", "!bang!", "^caret", "<lt>"],
        ["--include", "*.py"],
    ])
    def test_python_receives_exact_argv(self, args):
        vector = _bat_arg_vector(args)
        # cmd.exe's only rewrite inside double quotes in a batch file is %% -> %
        cmdline = vector.replace("%%", "%")
        assert windows_argv(cmdline) == args


# ---------------------------------------------------------------------------
# 4. POSIX: pause, shell rcfile
# ---------------------------------------------------------------------------

@needs_bash
class TestPosixLive:
    def test_run_sh_pause_does_not_clobber_exit_code_when_stdin_is_closed(self, cfg_factory):
        cfg = cfg_factory(include_posix=True, pause_on_exit=True)
        (cfg.project_dir / "run.sh").write_text(make_run_sh(cfg))
        (cfg.project_dir / "main.py").write_text("import sys; sys.exit(0)\n")
        make_fake_posix_venv(cfg.project_dir)
        r = subprocess.run([BASH, str(cfg.project_dir / "run.sh")],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stdout + r.stderr

    def test_run_sh_pause_preserves_nonzero_exit_code(self, cfg_factory):
        cfg = cfg_factory(include_posix=True, pause_on_exit=True)
        (cfg.project_dir / "run.sh").write_text(make_run_sh(cfg))
        (cfg.project_dir / "main.py").write_text("import sys; sys.exit(7)\n")
        make_fake_posix_venv(cfg.project_dir)
        r = subprocess.run([BASH, str(cfg.project_dir / "run.sh")],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
        assert r.returncode == 7

    @pytest.mark.parametrize("name,folder,label", [
        ("Plain", "plain", "Plain"),
        ("Leon's App", "Leon's tools", "Leon's App"),
        # PS1 is re-expanded every time the prompt is drawn, so $ ` \ are
        # dropped from the prompt label (the banner still shows the full name).
        ('Odd $(touch PWNED) `x` "q"', "dollar $HOME dir", 'Odd (touch PWNED) x "q"'),
    ])
    def test_shell_sh_rcfile_activates_and_sets_prompt(self, tmp_path, name, folder, label):
        project = tmp_path / folder
        project.mkdir()
        cfg = make_config(project, project_name=name, include_posix=True)
        (project / "shell.sh").write_text(make_shell_sh(cfg))
        make_fake_posix_venv(project)

        # Put a fake `bash` first on PATH that dumps the rcfile it was given.
        fakebin = tmp_path / "fakebin"
        fakebin.mkdir()
        fake = fakebin / "bash"
        fake.write_text('#!/bin/sh\nwhile [ $# -gt 0 ]; do\n'
                        '  if [ "$1" = "--rcfile" ]; then cat "$2"; exit 0; fi\n'
                        '  shift\ndone\nexit 99\n')
        fake.chmod(0o755)
        env = dict(os.environ, PATH=f"{fakebin}{os.pathsep}{os.environ['PATH']}")
        r = subprocess.run([BASH, str(project / "shell.sh")], capture_output=True,
                           text=True, env=env, check=False)
        assert r.returncode == 0, r.stderr
        rc_text = r.stdout.split("=" * 60)[-1].strip("\n")  # keep significant trailing "\\ "

        rc = tmp_path / "rc.sh"
        rc.write_text(rc_text + '\nprintf "PS1=[%s]\\n" "$PS1"\n')
        out = subprocess.run([BASH, str(rc)], capture_output=True, text=True,
                             cwd=tmp_path, check=False)
        assert out.returncode == 0, out.stderr
        assert "ACTIVATED" in out.stdout
        assert f"PS1=[({label}) " in out.stdout
        assert not (tmp_path / "PWNED").exists()


# ---------------------------------------------------------------------------
# 5. PowerShell template substitution must be single-pass
# ---------------------------------------------------------------------------

def test_ps1_placeholder_lookalike_in_project_name_stays_literal(cfg_factory):
    cfg = cfg_factory(project_name="__VENV_DIR__ and __APP_ENTRY__", venv_dir="venvx")
    content = make_run_ps1(cfg)
    assert "$PROJECT_NAME = '__VENV_DIR__ and __APP_ENTRY__'" in content


# ---------------------------------------------------------------------------
# 6. generate_files must be all-or-nothing on conflicts
# ---------------------------------------------------------------------------

def test_generate_conflict_writes_nothing_and_names_every_conflict(cfg_factory):
    cfg = cfg_factory(include_test_bat=True)
    (cfg.project_dir / "sync.bat").write_text("user's own")
    (cfg.project_dir / "test.bat").write_text("user's own too")
    with pytest.raises(FileExistsError) as exc:
        generate_files(cfg)
    assert sorted(p.name for p in cfg.project_dir.iterdir()) == ["sync.bat", "test.bat"]
    assert "sync.bat" in str(exc.value) and "test.bat" in str(exc.value)


# ---------------------------------------------------------------------------
# 7. check: self-unpack timestamps, cross-platform determinism
# ---------------------------------------------------------------------------

class _LaterClock:
    @staticmethod
    def now():
        return _dt.datetime(2031, 1, 1, 9, 9)


def test_self_unpack_check_ignores_embedded_timestamps(cfg_factory):
    cfg = cfg_factory(self_unpack=True, include_posix=True, include_powershell=True,
                      include_test_bat=True)
    generate_files(cfg)
    with mock.patch.object(core, "datetime", _LaterClock):
        statuses = {e.filename: e.status for e in check_drift(cfg)}
    assert statuses == {"setup.bat": "match"}


def _run_cli(argv):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    return e.value.code


def test_check_on_linux_agrees_with_generate_on_windows(tmp_path, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "main.py").write_text("")
    with mock.patch.object(sys, "platform", "win32"):
        assert _run_cli(["generate", str(proj), "--entry", "main.py"]) == 0
    with mock.patch.object(sys, "platform", "linux"):
        assert _run_cli(["check", str(proj), "--entry", "main.py"]) == 0


# ---------------------------------------------------------------------------
# 8. CLI: preset venv_dir honoured; presets file validated
# ---------------------------------------------------------------------------

def test_cli_preset_venv_dir_is_honoured(tmp_path):
    pm = PresetManager()
    pm.save("My Venv", {"venv_dir": "venv311", "entry_mode": "file", "app_entry": "main.py"})
    proj = tmp_path / "p"
    assert _run_cli(["generate", str(proj), "--preset", "My Venv", "--no-requirements"]) == 0
    assert 'set "VENV_DIR=venv311"' in (proj / "run.bat").read_text()


def test_corrupt_preset_entries_are_ignored_and_names_are_unique(tmp_path):
    PresetManager._STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    PresetManager._STORAGE_FILE.write_text(
        '{"Bad": 5, "Also bad": ["x"], "CLI Script": {"venv_dir": "hijack"},'
        ' "Good": {"venv_dir": "v", "entry_mode": "file", "app_entry": "a.py"}}'
    )
    pm = PresetManager()
    names = pm.names()
    assert len(names) == len(set(names))
    assert "Bad" not in names and "Also bad" not in names
    assert "Good" in names
    assert pm.get("CLI Script")["venv_dir"] == ".venv"


# ---------------------------------------------------------------------------
# 9. Scanner: dependency keywords must match names, not substrings
# ---------------------------------------------------------------------------

def test_scanner_does_not_match_keyword_substrings(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "metrics"\ndependencies = ["clickhouse-driver", "flasky-utils"]\n'
    )
    scan = scan_project_folder(tmp_path)
    assert scan.suggested_entry_mode is None


def test_scanner_reads_requirements_txt_for_framework_hints(tmp_path):
    (tmp_path / "requirements.txt").write_text("# web\nFastAPI>=0.110\nuvicorn[standard]\n")
    scan = scan_project_folder(tmp_path)
    assert scan.suggested_entry_mode == "runner"
    assert scan.suggested_app_entry == "uvicorn"


def test_every_bat_has_balanced_blocks_and_safe_echoes_inside_them(tmp_path):
    from helpers import bat_block_problems

    problems = {}
    for i, cfg in enumerate(_all_configs(tmp_path)):
        scripts = {n: c for n, c in build_previews(cfg).items() if n.endswith(".bat")}
        scripts["self-unpack setup.bat"] = make_self_unpacking_setup_bat(
            replace(cfg, include_setup=False, self_unpack=True))
        for name, content in scripts.items():
            bad = bat_block_problems(content)
            if bad:
                problems[f"{i}:{name}"] = bad
    assert not problems, problems
