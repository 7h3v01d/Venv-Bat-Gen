# venv-bat-gen

[![CI](https://github.com/7h3v01d/Venv-Bat-Gen/actions/workflows/ci.yml/badge.svg)](https://github.com/7h3v01d/Venv-Bat-Gen/actions/workflows/ci.yml)

**Generate project-local venv helper scripts for Python projects — Windows, WSL, macOS, and Linux.**

`venv-bat-gen` solves a specific Windows pain point: activating a virtual environment manually is annoying, error-prone, and breaks in scripts. The correct approach is to call `.venv\Scripts\python.exe` directly — but writing those helper scripts by hand every time is tedious.

This tool generates a complete set of project-local helper scripts in seconds, from a polished GUI or a single CLI command. It also supports **repo-friendly mode** — generate a single self-unpacking `setup.bat` that you commit to your repo, and anyone who clones it gets the full set of scripts on first run.

---

## What it generates

For every project, `venv-bat-gen` writes up to **18 scripts** (`.bat` for Windows, `.sh` for POSIX, `.ps1` for PowerShell):

| Script | Purpose |
|---|---|
| `run.bat` / `run.sh` / `run.ps1` | Run your project — file, module, or runner mode |
| `pip.bat` / `pip.sh` / `pip.ps1` | Project-local pip (or uv pip) wrapper |
| `shell.bat` / `shell.sh` / `shell.ps1` | Open an activated shell session |
| `sync.bat` / `sync.sh` / `sync.ps1` | Install / sync dependencies |
| `doctor.bat` / `doctor.sh` / `doctor.ps1` | Environment health check |
| `test.bat` / `test.sh` / `test.ps1` | Run pytest via the local venv |

Every script calls `.venv\Scripts\python.exe` (or `.venv/bin/python`) directly — **no manual activation required**, and no PATH pollution.

---

## Repo-friendly mode (self-unpacking setup.bat)

Pass `--self-unpack` (CLI) or check **"Repo mode: single self-unpacking setup.bat"** (GUI) to generate a single `setup.bat` instead of individual scripts.

**Ship only `setup.bat` in your repo.** On first run it:

1. Checks Python (or uv) is available
2. Creates the virtual environment
3. Installs dependencies from `requirements.txt` / `uv.lock` / `pyproject.toml`
4. Decodes and writes all companion scripts beside itself via `certutil`

All companion scripts are embedded as base64 inside `setup.bat` — no dependencies, no internet, no installer required. Scripts that already exist are never overwritten, so re-running is safe.

```bash
# Generate a self-unpacking setup.bat
venv-bat-gen generate . --entry main.py --self-unpack

# With test runner and uv
venv-bat-gen generate . --entry main.py --self-unpack --test --uv

# Preview what would be generated
venv-bat-gen generate . --entry main.py --self-unpack --preview
```

**Recommended `.gitignore` additions** when using repo mode (the generated companions are not tracked):

```gitignore
run.bat
pip.bat
shell.bat
sync.bat
doctor.bat
test.bat
# If --posix is also used:
run.sh
pip.sh
shell.sh
sync.sh
doctor.sh
test.sh
# If --powershell is also used:
run.ps1
pip.ps1
shell.ps1
sync.ps1
doctor.ps1
test.ps1
```

> **Note:** `--self-unpack` and `--setup` are mutually exclusive. Self-unpack already includes the bootstrap logic.

---

## Installation

The CLI has zero dependencies. Install the `gui` extra only if you want the desktop app.

**Via pip:**
```bash
# CLI only
pip install venv-bat-gen

# CLI + GUI
pip install "venv-bat-gen[gui]"
```

**Via uv (recommended):**
```bash
uv pip install venv-bat-gen
# or with the GUI:
uv pip install "venv-bat-gen[gui]"
```

**Via uv tool (globally, isolated):**
```bash
uv tool install venv-bat-gen
```

**From source:**
```bash
git clone https://github.com/7h3v01d/Venv-Bat-Gen
cd Venv-Bat-Gen
pip install -e .           # CLI only
pip install -e ".[gui]"    # CLI + GUI
```

> **Note:** Running `venv-bat-gen-gui` (or `python -m venv_bat_gen` with no
> arguments) without the `gui` extra installed prints an install hint and
> exits — it won't silently do nothing or dump a bare traceback. On Windows,
> that message is only visible if you launch it from a terminal; a
> double-clicked shortcut with PyQt6 missing will exit with no visible
> output, since it runs windowless.

---

## Usage

### GUI

```bash
# Launch the GUI
venv-bat-gen-gui

# Or
python -m venv_bat_gen
```

The GUI provides:
- **Presets** — built-in templates for FastAPI, PyQt6, CLI scripts, Streamlit, uv projects, and repo self-unpack. Save your own.
- **Folder auto-detect** — browse to a project folder and the scanner reads `pyproject.toml`, `uv.lock`, `requirements.txt`, and common entry files to suggest settings automatically.
- **Live preview** — see the generated scripts before writing them, with syntax highlighting.
- **Configure / Log tabs** — settings scroll freely on any screen size; the activity log switches automatically on generate.

### CLI

```bash
# Basic usage
venv-bat-gen generate C:\projects\myapi --runner --entry uvicorn \
    --runner-args "app.main:app --host 0.0.0.0 --port 8000 --reload"

# Repo mode — single self-unpacking setup.bat
venv-bat-gen generate C:\projects\myapp --entry main.py --self-unpack

# Repo mode with test runner and uv
venv-bat-gen generate C:\projects\myapp --entry main.py --self-unpack --test --uv

# Load a preset as defaults, then override
venv-bat-gen generate C:\projects\myapp --preset "FastAPI / Uvicorn" --name MyApp

# Use uv + generate POSIX .sh scripts too
venv-bat-gen generate ~/projects/mytool --module --entry mytool --uv --posix

# Also generate PowerShell .ps1 equivalents (independent of --posix)
venv-bat-gen generate ~/projects/mytool --entry main.py --powershell

# Preview generated content without writing files
venv-bat-gen generate C:\projects\myapp --entry main.py --self-unpack --preview

# Scan a folder for auto-detection hints
venv-bat-gen scan C:\projects\existing

# Check whether generated files have drifted from current settings
venv-bat-gen check C:\projects\myapp --entry main.py

# Same, but show a unified diff of what changed
venv-bat-gen check C:\projects\myapp --entry main.py --diff

# List available presets
venv-bat-gen presets
```

#### Checking for drift

`check` recomputes what `generate` would currently produce — using the
same CLI flag > preset > folder auto-detect > default priority — and
compares it against what's already on disk, without writing anything.
Useful after upgrading `venv-bat-gen` (template changes) or in CI, to
catch a project whose scripts have fallen out of sync with its settings:

```bash
venv-bat-gen check ./my_project --entry main.py
# exit 0: everything matches
# exit 1: something is missing or drifted — run `generate --overwrite` to fix
```

The one-time `Generated on: <timestamp>` line every script stamps is
ignored for comparison purposes, so `check` won't report drift just
because time has passed since the last `generate`.


#### Entry modes

| Flag | Generated command | Use when |
|---|---|---|
| `--file` | `python main.py` | Single entry file |
| `--module` | `python -m mypackage` | Proper package with `__main__.py` |
| `--runner` | `python -m uvicorn app.main:app ...` | Tools like uvicorn, streamlit, flask |

---

## uv support

Pass `--uv` (CLI) or check "Use uv" (GUI) to generate uv-native scripts:

- `sync.bat/sh` — runs `uv sync` (with `uv.lock` / `pyproject.toml` detection) or falls back to `uv pip install -r requirements.txt`
- `pip.bat/sh` — wraps `uv pip --python .venv/...`
- `doctor.bat/sh` — checks `uv` is on PATH and shows its version
- `create_venv` — runs `uv venv` instead of `python -m venv`, with graceful fallback if uv isn't installed

The **"uv Project"** and **"Repo Self-Unpack (uv)"** built-in presets configure all of this automatically.

---

## Cross-platform (POSIX) scripts

Pass `--posix` (CLI) or check "Generate POSIX .sh scripts" (GUI) to also write `.sh` equivalents of every script. Shell scripts are written with:
- Unix LF line endings
- `#!/usr/bin/env bash` shebang
- `chmod +x` set automatically on generate
- `.venv/bin/python` instead of `.venv\Scripts\python.exe`

When combined with `--self-unpack`, all `.sh` scripts are embedded in the single `setup.bat` alongside the `.bat` scripts and written on first run.

The **"CLI Script (Cross-Platform)"** preset generates both `.bat` and `.sh` by default.

---

## PowerShell (.ps1) scripts

Pass `--powershell` (CLI) or check "Generate PowerShell .ps1 scripts" (GUI) to also write `.ps1` equivalents of every script. Useful where `.bat`/`.cmd` execution is blocked by policy but PowerShell is allowed. PowerShell scripts are written with:
- Windows CRLF line endings (same as `.bat`) and `#Requires -Version 5.1`, so they run on the PowerShell that ships with Windows — no PowerShell 7/`pwsh` required
- `.venv\Scripts\python.exe` directly, same as `.bat`
- `shell.ps1` dot-sources `Activate.ps1` and, if that fails due to an execution-policy restriction, prints the one-liner to fix it (`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`) rather than failing silently

`--posix` and `--powershell` are independent — pass both to generate all three families at once. When combined with `--self-unpack`, `.ps1` scripts are embedded in `setup.bat` alongside `.bat` (and `.sh`, if also enabled) and written on first run.

---

## Presets

Built-in presets (read-only):

| Preset | Mode | Entry | uv | POSIX | Self-unpack |
|---|---|---|---|---|---|
| FastAPI / Uvicorn | runner | uvicorn | — | — | — |
| PyQt6 Desktop App | file | main.py | — | — | — |
| CLI Script | module | app | — | — | — |
| CLI Script (Cross-Platform) | module | app | — | ✔ | — |
| Streamlit App | runner | streamlit | — | — | — |
| uv Project | module | app | ✔ | — | — |
| Repo Self-Unpack | file | main.py | — | — | ✔ |
| Repo Self-Unpack (uv) | file | main.py | ✔ | — | ✔ |

User presets are saved to `~/.venv_bat_gen/presets.json` and persist across sessions.

> **Upgrading from v3.3?** Presets previously stored in `~/.keystoneai/venv_generator_presets.json` are automatically migrated to the new location on first run.

---

## Project structure

```
venv_bat_gen/
├── __init__.py     # version
├── __main__.py     # python -m venv_bat_gen entry point
├── core.py         # GeneratorConfig, all template generators, scanner, presets
├── cli.py          # argparse CLI — no Qt dependency
└── gui.py          # PyQt6 GUI — imports from core
```

`core.py` has zero Qt imports and is safe to use headlessly from scripts or other tools:

```python
from venv_bat_gen.core import GeneratorConfig, generate_files
from pathlib import Path

# Standard multi-file generation
cfg = GeneratorConfig(
    project_dir=Path("C:/projects/myapi"),
    project_name="MyAPI",
    venv_dir=".venv",
    entry_mode="runner",
    app_entry="uvicorn",
    runner_args="app.main:app --host 0.0.0.0 --port 8000 --reload",
    overwrite_existing=False,
    create_requirements=True,
    include_webengine_check=False,
    pause_on_exit=False,
    create_venv_now=False,
    include_test_bat=True,
    use_uv=False,
    include_posix=False,
    include_setup=False,
    self_unpack=False,
)
written = generate_files(cfg)

# Repo mode — single self-unpacking setup.bat
cfg_repo = GeneratorConfig(
    project_dir=Path("C:/projects/myapp"),
    project_name="MyApp",
    venv_dir=".venv",
    entry_mode="file",
    app_entry="main.py",
    runner_args="",
    overwrite_existing=False,
    create_requirements=True,
    include_webengine_check=False,
    pause_on_exit=True,
    create_venv_now=False,
    include_test_bat=True,
    use_uv=False,
    include_posix=False,
    include_setup=False,
    self_unpack=True,
)
written = generate_files(cfg_repo)  # writes only setup.bat
```

---

## Requirements

- Python 3.11+
- PyQt6 6.4+ — only needed for the GUI; install via `pip install venv-bat-gen[gui]`
- `certutil` (built into Windows 7+ — required at runtime by the generated self-unpacking `setup.bat`)
- uv (optional — only needed if using `--uv` / "Use uv" mode)

---

## Why not just activate the venv?

Activation works fine interactively. It breaks when:
- You run scripts from task schedulers, CI, or other tools that don't inherit your shell state
- You have multiple projects open and activation leaks across terminals
- You want a double-clickable launcher that just works

Calling `.venv\Scripts\python.exe` directly avoids all of this. The generated scripts are readable, editable, and self-documenting — they're not magic wrappers.

---

## Contributing

Issues and PRs welcome. The codebase is intentionally simple:

- Add a new template → add `make_<name>_bat()` and `make_<name>_sh()` to `core.py`, register in `build_previews()`
- Add a new preset → add an entry to `_BUILTIN_PRESETS` in `core.py`
- Add a CLI flag → `_build_generate_parser()` in `cli.py`, wire through `_cmd_generate()`
- Add a GUI option → `_build_options_group()` in `gui.py`, wire through `_read_config()`

---

## Changelog

### Unreleased
- **GUI smoke-tested for real** — added `tests/test_gui_smoke.py` (PyQt6 + pytest-qt, runs headlessly via Qt's `offscreen` platform, `dev-gui` extra). This caught a real bug: `PresetManager`'s internal field allowlist hadn't been updated for the new `include_powershell` flag, so saving a custom preset via the GUI silently dropped that setting. Fixed, plus a standing regression guard so it can't happen again for any future flag.
- **New PowerShell (`.ps1`) variant** — `--powershell` (CLI) / "Generate PowerShell .ps1 scripts" (GUI) generates `.ps1` equivalents of every script, targeting the PowerShell 5.1 that ships with Windows (no `pwsh`/PowerShell 7 required). Useful where `.bat` execution is blocked by policy but PowerShell is allowed. Independent of `--posix`; both can be enabled together. Also embeds correctly in `--self-unpack` mode alongside `.bat`/`.sh`. Along the way, fixed a pre-existing bug in `make_test_sh`: under `set -euo pipefail`, an unguarded pytest invocation meant bash would abort the script on test failure before the pass/fail banner or correct exit code ever ran.
- **New `check` subcommand** — `venv-bat-gen check <folder>` recomputes what `generate` would currently produce (same CLI flag > preset > folder auto-detect > default priority) and compares it against what's on disk, without writing anything. Exits 1 if anything is missing or drifted (handy in CI after a template upgrade), 0 if up to date. `--diff` shows a unified diff per drifted file. The one-time `Generated on: <timestamp>` line is ignored for comparison so `check` doesn't false-positive purely from time passing.
- **PyQt6 is now optional** — moved to a `gui` extra (`pip install venv-bat-gen[gui]`). The CLI has zero dependencies. `venv-bat-gen-gui` / `python -m venv_bat_gen` (no args) now exit with an actionable install hint instead of a bare `ModuleNotFoundError` when PyQt6 isn't installed.
- **Test suite** — added `tests/`, covering every template generator (bat/sh/ps1), the self-unpacking round-trip, the folder scanner, the preset system, drift detection, and the full CLI argparse layer (100% line coverage of `core.py` and `cli.py`).
- **CI** — GitHub Actions workflow running the test suite across Windows/macOS/Linux × Python 3.11–3.13, a `ruff` lint gate, and package build verification.
- **Lint cleanup** — removed 3 unused imports and 2 stray f-string prefixes; the codebase's deliberate compact `if x: y` one-liner style is now a documented, project-wide `ruff` ignore (`E701`) rather than unaddressed noise.
- **Fixed stale metadata** — `__init__.py`'s `__version__`/`__author__` now match `pyproject.toml` and the current `Leon Priest / 7h3v01d` branding; project URLs across `README.md` and `pyproject.toml` now consistently point to `github.com/7h3v01d/Venv-Bat-Gen`.

### v3.4.0
- **Repo mode** — new `--self-unpack` CLI flag and "Repo mode" GUI checkbox. Generates a single `setup.bat` containing all companion scripts encoded as base64, decoded via `certutil` on first run. Safe to re-run — existing files are never overwritten.
- **Two new presets** — `Repo Self-Unpack` and `Repo Self-Unpack (uv)`
- **Branding** — updated throughout to `Leon Priest / 7h3v01d`
- **Preset storage** — moved from `~/.keystoneai/` to `~/.venv_bat_gen/`; automatic migration on first run
- **`--self-unpack` + `--setup` mutex** — these are mutually exclusive; the CLI errors clearly if both are passed
- **`certutil` failure detection** — the generated `setup.bat` now checks whether each output file was actually created and reports `[FAIL]` with a clear message if certutil is unavailable
- **GUI** — `self_unpack` checkbox disables standalone `setup` option and vice versa; round-trips through preset save/load

### v3.3.x
- uv support, POSIX `.sh` scripts, project folder scanner, preset system

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Built by [Leon Priest / 7h3v01d](https://github.com/7h3v01d) 
