#!/usr/bin/env python3
"""
Venv Batch Template Generator v2.12  (PyQt6 edition)
KeystoneAI Pty Ltd

Generates up to six project-local helper scripts:

    run.bat       - launch the project via its venv Python
    pip.bat       - install packages into the project venv
    shell.bat     - open an activated interactive venv shell
    sync.bat      - upgrade pip and sync venv to requirements.txt
    doctor.bat    - audit the project environment
    test.bat      - run pytest via venv Python (optional)

Core principle:
    Never rely on manual venv activation.
    Call .venv\\Scripts\\python.exe directly.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Colour palette (dark, utilitarian, consistent with KeystoneAI tools)
# ---------------------------------------------------------------------------
PALETTE = {
    "bg":           "#1e1e2e",
    "surface":      "#2a2a3d",
    "surface_alt":  "#313149",
    "border":       "#44445a",
    "accent":       "#7c6af7",
    "accent_hover": "#9b8dff",
    "text":         "#e2e2f0",
    "text_dim":     "#8888aa",
    "ok":           "#4ec97b",
    "warn":         "#f0c040",
    "error":        "#f07070",
    "bat_keyword":  "#c792ea",
    "bat_rem":      "#546e7a",
    "bat_string":   "#c3e88d",
    "bat_var":      "#82aaff",
}

STYLESHEET = f"""
QWidget {{
    background-color: {PALETTE['bg']};
    color: {PALETTE['text']};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QGroupBox {{
    background-color: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    margin-top: 10px;
    padding: 10px 10px 10px 10px;
    font-weight: 600;
    font-size: 12px;
    color: {PALETTE['text_dim']};
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    top: 1px;
}}

QLineEdit {{
    background-color: {PALETTE['surface_alt']};
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    padding: 5px 8px;
    color: {PALETTE['text']};
    selection-background-color: {PALETTE['accent']};
}}

QLineEdit:focus {{
    border-color: {PALETTE['accent']};
}}

QPushButton {{
    background-color: {PALETTE['surface_alt']};
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    padding: 5px 14px;
    color: {PALETTE['text']};
    font-weight: 500;
    min-height: 26px;
}}

QPushButton:hover {{
    background-color: {PALETTE['accent']};
    border-color: {PALETTE['accent']};
    color: #ffffff;
}}

QPushButton:pressed {{
    background-color: {PALETTE['accent_hover']};
}}

QPushButton#primary {{
    background-color: {PALETTE['accent']};
    border-color: {PALETTE['accent']};
    color: #ffffff;
    font-weight: 600;
    font-size: 13px;
    min-height: 34px;
    padding: 6px 20px;
}}

QPushButton#primary:hover {{
    background-color: {PALETTE['accent_hover']};
    border-color: {PALETTE['accent_hover']};
}}

QPushButton#danger {{
    background-color: transparent;
    border-color: {PALETTE['error']};
    color: {PALETTE['error']};
}}

QPushButton#danger:hover {{
    background-color: {PALETTE['error']};
    color: #ffffff;
}}

QCheckBox, QRadioButton {{
    spacing: 6px;
    color: {PALETTE['text']};
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {PALETTE['border']};
    border-radius: 3px;
    background-color: {PALETTE['surface_alt']};
}}

QRadioButton::indicator {{
    border-radius: 8px;
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {PALETTE['accent']};
    border-color: {PALETTE['accent']};
}}

QPlainTextEdit {{
    background-color: #141420;
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    color: {PALETTE['text']};
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    selection-background-color: {PALETTE['accent']};
    padding: 4px;
}}

QTabWidget::pane {{
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    background-color: #141420;
}}

QTabBar::tab {{
    background-color: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 14px;
    color: {PALETTE['text_dim']};
    margin-right: 2px;
    font-size: 12px;
}}

QTabBar::tab:selected {{
    background-color: #141420;
    color: {PALETTE['text']};
    border-bottom: 1px solid #141420;
}}

QTabBar::tab:hover:!selected {{
    color: {PALETTE['text']};
}}

QSplitter::handle {{
    background-color: {PALETTE['border']};
    width: 1px;
    height: 1px;
}}

QStatusBar {{
    background-color: {PALETTE['surface']};
    border-top: 1px solid {PALETTE['border']};
    color: {PALETTE['text_dim']};
    font-size: 12px;
    padding: 2px 8px;
}}

QLabel#hint {{
    color: {PALETTE['text_dim']};
    font-size: 11px;
    font-style: italic;
}}

QLabel#sectiontitle {{
    font-size: 18px;
    font-weight: 700;
    color: {PALETTE['text']};
}}

QLabel#subtitle {{
    font-size: 12px;
    color: {PALETTE['text_dim']};
}}

QFrame#divider {{
    background-color: {PALETTE['border']};
    max-height: 1px;
    min-height: 1px;
}}
"""


# ---------------------------------------------------------------------------
# BAT syntax highlighter
# ---------------------------------------------------------------------------

class BatHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text: str) -> None:
        def fmt(hex_color: str, bold: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(hex_color))
            if bold:
                f.setFontWeight(700)
            return f

        stripped = text.lstrip()

        # Full-line REM comments
        if stripped.lower().startswith("rem ") or stripped.lower() == "rem":
            self.setFormat(0, len(text), fmt(PALETTE["bat_rem"]))
            return

        # Echo lines — dim
        if stripped.lower().startswith("echo ") or stripped.lower() == "echo.":
            self.setFormat(0, len(text), fmt(PALETTE["text_dim"]))

        # Keywords
        import re
        keywords = r"\b(if|else|goto|call|set|exit|pause|title|cd|setlocal|endlocal|for|do|in|not|exist|errorlevel|echo)\b"
        for m in re.finditer(keywords, text, re.IGNORECASE):
            self.setFormat(m.start(), m.end() - m.start(), fmt(PALETTE["bat_keyword"], bold=True))

        # %VARIABLES%
        for m in re.finditer(r"%[^%\n]+%", text):
            self.setFormat(m.start(), m.end() - m.start(), fmt(PALETTE["bat_var"]))

        # Quoted strings
        for m in re.finditer(r'"[^"\n]*"', text):
            self.setFormat(m.start(), m.end() - m.start(), fmt(PALETTE["bat_string"]))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

def bat_escape(value: str) -> str:
    """Escape characters that would break batch variable assignments."""
    # Strip double-quotes (can't appear inside a set "VAR=..." safely)
    # Escape % (would be interpreted as variable delimiter in batch)
    # Caret ^ and ampersand & are only dangerous if unquoted; since we wrap
    # all our set values in double-quotes they are safe, but percent needs doubling.
    value = value.replace('"', "")
    value = value.replace("%", "%%")
    return value


# Valid Python module/package name: identifiers separated by dots
# e.g. desktop_companion, package.submodule, my_app
MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")

# Batch command arguments are intentionally conservative. Runner mode is designed
# for simple Python-module command lines such as:
#   uvicorn jobfit.main:app --host 0.0.0.0 --port 8080 --reload
# Characters below can alter cmd.exe control flow after variable expansion.
RUNNER_ARGS_UNSAFE_RE = re.compile(r'[&|<>^"]')


@dataclass(frozen=True)
class GeneratorConfig:
    project_dir: Path
    project_name: str
    venv_dir: str
    entry_mode: str          # "file", "module", or "runner"
    app_entry: str           # file path, module name, or runner module
    runner_args: str         # used only when entry_mode == "runner"
    overwrite_existing: bool
    create_requirements: bool
    include_webengine_check: bool
    pause_on_exit: bool
    create_venv_now: bool
    include_test_bat: bool


# ---------------------------------------------------------------------------
# .bat generators
# ---------------------------------------------------------------------------

def make_run_bat(cfg: GeneratorConfig) -> str:
    project_name = bat_escape(cfg.project_name)
    venv_dir     = bat_escape(cfg.venv_dir)
    entry_mode   = bat_escape(cfg.entry_mode)
    app_entry    = bat_escape(cfg.app_entry)
    runner_args  = bat_escape(cfg.runner_args)
    pause_block  = "pause\nexit /b %EXITCODE%\n" if cfg.pause_on_exit else "exit /b %EXITCODE%\n"

    return fr'''@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Project Runner
rem  Generated by Venv Batch Template Generator (KeystoneAI)
rem
rem  ENTRY_MODE:
rem    file   -> .venv\Scripts\python.exe app.py
rem    module -> .venv\Scripts\python.exe -m package_name
rem    runner -> .venv\Scripts\python.exe -m runner_module args...
rem
rem  Example runner command:
rem    .venv\Scripts\python.exe -m uvicorn jobfit.main:app --host 0.0.0.0 --port 8080 --reload
rem ============================================================

set "PROJECT_NAME={project_name}"
set "VENV_DIR={venv_dir}"
set "ENTRY_MODE={entry_mode}"
set "APP_ENTRY={app_entry}"
set "RUNNER_ARGS={runner_args}"

set "PY=%CD%\%VENV_DIR%\Scripts\python.exe"

if not exist "%PY%" (
    echo [ERROR] Local venv was not found:
    echo         "%PY%"
    echo.
    echo Create it with:
    echo         python -m venv "%VENV_DIR%"
    echo         "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
    echo         "%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if /I "%ENTRY_MODE%"=="file" (
    if not exist "%APP_ENTRY%" (
        echo [ERROR] Entry file does not exist:
        echo         "%APP_ENTRY%"
        echo.
        echo Edit run.bat and set APP_ENTRY to your real launcher file.
        echo.
        pause
        exit /b 1
    )
)

title "%PROJECT_NAME% - RUN"
echo ============================================================
echo  Running : "%PROJECT_NAME%"
echo  Project : "%CD%"
echo  Python  : "%PY%"
echo  Mode    : %ENTRY_MODE%
echo  Entry   : "%APP_ENTRY%"
if /I "%ENTRY_MODE%"=="runner" echo  Args    : "%RUNNER_ARGS%"
echo ============================================================
echo.

if /I "%ENTRY_MODE%"=="module" (
    "%PY%" -m %APP_ENTRY% %*
) else if /I "%ENTRY_MODE%"=="runner" (
    "%PY%" -m %APP_ENTRY% %RUNNER_ARGS% %*
) else (
    "%PY%" "%APP_ENTRY%" %*
)

set "EXITCODE=%ERRORLEVEL%"
echo.
echo ============================================================
echo  Process exited with code: %EXITCODE%
echo ============================================================
{pause_block}'''


def make_pip_bat(cfg: GeneratorConfig) -> str:
    venv_dir = bat_escape(cfg.venv_dir)
    return f'''@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Project-local pip wrapper
rem  Generated by Venv Batch Template Generator (KeystoneAI)
rem
rem  Usage:
rem    pip.bat install requests
rem    pip.bat install -r requirements.txt
rem    pip.bat freeze > requirements.txt
rem    pip.bat list
rem    pip.bat uninstall requests
rem ============================================================

set "VENV_DIR={venv_dir}"
set "PY=%CD%\\%VENV_DIR%\\Scripts\\python.exe"

if not exist "%PY%" (
    echo [ERROR] Local venv was not found:
    echo         "%PY%"
    echo.
    echo Create it with:
    echo         python -m venv "%VENV_DIR%"
    echo.
    pause
    exit /b 1
)

"%PY%" -m pip %*
exit /b %ERRORLEVEL%
'''


def make_shell_bat(cfg: GeneratorConfig) -> str:
    project_name = bat_escape(cfg.project_name)
    venv_dir     = bat_escape(cfg.venv_dir)
    return f'''@echo off
cd /d "%~dp0"

rem ============================================================
rem  Project venv shell
rem  Generated by Venv Batch Template Generator (KeystoneAI)
rem
rem  Opens an activated CMD session for this project.
rem  Use only when you need an interactive venv session.
rem  Exit with: exit
rem ============================================================

set "PROJECT_NAME={project_name}"
set "VENV_DIR={venv_dir}"
set "ACTIVATE=%CD%\\%VENV_DIR%\\Scripts\\activate.bat"

if not exist "%ACTIVATE%" (
    echo [ERROR] Local venv was not found:
    echo         "%ACTIVATE%"
    echo.
    echo Create it with:
    echo         python -m venv "%VENV_DIR%"
    echo.
    pause
    exit /b 1
)

title "%PROJECT_NAME% - VENV SHELL"
call "%ACTIVATE%"

echo ============================================================
echo  Project shell activated
echo  Project: "%CD%"
echo  Python :
where python
echo  Type "exit" to leave this shell.
echo ============================================================
echo.
cmd /k
'''


def make_sync_bat(cfg: GeneratorConfig) -> str:
    project_name = bat_escape(cfg.project_name)
    venv_dir     = bat_escape(cfg.venv_dir)
    return f'''@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Dependency sync
rem  Generated by Venv Batch Template Generator (KeystoneAI)
rem
rem  NOTE: This does NOT upgrade every installed package.
rem  It syncs the venv to whatever is in requirements.txt.
rem
rem  Steps:
rem    1. Confirm venv exists
rem    2. Upgrade pip itself to latest
rem    3. Install / sync requirements.txt (exact versions pinned)
rem    4. Run pip check to verify dependency health
rem
rem  To pin current state first, run:
rem    pip.bat freeze > requirements.txt
rem ============================================================

set "PROJECT_NAME={project_name}"
set "VENV_DIR={venv_dir}"
set "PY=%CD%\\%VENV_DIR%\\Scripts\\python.exe"

if not exist "%PY%" (
    echo [ERROR] Local venv was not found:
    echo         "%PY%"
    echo.
    echo Create it with:
    echo         python -m venv "%VENV_DIR%"
    echo.
    pause
    exit /b 1
)

title "%PROJECT_NAME% - SYNC"

echo ============================================================
echo  Syncing: "%PROJECT_NAME%"
echo  Python : "%PY%"
echo ============================================================
echo.

echo [1/3] Upgrading pip...
echo ============================================================
"%PY%" -m pip install --upgrade pip
echo.

if exist "requirements.txt" (
    echo [2/3] Syncing requirements.txt...
    echo ============================================================
    "%PY%" -m pip install -r requirements.txt
    echo.
) else (
    echo [2/3] SKIPPED: requirements.txt not found.
    echo       Run pip.bat freeze ^> requirements.txt to create one.
    echo.
)

echo [3/3] Dependency health check...
echo ============================================================
"%PY%" -m pip check
echo.

echo ============================================================
echo  SYNC COMPLETE
echo ============================================================
pause
exit /b 0
'''


def make_doctor_bat(cfg: GeneratorConfig) -> str:
    project_name = bat_escape(cfg.project_name)
    venv_dir     = bat_escape(cfg.venv_dir)
    entry_mode   = bat_escape(cfg.entry_mode)
    app_entry    = bat_escape(cfg.app_entry)
    runner_args  = bat_escape(cfg.runner_args)

    webengine_block = ""
    if cfg.include_webengine_check:
        webengine_block = r'''
echo ------------------------------------------------------------
echo  Optional: PyQt6 WebEngine check
echo ------------------------------------------------------------
"%PY%" -c "from PyQt6 import QtCore; print('PyQt:', QtCore.PYQT_VERSION_STR); print('Qt   :', QtCore.QT_VERSION_STR); from PyQt6.QtWebEngineWidgets import QWebEngineView; print('[OK] WebEngine import succeeded.')"
if errorlevel 1 (
    echo.
    echo [FAIL] PyQt6 WebEngine check failed.
    echo        Possible causes: not installed, version mismatch, or DLL load error.
    echo        Run the check manually to see the full traceback:
    echo        .venv\Scripts\python.exe -c "from PyQt6.QtWebEngineWidgets import QWebEngineView"
) else (
    echo [OK] PyQt6 WebEngine is available.
)
echo.
'''

    return fr'''@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Project environment doctor
rem  Generated by Venv Batch Template Generator (KeystoneAI)
rem ============================================================

set "PROJECT_NAME={project_name}"
set "VENV_DIR={venv_dir}"
set "ENTRY_MODE={entry_mode}"
set "APP_ENTRY={app_entry}"
set "RUNNER_ARGS={runner_args}"
set "PY=%CD%\%VENV_DIR%\Scripts\python.exe"

echo ============================================================
echo  PROJECT DOCTOR: "%PROJECT_NAME%"
echo ============================================================
echo  Project: "%CD%"
echo  Mode   : %ENTRY_MODE%
echo  Entry  : "%APP_ENTRY%"
if /I "%ENTRY_MODE%"=="runner" echo  Args   : "%RUNNER_ARGS%"
echo.

if not exist "%PY%" (
    echo [FAIL] Local venv was not found:
    echo        "%PY%"
    echo.
    echo  Create it with:
    echo        python -m venv "%VENV_DIR%"
    echo        "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
    echo.
    pause
    exit /b 1
)

echo [OK] Local venv found:
echo      "%PY%"
echo.

echo ------------------------------------------------------------
echo  Python identity
echo ------------------------------------------------------------
"%PY%" -c "import sys; print('executable:', sys.executable); print('prefix    :', sys.prefix); print('version   :', sys.version)"
echo.

echo ------------------------------------------------------------
echo  Pip version
echo ------------------------------------------------------------
"%PY%" -m pip --version
echo.

echo ------------------------------------------------------------
echo  Installed packages
echo ------------------------------------------------------------
"%PY%" -m pip list
echo.

echo ------------------------------------------------------------
echo  Dependency health check
echo ------------------------------------------------------------
"%PY%" -m pip check
echo.

echo ------------------------------------------------------------
echo  Entry point check
echo ------------------------------------------------------------
if /I "%ENTRY_MODE%"=="file" (
    if exist "%APP_ENTRY%" (
        echo [OK]   Entry file found: "%APP_ENTRY%"
    ) else (
        echo [FAIL] Entry file not found: "%APP_ENTRY%"
    )
) else if /I "%ENTRY_MODE%"=="runner" (
    "%PY%" -c "import importlib.util, sys; name=r'%APP_ENTRY%'; spec=importlib.util.find_spec(name); print(('[OK]   Runner module found: ' if spec else '[FAIL] Runner module not found: ') + name); sys.exit(0 if spec else 1)"
    echo [INFO] Runner args: "%RUNNER_ARGS%"
) else (
    "%PY%" -c "import importlib.util, sys; name=r'%APP_ENTRY%'; spec=importlib.util.find_spec(name); print(('[OK]   Module found: ' if spec else '[FAIL] Module not found: ') + name); sys.exit(0 if spec else 1)"
)
echo.

echo ------------------------------------------------------------
echo  Requirements files
echo ------------------------------------------------------------
if exist "requirements.txt" (
    echo [OK]   requirements.txt found.
) else (
    echo [WARN] requirements.txt not found.
)
if exist "requirements.lock.txt" (
    echo [OK]   requirements.lock.txt found.
) else (
    echo [WARN] requirements.lock.txt not found ^(optional^).
)
echo.
{webengine_block}
echo ============================================================
echo  DOCTOR COMPLETE
echo ============================================================
pause
exit /b 0
'''


def make_test_bat(cfg: GeneratorConfig) -> str:
    project_name = bat_escape(cfg.project_name)
    venv_dir     = bat_escape(cfg.venv_dir)
    return f'''@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Project test runner
rem  Generated by Venv Batch Template Generator (KeystoneAI)
rem
rem  Runs pytest via the project-local venv Python.
rem
rem  Usage:
rem    test.bat                        (run all tests)
rem    test.bat tests/test_core.py     (run a specific file)
rem    test.bat -k mapper              (filter by name)
rem    test.bat -v --tb=short          (verbose with short tracebacks)
rem ============================================================

set "PROJECT_NAME={project_name}"
set "VENV_DIR={venv_dir}"
set "PY=%CD%\\%VENV_DIR%\\Scripts\\python.exe"

if not exist "%PY%" (
    echo [ERROR] Local venv was not found:
    echo         "%PY%"
    echo.
    echo Create it with:
    echo         python -m venv "%VENV_DIR%"
    echo.
    pause
    exit /b 1
)

title "%PROJECT_NAME% - TEST"
echo ============================================================
echo  Testing: "%PROJECT_NAME%"
echo  Python : "%PY%"
echo ============================================================
echo.

"%PY%" -m pytest -v %*
set "EXITCODE=%ERRORLEVEL%"

echo.
echo ============================================================
if "%EXITCODE%"=="0" (
    echo  TESTS PASSED
) else (
    echo  TESTS FAILED  ^(exit code: %EXITCODE%^)
)
echo ============================================================
pause
exit /b %EXITCODE%
'''


# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------

def generate_files(cfg: GeneratorConfig) -> list[Path]:
    cfg.project_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "run.bat":    make_run_bat(cfg),
        "pip.bat":    make_pip_bat(cfg),
        "shell.bat":  make_shell_bat(cfg),
        "sync.bat":   make_sync_bat(cfg),
        "doctor.bat": make_doctor_bat(cfg),
    }
    if cfg.include_test_bat:
        outputs["test.bat"] = make_test_bat(cfg)

    written: list[Path] = []
    for filename, content in outputs.items():
        path = cfg.project_dir / filename
        if path.exists() and not cfg.overwrite_existing:
            raise FileExistsError(
                f"{path.name} already exists in that folder.\n"
                "Enable 'Overwrite existing files' to replace it."
            )
        path.write_text(content, encoding="utf-8", newline="\r\n")
        written.append(path)

    if cfg.create_requirements:
        req = cfg.project_dir / "requirements.txt"
        if not req.exists():
            req.write_text("", encoding="utf-8")
            written.append(req)

    return written


def create_venv(cfg: GeneratorConfig) -> None:
    venv_path = cfg.project_dir / cfg.venv_dir
    if venv_path.exists():
        return  # already exists — caller should note this
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_path)],
        cwd=str(cfg.project_dir),
        check=True,
    )


def build_previews(cfg: GeneratorConfig) -> dict[str, str]:
    previews = {
        "run.bat":    make_run_bat(cfg),
        "pip.bat":    make_pip_bat(cfg),
        "shell.bat":  make_shell_bat(cfg),
        "sync.bat":   make_sync_bat(cfg),
        "doctor.bat": make_doctor_bat(cfg),
    }
    if cfg.include_test_bat:
        previews["test.bat"] = make_test_bat(cfg)
    return previews


# ---------------------------------------------------------------------------
# Worker thread (venv creation can be slow)
# ---------------------------------------------------------------------------

class VenvWorker(QThread):
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, cfg: GeneratorConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def run(self) -> None:
        try:
            create_venv(self.cfg)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class App(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Venv Batch Template Generator")
        self.setMinimumSize(980, 720)
        self._worker: VenvWorker | None = None
        self._last_written: list[Path] = []

        self._build_ui()
        self._status("Ready — select a project folder to begin.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 0)
        root.setSpacing(0)

        # Header
        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Venv Batch Template Generator")
        title.setObjectName("sectiontitle")
        sub = QLabel(
            "Generate project-local venv scripts for file, module, and runner-command Python projects."
        )
        sub.setObjectName("subtitle")
        header.addWidget(title)
        header.addWidget(sub)
        root.addLayout(header)
        root.addSpacing(14)

        divider = QFrame()
        divider.setObjectName("divider")
        root.addWidget(divider)
        root.addSpacing(14)

        # Main splitter: left (config) | right (preview)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = self._build_left_panel()
        splitter.addWidget(left)

        right = self._build_right_panel()
        splitter.addWidget(right)

        splitter.setSizes([480, 500])
        root.addWidget(splitter, stretch=1)

        # Status bar
        self._statusbar = QStatusBar()
        self._statusbar.setSizeGripEnabled(False)
        root.addWidget(self._statusbar)

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(420)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(10)

        layout.addWidget(self._build_project_group())
        layout.addWidget(self._build_entry_group())
        layout.addWidget(self._build_options_group())
        layout.addSpacing(4)
        layout.addLayout(self._build_action_row())
        layout.addWidget(self._build_log_panel())

        return w

    def _build_project_group(self) -> QGroupBox:
        grp = QGroupBox("Project")
        grid = self._grid_layout(grp, cols=3)

        # Row 0: folder
        grid.addWidget(QLabel("Project folder:"), 0, 0)
        self._project_dir = QLineEdit()
        self._project_dir.setPlaceholderText("C:\\\\Users\\\\you\\\\projects\\\\my_project")
        self._project_dir.textChanged.connect(self._on_project_dir_changed)
        grid.addWidget(self._project_dir, 0, 1)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_project_dir)
        grid.addWidget(btn_browse, 0, 2)

        # Row 1: name
        grid.addWidget(QLabel("Project name:"), 1, 0)
        self._project_name = QLineEdit()
        self._project_name.setPlaceholderText("Auto-filled from folder name")
        grid.addWidget(self._project_name, 1, 1)
        btn_use_folder = QPushButton("Use Folder Name")
        btn_use_folder.clicked.connect(self._use_folder_name)
        grid.addWidget(btn_use_folder, 1, 2)

        # Row 2: venv folder
        grid.addWidget(QLabel("Venv folder:"), 2, 0)
        self._venv_dir = QLineEdit(".venv")
        self._venv_dir.setMaximumWidth(140)
        grid.addWidget(self._venv_dir, 2, 1, 1, 2)

        return grp

    def _build_entry_group(self) -> QGroupBox:
        grp = QGroupBox("Entry Point")
        layout = QVBoxLayout(grp)
        layout.setSpacing(8)

        # Mode radios
        mode_row = QHBoxLayout()
        self._entry_mode_file   = QRadioButton("Python file")
        self._entry_mode_module = QRadioButton("Python module / package")
        self._entry_mode_runner = QRadioButton("Tool / runner command")
        self._entry_mode_file.setChecked(True)
        self._entry_mode_file.toggled.connect(self._on_entry_mode_changed)
        self._entry_mode_module.toggled.connect(self._on_entry_mode_changed)
        self._entry_mode_runner.toggled.connect(self._on_entry_mode_changed)
        mode_row.addWidget(self._entry_mode_file)
        mode_row.addWidget(self._entry_mode_module)
        mode_row.addWidget(self._entry_mode_runner)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Entry value
        entry_row = QHBoxLayout()
        entry_row.addWidget(QLabel("Entry / runner:"))
        self._app_entry = QLineEdit("main.py")
        entry_row.addWidget(self._app_entry, 1)
        self._btn_browse_py = QPushButton("Browse .py…")
        self._btn_browse_py.clicked.connect(self._browse_entry_file)
        entry_row.addWidget(self._btn_browse_py)
        layout.addLayout(entry_row)

        # Runner arguments
        runner_row = QHBoxLayout()
        runner_row.addWidget(QLabel("Runner args:"))
        self._runner_args = QLineEdit("jobfit.main:app --host 0.0.0.0 --port 8080 --reload")
        self._runner_args.setPlaceholderText("e.g. jobfit.main:app --host 0.0.0.0 --port 8080 --reload")
        self._runner_args.setEnabled(False)
        runner_row.addWidget(self._runner_args, 1)
        layout.addLayout(runner_row)

        hint = QLabel(
            'File: "main.py"   ·   Module: "desktop_companion"   ·   Runner: "uvicorn" + args'
        )
        hint.setObjectName("hint")
        layout.addWidget(hint)

        return grp

    def _build_options_group(self) -> QGroupBox:
        grp = QGroupBox("Options")
        layout = QVBoxLayout(grp)
        layout.setSpacing(6)

        row0 = QHBoxLayout()
        self._chk_overwrite     = QCheckBox("Overwrite existing .bat files")
        self._chk_requirements  = QCheckBox("Create requirements.txt if missing")
        self._chk_requirements.setChecked(True)
        row0.addWidget(self._chk_overwrite)
        row0.addWidget(self._chk_requirements)
        row0.addStretch()

        row1 = QHBoxLayout()
        self._chk_webengine     = QCheckBox("Include PyQt6 WebEngine check in doctor.bat")
        self._chk_webengine.setChecked(True)
        self._chk_pause         = QCheckBox("Pause when run.bat exits")
        self._chk_pause.setChecked(True)
        row1.addWidget(self._chk_webengine)
        row1.addWidget(self._chk_pause)
        row1.addStretch()

        row2 = QHBoxLayout()
        self._chk_create_venv = QCheckBox("Create .venv now  (runs python -m venv)")
        self._chk_test_bat    = QCheckBox("Include test.bat  (pytest runner)")
        row2.addWidget(self._chk_create_venv)
        row2.addWidget(self._chk_test_bat)
        row2.addStretch()

        layout.addLayout(row0)
        layout.addLayout(row1)
        layout.addLayout(row2)

        return grp

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        btn_preview  = QPushButton("⟳  Refresh Preview")
        btn_preview.clicked.connect(self._refresh_preview)
        row.addWidget(btn_preview)

        btn_generate = QPushButton("Generate Script Set")
        btn_generate.setObjectName("primary")
        btn_generate.clicked.connect(self._on_generate)
        row.addWidget(btn_generate)

        self._btn_open_folder = QPushButton("📂  Open Folder")
        self._btn_open_folder.setEnabled(False)
        self._btn_open_folder.clicked.connect(self._open_output_folder)
        row.addWidget(self._btn_open_folder)

        btn_clear = QPushButton("Clear Log")
        btn_clear.setObjectName("danger")
        btn_clear.clicked.connect(self._clear_log)
        row.addWidget(btn_clear)

        row.addStretch()
        return row

    def _build_log_panel(self) -> QPlainTextEdit:
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(180)
        self._log.setPlaceholderText("Activity log will appear here…")
        return self._log

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(440)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 0, 0, 10)
        layout.setSpacing(6)

        lbl = QLabel("Script Preview")
        lbl.setObjectName("sectiontitle")
        lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(lbl)

        hint = QLabel("Live preview of the files that will be written. Edit settings then click Refresh Preview.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._preview_tabs = QTabWidget()
        layout.addWidget(self._preview_tabs, stretch=1)

        # Create one tab per output file
        self._preview_editors: dict[str, QPlainTextEdit] = {}
        for name in ("run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat", "test.bat"):
            editor = QPlainTextEdit()
            editor.setReadOnly(True)
            BatHighlighter(editor.document())
            self._preview_editors[name] = editor
            self._preview_tabs.addTab(editor, name)

        return w

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _grid_layout(parent: QGroupBox, cols: int):
        gl = QGridLayout(parent)
        gl.setSpacing(8)
        gl.setColumnStretch(1, 1)
        return gl

    def _status(self, msg: str) -> None:
        self._statusbar.showMessage(msg)

    def _log_line(self, text: str, tag: str = "") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "ok":    "✔",
            "warn":  "⚠",
            "error": "✖",
        }.get(tag, "·")
        self._log.appendPlainText(f"[{ts}] {prefix}  {text}")
        self._log.ensureCursorVisible()

    def _clear_log(self) -> None:
        self._log.clear()

    # ------------------------------------------------------------------
    # Config reader
    # ------------------------------------------------------------------

    def _read_config(self) -> GeneratorConfig:
        project_dir_raw = self._project_dir.text().strip()
        if not project_dir_raw:
            raise ValueError("Select a project folder first.")
        project_dir  = Path(project_dir_raw)
        project_name = self._project_name.text().strip() or project_dir.name
        venv_dir     = self._venv_dir.text().strip() or ".venv"
        if self._entry_mode_runner.isChecked():
            entry_mode = "runner"
        elif self._entry_mode_module.isChecked():
            entry_mode = "module"
        else:
            entry_mode = "file"
        app_entry   = self._app_entry.text().strip()
        runner_args = self._runner_args.text().strip() if entry_mode == "runner" else ""

        if not app_entry:
            raise ValueError("Entry value is required.")

        if entry_mode in {"module", "runner"}:
            if not MODULE_RE.match(app_entry):
                label = "Runner mode" if entry_mode == "runner" else "Module mode"
                raise ValueError(
                    f"{label} expects a valid Python module name, "
                    "e.g. desktop_companion, uvicorn, or package.submodule.\n\n"
                    "Module names may only contain letters, digits, underscores, "
                    "and dots (no spaces, hyphens, or special characters)."
                )

        if entry_mode == "runner" and RUNNER_ARGS_UNSAFE_RE.search(runner_args):
            raise ValueError(
                "Runner args contain characters that are unsafe in Windows batch files.\n\n"
                "Blocked characters: & | < > ^ and double quotes.\n\n"
                "Use simple argument tokens such as:\n"
                "jobfit.main:app --host 0.0.0.0 --port 8080 --reload"
            )

        return GeneratorConfig(
            project_dir=project_dir,
            project_name=project_name,
            venv_dir=venv_dir,
            entry_mode=entry_mode,
            app_entry=app_entry,
            runner_args=runner_args,
            overwrite_existing=self._chk_overwrite.isChecked(),
            create_requirements=self._chk_requirements.isChecked(),
            include_webengine_check=self._chk_webengine.isChecked(),
            pause_on_exit=self._chk_pause.isChecked(),
            create_venv_now=self._chk_create_venv.isChecked(),
            include_test_bat=self._chk_test_bat.isChecked(),
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_project_dir_changed(self, text: str) -> None:
        if text.strip() and not self._project_name.text().strip():
            self._project_name.setText(Path(text.strip()).name)

    def _browse_project_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select project folder")
        if selected:
            self._project_dir.setText(selected)

    def _use_folder_name(self) -> None:
        value = self._project_dir.text().strip()
        if value:
            self._project_name.setText(Path(value).name)

    def _browse_entry_file(self) -> None:
        initial = self._project_dir.text().strip() or os.getcwd()
        selected, _ = QFileDialog.getOpenFileName(
            self, "Select Python entry file", initial,
            "Python files (*.py);;All files (*.*)"
        )
        if selected:
            p = Path(selected)
            project_raw = self._project_dir.text().strip()
            if project_raw:
                try:
                    self._app_entry.setText(str(p.relative_to(Path(project_raw))))
                except ValueError:
                    self._app_entry.setText(str(p))
            else:
                self._app_entry.setText(str(p))
            self._entry_mode_file.setChecked(True)

    def _on_entry_mode_changed(self, checked: bool) -> None:
        current = self._app_entry.text().strip()
        FILE_DEFAULTS   = {"main.py", "app.py", "__main__.py", ""}
        MODULE_DEFAULTS = {"desktop_companion", "app", "main", ""}
        RUNNER_DEFAULTS = {"uvicorn", "streamlit", "flask", "pytest", "PyInstaller", ""}

        if self._entry_mode_runner.isChecked():
            # Switching TO runner mode: python -m runner_module args...
            if current in FILE_DEFAULTS or current in MODULE_DEFAULTS or current.endswith(".py"):
                self._app_entry.setText("uvicorn")
            self._app_entry.setPlaceholderText("e.g. uvicorn")
            self._runner_args.setEnabled(True)
            self._btn_browse_py.setEnabled(False)
            if not self._runner_args.text().strip():
                self._runner_args.setText("jobfit.main:app --host 0.0.0.0 --port 8080 --reload")
        elif self._entry_mode_module.isChecked():
            # Switching TO module mode: python -m package_name
            if current in FILE_DEFAULTS or current in RUNNER_DEFAULTS or current.endswith(".py"):
                self._app_entry.setText("desktop_companion")
            self._app_entry.setPlaceholderText("e.g. desktop_companion")
            self._runner_args.setEnabled(False)
            self._btn_browse_py.setEnabled(False)
        else:
            # Switching TO file mode: python app.py
            if current in MODULE_DEFAULTS or current in RUNNER_DEFAULTS:
                self._app_entry.setText("main.py")
            self._app_entry.setPlaceholderText("e.g. main.py")
            self._runner_args.setEnabled(False)
            self._btn_browse_py.setEnabled(True)


    def _refresh_preview(self) -> None:
        try:
            cfg = self._read_config()
            previews = build_previews(cfg)
            for name, editor in self._preview_editors.items():
                if name in previews:
                    editor.setPlainText(previews[name])
                    # Ensure tab is visible
                    idx = self._preview_tabs.indexOf(editor)
                    if idx == -1:
                        self._preview_tabs.addTab(editor, name)
                else:
                    # Hide test.bat tab when not included
                    idx = self._preview_tabs.indexOf(editor)
                    if idx != -1:
                        self._preview_tabs.removeTab(idx)
                    editor.setPlainText("(not included — enable 'Include test.bat' to preview)")
            detail = f"{cfg.entry_mode}: {cfg.app_entry}"
            if cfg.entry_mode == "runner" and cfg.runner_args:
                detail += f" {cfg.runner_args}"
            self._status(f"Preview updated — {cfg.project_name}  [{detail}]")
        except ValueError as exc:
            self._status(f"Preview not available: {exc}")

    def _on_generate(self) -> None:
        try:
            cfg = self._read_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Configuration error", str(exc))
            return

        self._log_line(f"Generating 5-file set for: {cfg.project_dir}", "")
        detail = f"Mode: {cfg.entry_mode}  ·  Entry: {cfg.app_entry}"
        if cfg.entry_mode == "runner" and cfg.runner_args:
            detail += f"  ·  Args: {cfg.runner_args}"
        self._log_line(detail, "")

        try:
            written = generate_files(cfg)
        except FileExistsError as exc:
            self._log_line(str(exc), "error")
            QMessageBox.warning(self, "File exists", str(exc))
            return
        except Exception as exc:
            self._log_line(str(exc), "error")
            QMessageBox.critical(self, "Error", str(exc))
            return

        for path in written:
            self._log_line(path.name, "ok")

        # Refresh preview to match what was just written
        self._refresh_preview()

        # Enable open-folder
        self._last_written = written
        self._btn_open_folder.setEnabled(True)

        if cfg.create_venv_now:
            venv_path = cfg.project_dir / cfg.venv_dir
            if venv_path.exists():
                self._log_line(f".venv already exists at {venv_path} — skipped.", "warn")
                self._finish_generate(cfg)
            else:
                self._log_line("Creating .venv (this may take a moment)…", "")
                self._status("Creating .venv…")
                self._worker = VenvWorker(cfg)
                self._worker.finished.connect(lambda: self._on_venv_created(cfg))
                self._worker.error.connect(self._on_venv_error)
                self._worker.start()
        else:
            self._finish_generate(cfg)

    def _on_venv_created(self, cfg: GeneratorConfig) -> None:
        self._log_line(f".venv created at {cfg.project_dir / cfg.venv_dir}", "ok")
        self._finish_generate(cfg)

    def _on_venv_error(self, msg: str) -> None:
        self._log_line(f"venv creation failed: {msg}", "error")
        self._status("Generation complete (venv creation failed — see log).")

    def _finish_generate(self, cfg: GeneratorConfig) -> None:
        bat_count = 5 + (1 if cfg.include_test_bat else 0)
        self._log_line("Done.", "ok")
        self._status(
            f"Generated {bat_count} files -> {cfg.project_dir}   "
            f"({cfg.entry_mode}: {cfg.app_entry}"
            f"{(' ' + cfg.runner_args) if cfg.entry_mode == 'runner' and cfg.runner_args else ''})"
        )
        QMessageBox.information(
            self,
            "Generated",
            f"{bat_count} project helper files written to:\n{cfg.project_dir}"
        )

    def _open_output_folder(self) -> None:
        if self._last_written:
            folder = str(self._last_written[0].parent)
            os.startfile(folder)

    # ------------------------------------------------------------------
    # Window close — ensure worker thread is stopped
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Venv Batch Template Generator")
    app.setOrganizationName("KeystoneAI")
    app.setStyleSheet(STYLESHEET)
    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
