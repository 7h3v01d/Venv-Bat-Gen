# Venv Project Templates

A small set of Windows `.bat` helper scripts for managing Python project virtual environments without constantly activating and deactivating them manually.

The core idea is simple:

> Do not enter venvs unless you need to.  
> Call the project’s `.venv\Scripts\python.exe` directly.

This keeps each project isolated and prevents dependency conflicts between projects.

---

## Included Files

### `run.bat`

Runs the project using the local `.venv` Python executable.

Edit this line per project:

```bat
set "APP_ENTRY=main.py"
```
Example:
```bat
set "APP_ENTRY=devtoolkit.py"
```
Then run:
```
run.bat
```

---

### pip.bat

A safe wrapper around pip that installs packages into the local project .venv.

Instead of:
```bat
pip install requests
```
Use:
```bat
pip.bat install requests
```
Or:
```bat
pip.bat install -r requirements.txt
pip.bat freeze
pip.bat list
```
---

### shell.bat

Opens an activated shell for the project when you actually need one.

Use this only when you want to work interactively inside the venv:

```bat
shell.bat
```
The terminal title is changed so it is easier to see which project shell you are in.

---

### doctor.bat

Checks the local project environment.

It reports:

- project path
- venv Python executable
- Python version
- pip version
- pip check result
- whether requirements.txt exists
- optional PyQt6 WebEngine import test

Run:
```bat
doctor.bat
```

---

### First-Time Setup Per Project

From the project folder:
```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
```
Then install dependencies:
```bat
pip.bat install -r requirements.txt
```
Or install packages manually:
```bat
pip.bat install PyQt6 requests fastapi
```
--- 

### Recommended Project Layout

```
my_project/
  .venv/
  requirements.txt
  run.bat
  pip.bat
  shell.bat
  doctor.bat
  main.py
```

### Why Use This?

Manual venv activation can get confusing when switching between many projects.

These scripts avoid that by making each project call its own Python directly:
```bat
.venv\Scripts\python.exe
```
This prevents accidental global installs and stops one project’s dependencies from breaking another project.

---

### Basic Workflow

Create the venv:
```bat
python -m venv .venv
```
Install packages safely:
```bat
pip.bat install -r requirements.txt
```
Run the app:
```bat
run.bat
```
Check the environment:
```bat
doctor.bat
```
Open an interactive project shell only when needed:
```bat
shell.bat
```
---

### Notes

These templates are designed for Windows Python projects.

They are especially useful for projects with fragile or heavy dependencies such as:

- PyQt6 / PySide6 GUI apps
- FastAPI apps
- ML / AI projects
- audio/video tools
- PyInstaller builds
- long-term personal developer tools

For PyInstaller, build from inside the project .venv so the executable captures the correct dependency stack.