# venv-bat-gen

**Generate project-local venv helper scripts for Python projects — Windows, WSL, macOS, and Linux.**

`venv-bat-gen` solves a specific Windows pain point: activating a virtual environment manually is annoying, error-prone, and breaks in scripts. The correct approach is to call `.venv\Scripts\python.exe` directly — but writing those helper scripts by hand every time is tedious.

This tool generates a complete set of project-local helper scripts in seconds, from a polished GUI or a single CLI command.

---

## What it generates

For every project, `venv-bat-gen` writes up to **12 scripts** (`.bat` for Windows, `.sh` for POSIX):

| Script | Purpose |
|---|---|
| `run.bat` / `run.sh` | Run your project — file, module, or runner mode |
| `pip.bat` / `pip.sh` | Project-local pip (or uv pip) wrapper |
| `shell.bat` / `shell.sh` | Open an activated shell session |
| `sync.bat` / `sync.sh` | Install / sync dependencies |
| `doctor.bat` / `doctor.sh` | Environment health check |
| `test.bat` / `test.sh` | Run pytest via the local venv |

Every script calls `.venv\Scripts\python.exe` (or `.venv/bin/python`) directly — **no manual activation required**, and no PATH pollution.

---

## Installation

**Via pip:**
```bash
pip install venv-bat-gen
```

**Via uv (recommended):**
```bash
uv pip install venv-bat-gen
```

**Via uv tool (globally, isolated):**
```bash
uv tool install venv-bat-gen
```

**From source:**
```bash
git clone https://github.com/keystoneai/venv-bat-gen
cd venv-bat-gen
pip install -e .
```

> **Note:** The GUI requires PyQt6. If you only need the CLI, PyQt6 is still installed as a dependency — a headless CLI-only mode may be added in a future release.

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
- **Presets** — built-in templates for FastAPI, PyQt6, CLI scripts, Streamlit, and uv projects. Save your own.
- **Folder auto-detect** — browse to a project folder and the scanner reads `pyproject.toml`, `uv.lock`, `requirements.txt`, and common entry files to suggest settings automatically.
- **Live preview** — see the generated scripts before writing them, with syntax highlighting.
- **Configure / Log tabs** — settings scroll freely on any screen size; the activity log switches automatically on generate.

### CLI

```bash
# Basic usage
venv-bat-gen generate C:\projects\myapi --runner --entry uvicorn \
    --runner-args "app.main:app --host 0.0.0.0 --port 8000 --reload"

# Load a preset as defaults, then override
venv-bat-gen generate C:\projects\myapp --preset "FastAPI / Uvicorn" --name MyApp

# Use uv + generate POSIX .sh scripts too
venv-bat-gen generate ~/projects/mytool --module --entry mytool --uv --posix

# Dry run — see what would be written
venv-bat-gen generate C:\projects\myapp --preset "PyQt6 Desktop App" --dry-run

# Scan a folder for auto-detection hints
venv-bat-gen scan C:\projects\existing

# List available presets
venv-bat-gen presets
venv-bat-gen presets --detail
```

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

The **"uv Project"** built-in preset configures all of this automatically.

---

## Cross-platform (POSIX) scripts

Pass `--posix` (CLI) or check "Generate POSIX .sh scripts" (GUI) to also write `.sh` equivalents of every script. Shell scripts are written with:
- Unix LF line endings
- `#!/usr/bin/env bash` shebang
- `chmod +x` set automatically on generate
- `.venv/bin/python` instead of `.venv\Scripts\python.exe`

The **"CLI Script (Cross-Platform)"** preset generates both `.bat` and `.sh` by default.

---

## Presets

Built-in presets (read-only):

| Preset | Mode | Entry | uv | POSIX |
|---|---|---|---|---|
| FastAPI / Uvicorn | runner | uvicorn | — | — |
| PyQt6 Desktop App | file | main.py | — | — |
| CLI Script | module | app | — | — |
| CLI Script (Cross-Platform) | module | app | — | ✔ |
| Streamlit App | runner | streamlit | — | — |
| uv Project | module | app | ✔ | — |

User presets are saved to `~/.keystoneai/venv_generator_presets.json` and persist across sessions.

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
)
written = generate_files(cfg)
```

---

## Requirements

- Python 3.11+
- PyQt6 6.4+ (GUI)
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

## License

MIT — see [LICENSE](LICENSE).

---

*Built by [KeystoneAI](https://github.com/keystoneai) · Iterated with the help of Claude (Anthropic)*
