# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Leon Priest (7h3v01d)
"""
Shared test helpers that are not fixtures: reference parsers and runners
used to check generated scripts *behaviourally* rather than by substring.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Windows command-line -> argv reference parser
# ---------------------------------------------------------------------------

def windows_argv(cmdline: str) -> list[str]:
    """Split a Windows command line the way the MSVC CRT / CommandLineToArgvW
    does for every argument after argv[0] (what python.exe and console-script
    launchers use):

      * whitespace separates args unless inside double quotes
      * 2n backslashes followed by '"'   -> n backslashes, quote toggles
      * 2n+1 backslashes followed by '"' -> n backslashes and a literal '"'
      * backslashes not followed by '"'  -> literal
      * '""' inside a quoted region      -> literal '"' (post-2008 CRT rule)
    """
    args: list[str] = []
    i, n = 0, len(cmdline)
    while True:
        while i < n and cmdline[i] in " \t":
            i += 1
        if i >= n:
            return args
        cur: list[str] = []
        in_q = False
        while i < n and (in_q or cmdline[i] not in " \t"):
            ch = cmdline[i]
            if ch == "\\":
                j = i
                while j < n and cmdline[j] == "\\":
                    j += 1
                count = j - i
                if j < n and cmdline[j] == '"':
                    cur.append("\\" * (count // 2))
                    if count % 2:
                        cur.append('"')
                        i = j + 1
                    else:
                        i = j  # the quote is processed below
                else:
                    cur.append("\\" * count)
                    i = j
                continue
            if ch == '"':
                if in_q and i + 1 < n and cmdline[i + 1] == '"':
                    cur.append('"')
                    i += 2
                    continue
                in_q = not in_q
                i += 1
                continue
            cur.append(ch)
            i += 1
        args.append("".join(cur))


# ---------------------------------------------------------------------------
# cmd.exe echo-line quote guard
# ---------------------------------------------------------------------------

#: Variables whose values come from the user (project name, entry) or the
#: filesystem (paths), and so may contain & | < > ^ ( ).
RISKY_BAT_VARS = (
    "PROJECT_NAME", "APP_ENTRY", "VENV_DIR", "CD", "PY", "ACTIVATE",
    "SCRIPT_EXE", "RUNNER_ARGS", "~dp0",
)

_ECHO_RE = re.compile(r"^\s*(?:if\b.*?\)?\s*)?(?:echo[ .(]|title )", re.IGNORECASE)


def unquoted_bat_refs(script: str) -> list[str]:
    """Return every `echo ...` / `title ...` line in a .bat script that expands one of the
    RISKY_BAT_VARS outside a double-quoted span. cmd.exe performs %-expansion
    before it looks for & | < > ^, so an unquoted expansion of a value like
    'R&D' splits the echo into two commands."""
    bad: list[str] = []
    for raw in script.splitlines():
        line = raw.rstrip("\r")
        if not _ECHO_RE.match(line):
            continue
        low = line.lower()
        idx = low.find("echo")
        if idx == -1 or (0 <= low.find("title ") < idx):
            idx = low.find("title ")
        body = line[idx + 4:]
        in_q = False
        k = 0
        while k < len(body):
            ch = body[k]
            if ch == '"':
                in_q = not in_q
            elif ch == "%" and not in_q:
                for var in RISKY_BAT_VARS:
                    if body.startswith(f"%{var}%", k) or body.startswith(f"%{var}:", k):
                        bad.append(line.strip())
                        break
            k += 1
    return bad


# ---------------------------------------------------------------------------
# PowerShell
# ---------------------------------------------------------------------------

def find_pwsh() -> str | None:
    """Locate a PowerShell 7 binary (pwsh), honouring $VBG_PWSH."""
    explicit = os.environ.get("VBG_PWSH")
    if explicit and Path(explicit).exists():
        return explicit
    return shutil.which("pwsh")


def ps51_decode(raw: bytes) -> str:
    """Decode script bytes the way Windows PowerShell 5.1 does: honour a
    UTF-8 BOM, otherwise fall back to the ANSI code page (cp1252 on
    English-locale Windows)."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8")
    return raw.decode("cp1252", errors="replace")


def ps_parse_errors(pwsh: str, script_text: str, tmp: Path) -> list[str]:
    """Parse script_text with PowerShell's real parser; return error messages."""
    f = tmp / "parse_target.ps1"
    f.write_text(script_text, encoding="utf-8-sig")
    cmd = (
        "$t=$null;$e=$null;"
        f"[void][System.Management.Automation.Language.Parser]::ParseFile('{f}',[ref]$t,[ref]$e);"
        "$e | ForEach-Object { $_.Message }"
    )
    r = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", cmd],
                       capture_output=True, text=True, timeout=120, check=False)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# Fake venvs
# ---------------------------------------------------------------------------

def make_fake_posix_venv(project: Path, venv_dir: str = ".venv", python_script: str | None = None) -> Path:
    """Create <project>/<venv_dir>/bin/python. By default it re-execs the
    test interpreter; pass python_script to substitute a custom sh body."""
    bindir = project / venv_dir / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    py = bindir / "python"
    body = python_script or f'exec "{sys.executable}" "$@"\n'
    py.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    py.chmod(0o755)
    (bindir / "activate").write_text("echo ACTIVATED\n", encoding="utf-8")
    return py


def make_fake_windows_layout_venv(project: Path, venv_dir: str = ".venv", python_script: str | None = None) -> Path:
    """Create <project>/<venv_dir>/Scripts/python.exe as an executable shell
    script, so PowerShell 7 on Linux/macOS can exercise .ps1 templates."""
    sdir = project / venv_dir / "Scripts"
    sdir.mkdir(parents=True, exist_ok=True)
    py = sdir / "python.exe"
    body = python_script or f'exec "{sys.executable}" "$@"\n'
    py.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    py.chmod(0o755)
    return py


# ---------------------------------------------------------------------------
# cmd.exe parenthesised-block guard
# ---------------------------------------------------------------------------

def _unquoted_unescaped(line: str, ch: str) -> int:
    """Count `ch` occurrences outside double quotes and not ^-escaped."""
    n, in_q, k = 0, False, 0
    while k < len(line):
        c = line[k]
        if c == "^" and not in_q:
            k += 2
            continue
        if c == '"':
            in_q = not in_q
        elif c == ch and not in_q:
            n += 1
        k += 1
    return n


def bat_block_problems(script: str) -> list[str]:
    """Static check of cmd.exe ( ... ) blocks in a generated .bat:

    * inside a block, an `echo` (or `rem`) whose text has an unescaped,
      unquoted ')' would terminate the block early;
    * every opened block must be closed by the end of the script.
    """
    problems: list[str] = []
    depth = 0
    for raw in script.splitlines():
        line = raw.rstrip("\r").strip()
        low = line.lower()
        if not line or low.startswith("rem ") or low == "rem":
            if depth and ")" in line:
                problems.append(f"')' inside rem within a block: {line}")
            continue
        is_echo = low.startswith("echo") or (low.startswith("if ") and " echo" in low)
        if depth and is_echo:
            text = line[low.find("echo") + 4:]
            if _unquoted_unescaped(text, ")"):
                problems.append(f"unescaped ')' in echo inside a block: {line}")
            continue
        if is_echo:
            continue
        opens = _unquoted_unescaped(line, "(")
        closes = _unquoted_unescaped(line, ")")
        depth += opens - closes
        if depth < 0:
            problems.append(f"block closed more than opened: {line}")
            depth = 0
    if depth:
        problems.append(f"{depth} block(s) left open at end of script")
    return problems
