# Venv Batch Template Generator

A Windows GUI utility that generates a set of project-local helper scripts for Python projects.

**v2.1** — PyQt6 GUI, live script preview, file and module entry modes, optional `.venv` creation, and a hardened batch output.

Core idea:

```bat
.venv\Scripts\python.exe
```

Each project owns its own Python runtime. The generated scripts call that runtime directly — no activation, no guessing, no global dependency damage.

---

## Requirements

- Python 3.10+
- PyQt6

```bat
pip install PyQt6
```

---

## Files Generated

The base set is five scripts. An optional sixth can be included.

### `run.bat`

Launches the project using its local venv Python.

Supports two modes, selected in the GUI:

**File mode** — for projects launched as a script:

```bat
.venv\Scripts\python.exe main.py
```

**Module mode** — for projects launched as a package:

```bat
.venv\Scripts\python.exe -m desktop_companion
```

Pass-through args work in both modes:

```bat
run.bat --debug --port 8080
```

---

### `pip.bat`

Installs packages into the project venv, not global Python.

```bat
pip.bat install requests
pip.bat install -r requirements.txt
pip.bat freeze > requirements.txt
pip.bat list
pip.bat uninstall requests
```

---

### `shell.bat`

Opens an activated CMD session for the project. Use this only when you deliberately want an interactive venv shell. Exit with `exit`.

---

### `sync.bat`

Syncs the project venv to `requirements.txt`.

> **Note:** This does not upgrade every installed package. It upgrades pip itself, then installs whatever is pinned in `requirements.txt`, then runs `pip check`.

```bat
sync.bat
```

To capture your current state first:

```bat
pip.bat freeze > requirements.txt
```

---

### `doctor.bat`

Audits the project environment. Run this when something seems broken.

Reports:

- project path and venv Python executable
- Python version, prefix, executable path
- pip version
- full installed package list
- `pip check` dependency health
- entry point status (file exists / module importable)
- `requirements.txt` and `requirements.lock.txt` presence
- optional PyQt6 WebEngine import check (full traceback shown on failure)

---

### `test.bat` *(optional)*

Runs pytest via the project venv Python. Enable **Include test.bat** in the GUI.

```bat
test.bat                          (run all tests)
test.bat tests/test_core.py       (run a specific file)
test.bat -k mapper                (filter by name)
test.bat -v --tb=short            (verbose with short tracebacks)
```

Requires pytest to be installed in the project venv:

```bat
pip.bat install pytest
```

---

## How To Use The GUI

```bat
python venv_template_generator.py
```

1. Click **Browse** and select the target project folder.
2. Enter or confirm the project name (auto-filled from the folder name).
3. Set the venv folder name — usually `.venv`.
4. Choose the entry type:
   - **Python file** — e.g. `main.py` or `src\app.py`
   - **Python module / package** — e.g. `desktop_companion`
5. Configure options (see below).
6. Click **Generate Script Set**.

The right panel shows a live preview of every file before it is written. Switch tabs to inspect each script. Click **Refresh Preview** after changing settings.

After generating, click **Open Folder** to open the output directory in Explorer.

---

## Options

| Option | Default | Description |
|---|---|---|
| Overwrite existing .bat files | Off | Replace files if they already exist in the folder |
| Create requirements.txt if missing | On | Write an empty requirements.txt if none exists |
| Include PyQt6 WebEngine check in doctor.bat | On | Adds a WebEngine import test with full error output |
| Pause when run.bat exits | On | Keeps the terminal open after the process ends |
| Create .venv now | Off | Runs `python -m venv .venv` immediately after generating |
| Include test.bat | Off | Generate an optional pytest runner script |

---

## For Module Projects

If you normally launch a project like this:

```bat
python -m desktop_companion
```

Select **Python module / package** and enter:

```text
desktop_companion
```

Dotted submodule paths are also valid:

```text
mypackage.cli
```

Module names are validated against the Python identifier rules. Spaces, hyphens, and special characters are rejected.

---

## First-Time Project Setup

Generate the scripts, then:

```bat
python -m venv .venv
```

Or enable **Create .venv now** to have the GUI do it.

Install dependencies:

```bat
pip.bat install -r requirements.txt
```

Run the project:

```bat
run.bat
```

Check the environment:

```bat
doctor.bat
```

---

## Daily Workflow

```bat
run.bat                            launch the project
pip.bat install <package>          add a dependency
pip.bat freeze > requirements.txt  pin current state
sync.bat                           restore venv from requirements.txt
doctor.bat                         diagnose environment problems
test.bat                           run the test suite
shell.bat                          drop into an interactive venv shell
```

---

## Recommended Project Layout

```text
my_project\
  .venv\
  requirements.txt
  run.bat
  pip.bat
  shell.bat
  sync.bat
  doctor.bat
  test.bat          (if included)
  main.py
```

---

## Why This Exists

Manual venv activation is easy to forget, especially when switching between several projects. The wrong pip or python silently installs into the wrong place.

This utility makes the runtime boundary explicit and permanent:

```text
Project A uses  Project A\.venv\Scripts\python.exe
Project B uses  Project B\.venv\Scripts\python.exe
```

No activation. No global damage. No broken projects because another project upgraded the wrong package.

---

## Batch Safety Notes

The generated scripts are hardened for Windows CMD:

- All dynamic paths (`%CD%`, `%PY%`, `%APP_ENTRY%`, `%VENV_DIR%`) are quoted in `echo` and `title` lines, so project names or paths containing `&`, `|`, `<`, or `>` do not break output.
- All `set` assignments use the `set "VAR=value"` form.
- `%` characters in project names are doubled to `%%` to prevent variable expansion.
- No Unicode characters appear in generated `.bat` content — pure ASCII throughout for CMD codepage safety.

---

## PyInstaller Note

Build from inside the project venv or call its Python directly:

```bat
.venv\Scripts\python.exe -m PyInstaller your_app.spec
```

This ensures the executable captures the correct project dependency stack, not whatever happens to be active globally.
