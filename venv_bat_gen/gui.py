"""
venv_bat_gen.gui
================
PyQt6 GUI.  All visual logic lives here; no template strings, no file I/O.
Imports everything it needs from .core.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .core import (
    FolderScan,
    GeneratorConfig,
    MODULE_RE,
    RUNNER_ARGS_UNSAFE_RE,
    PresetManager,
    build_previews,
    create_venv,
    generate_files,
    scan_project_folder,
)


# ---------------------------------------------------------------------------
# Colour palette & stylesheet
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
    padding: 10px;
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
QLineEdit:focus {{ border-color: {PALETTE['accent']}; }}
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
QPushButton:pressed {{ background-color: {PALETTE['accent_hover']}; }}
QPushButton#primary {{
    background-color: {PALETTE['accent']};
    border-color: {PALETTE['accent']};
    color: #ffffff;
    font-weight: 600;
    font-size: 13px;
    min-height: 26px;
    padding: 5px 14px;
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
    width: 16px; height: 16px;
    border: 1px solid {PALETTE['border']};
    border-radius: 3px;
    background-color: {PALETTE['surface_alt']};
}}
QRadioButton::indicator {{ border-radius: 8px; }}
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
QTabBar::tab:hover:!selected {{ color: {PALETTE['text']}; }}
QSplitter::handle {{
    background-color: {PALETTE['border']};
    width: 1px; height: 1px;
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
QLabel#detect_hints {{
    background-color: {PALETTE['surface_alt']};
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    color: {PALETTE['text']};
    font-size: 12px;
    padding: 6px 10px;
}}
QTabWidget#lefttabs::pane {{
    border: none;
    background-color: transparent;
}}
QTabBar#lefttabs::tab {{
    background-color: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 7px 22px;
    color: {PALETTE['text_dim']};
    margin-right: 3px;
    font-size: 13px;
    font-weight: 500;
}}
QTabBar#lefttabs::tab:selected {{
    background-color: {PALETTE['surface_alt']};
    color: {PALETTE['text']};
    border-bottom: 1px solid {PALETTE['surface_alt']};
}}
QTabBar#lefttabs::tab:hover:!selected {{
    color: {PALETTE['text']};
    background-color: {PALETTE['surface_alt']};
}}
QScrollArea {{ border: none; background-color: transparent; }}
"""


# ---------------------------------------------------------------------------
# BAT syntax highlighter
# ---------------------------------------------------------------------------

class BatHighlighter(QSyntaxHighlighter):
    import re as _re
    _RE_KEYWORDS = _re.compile(
        r"\b(if|else|goto|call|set|exit|pause|title|cd|setlocal|endlocal"
        r"|for|do|in|not|exist|errorlevel|echo|where)\b",
        _re.IGNORECASE,
    )
    _RE_VARS    = _re.compile(r"%[^%\n]+%")
    _RE_STRINGS = _re.compile(r'"[^"\n]*"')

    @staticmethod
    def _fmt(hex_color: str, bold: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(hex_color))
        if bold:
            f.setFontWeight(700)
        return f

    def highlightBlock(self, text: str) -> None:
        stripped = text.lstrip()
        if stripped.lower().startswith("rem ") or stripped.lower() == "rem":
            self.setFormat(0, len(text), self._fmt(PALETTE["bat_rem"]))
            return
        if stripped.lower().startswith("echo ") or stripped.lower() == "echo.":
            self.setFormat(0, len(text), self._fmt(PALETTE["text_dim"]))
        for m in self._RE_KEYWORDS.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(),
                           self._fmt(PALETTE["bat_keyword"], bold=True))
        for m in self._RE_VARS.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt(PALETTE["bat_var"]))
        for m in self._RE_STRINGS.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt(PALETTE["bat_string"]))


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class BashHighlighter(QSyntaxHighlighter):
    """Minimal bash syntax highlighter for .sh preview tabs."""
    import re as _re
    _RE_KEYWORDS = _re.compile(
        r"\b(if|then|else|elif|fi|for|while|do|done|case|esac|in"
        r"|function|return|exit|echo|set|export|source|local|readonly"
        r"|command|cd|pwd|true|false|test|read)\b"
    )
    _RE_COMMENT  = _re.compile(r"#.*$")
    _RE_VAR      = _re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")
    _RE_STRING   = _re.compile(r'"[^"]*"')
    _RE_SHEBANG  = _re.compile(r"^#!")

    def __init__(self, document) -> None:
        super().__init__(document)

    @staticmethod
    def _fmt(hex_color: str, bold: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(hex_color))
        if bold:
            f.setFontWeight(700)
        return f

    def highlightBlock(self, text: str) -> None:
        # Shebang line
        if self._RE_SHEBANG.match(text):
            self.setFormat(0, len(text), self._fmt(PALETTE["bat_rem"]))
            return
        # Full-line comments
        if text.lstrip().startswith("#"):
            self.setFormat(0, len(text), self._fmt(PALETTE["bat_rem"]))
            return
        # Keywords
        for m in self._RE_KEYWORDS.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(),
                           self._fmt(PALETTE["bat_keyword"], bold=True))
        # Variables
        for m in self._RE_VAR.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt(PALETTE["bat_var"]))
        # Strings
        for m in self._RE_STRING.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt(PALETTE["bat_string"]))
        # Inline comments
        for m in self._RE_COMMENT.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt(PALETTE["bat_rem"]))


class PowerShellHighlighter(QSyntaxHighlighter):
    """Minimal PowerShell syntax highlighter for .ps1 preview tabs."""
    import re as _re
    _RE_KEYWORDS = _re.compile(
        r"\b(if|else|elseif|switch|foreach|for|while|do|function|return"
        r"|exit|param|try|catch|finally|begin|process|end|break|continue"
        r"|Write-Host|Read-Host|Test-Path|Join-Path|Set-Location|Get-Command)\b",
        _re.IGNORECASE,
    )
    _RE_COMMENT = _re.compile(r"#.*$")
    _RE_VAR     = _re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
    _RE_DSTRING = _re.compile(r'"[^"\n]*"')
    _RE_SSTRING = _re.compile(r"'[^'\n]*'")
    _RE_REQUIRES = _re.compile(r"^#Requires")

    def __init__(self, document) -> None:
        super().__init__(document)

    @staticmethod
    def _fmt(hex_color: str, bold: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(hex_color))
        if bold:
            f.setFontWeight(700)
        return f

    def highlightBlock(self, text: str) -> None:
        stripped = text.lstrip()
        # #Requires directive and full-line comments
        if self._RE_REQUIRES.match(stripped) or stripped.startswith("#"):
            self.setFormat(0, len(text), self._fmt(PALETTE["bat_rem"]))
            return
        # Keywords
        for m in self._RE_KEYWORDS.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(),
                           self._fmt(PALETTE["bat_keyword"], bold=True))
        # Variables ($VAR)
        for m in self._RE_VAR.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt(PALETTE["bat_var"]))
        # Double- and single-quoted strings
        for m in self._RE_DSTRING.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt(PALETTE["bat_string"]))
        for m in self._RE_SSTRING.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt(PALETTE["bat_string"]))


# ---------------------------------------------------------------------------
# Worker thread
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
# Main application window
# ---------------------------------------------------------------------------

class App(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Venv Batch Template Generator")
        self.setMinimumSize(1100, 740)
        self.resize(1200, 800)
        self._worker: VenvWorker | None = None
        self._last_written: list[Path] = []
        self._presets = PresetManager()
        self._build_ui()
        self._status("Ready — select a project folder to begin.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 0)
        root.setSpacing(0)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Venv Batch Template Generator")
        title.setObjectName("sectiontitle")
        sub = QLabel("Generate project-local venv scripts for file, module, and runner-command Python projects.")
        sub.setObjectName("subtitle")
        header.addWidget(title)
        header.addWidget(sub)
        root.addLayout(header)
        root.addSpacing(14)

        divider = QFrame()
        divider.setObjectName("divider")
        root.addWidget(divider)
        root.addSpacing(14)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([540, 760])
        root.addWidget(splitter, stretch=1)

        self._statusbar = QStatusBar()
        self._statusbar.setSizeGripEnabled(False)
        root.addWidget(self._statusbar)

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(540)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 10, 0)
        outer.setSpacing(8)

        self._left_tabs = QTabWidget()
        self._left_tabs.setObjectName("lefttabs")
        self._left_tabs.tabBar().setObjectName("lefttabs")
        self._left_tabs.addTab(self._build_configure_tab(), "⚙  Configure")
        self._left_tabs.addTab(self._build_log_tab(),       "📋  Log")
        outer.addWidget(self._left_tabs, stretch=1)

        action_w = QWidget()
        action_w.setMinimumWidth(540)
        action_layout = QHBoxLayout(action_w)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        self._populate_action_row(action_layout)
        outer.addWidget(action_w)

        return w

    def _build_configure_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._build_preset_group())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 6, 8)
        inner_layout.setSpacing(8)
        inner_layout.addWidget(self._build_project_group())
        inner_layout.addWidget(self._build_detect_banner())
        inner_layout.addWidget(self._build_entry_group())
        inner_layout.addWidget(self._build_options_group())
        inner_layout.addStretch()

        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)
        return tab

    def _build_log_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Activity log will appear here…")
        layout.addWidget(self._log, stretch=1)
        return tab

    def _build_log_panel(self) -> QPlainTextEdit:
        return self._log  # shim — log created in _build_log_tab

    def _build_preset_group(self) -> QGroupBox:
        grp = QGroupBox("Presets")
        row = QHBoxLayout(grp)
        row.setSpacing(8)

        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(200)
        self._preset_combo.setPlaceholderText("— select a preset —")
        self._preset_combo.addItems(self._presets.names())
        row.addWidget(self._preset_combo, 1)

        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self._on_preset_load)
        row.addWidget(btn_load)

        btn_save = QPushButton("Save as…")
        btn_save.clicked.connect(self._on_preset_save)
        row.addWidget(btn_save)

        self._btn_preset_delete = QPushButton("Delete")
        self._btn_preset_delete.setObjectName("danger")
        self._btn_preset_delete.clicked.connect(self._on_preset_delete)
        row.addWidget(self._btn_preset_delete)

        return grp

    def _build_project_group(self) -> QGroupBox:
        grp = QGroupBox("Project")
        grid = self._grid_layout(grp, cols=3)

        grid.addWidget(QLabel("Project folder:"), 0, 0)
        self._project_dir = QLineEdit()
        self._project_dir.setPlaceholderText("C:\\\\Users\\\\you\\\\projects\\\\my_project")
        self._project_dir.textChanged.connect(self._on_project_dir_changed)
        grid.addWidget(self._project_dir, 0, 1)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_project_dir)
        grid.addWidget(btn_browse, 0, 2)

        grid.addWidget(QLabel("Project name:"), 1, 0)
        self._project_name = QLineEdit()
        self._project_name.setPlaceholderText("Auto-filled from folder name")
        grid.addWidget(self._project_name, 1, 1)
        btn_use_folder = QPushButton("Use Folder Name")
        btn_use_folder.clicked.connect(self._use_folder_name)
        grid.addWidget(btn_use_folder, 1, 2)

        grid.addWidget(QLabel("Venv folder:"), 2, 0)
        self._venv_dir = QLineEdit(".venv")
        self._venv_dir.setMaximumWidth(140)
        grid.addWidget(self._venv_dir, 2, 1, 1, 2)

        return grp

    def _build_detect_banner(self) -> QWidget:
        self._detect_widget = QWidget()
        self._detect_widget.setVisible(False)
        outer = QVBoxLayout(self._detect_widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._detect_hints = QLabel()
        self._detect_hints.setObjectName("detect_hints")
        self._detect_hints.setWordWrap(True)
        outer.addWidget(self._detect_hints)

        btn_row = QHBoxLayout()
        self._btn_apply_scan = QPushButton("Apply suggestions")
        self._btn_apply_scan.clicked.connect(self._on_apply_scan)
        btn_row.addWidget(self._btn_apply_scan)
        btn_dismiss = QPushButton("Dismiss")
        btn_dismiss.clicked.connect(lambda: self._detect_widget.setVisible(False))
        btn_row.addWidget(btn_dismiss)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._last_scan: FolderScan | None = None
        return self._detect_widget

    def _build_entry_group(self) -> QGroupBox:
        grp = QGroupBox("Entry Point")
        layout = QVBoxLayout(grp)
        layout.setSpacing(8)

        mode_grid = QGridLayout()
        mode_grid.setHorizontalSpacing(16)
        mode_grid.setVerticalSpacing(4)
        self._entry_mode_file   = QRadioButton("Python file")
        self._entry_mode_module = QRadioButton("Python module / package")
        self._entry_mode_runner = QRadioButton("Tool / runner command")
        self._entry_mode_file.setChecked(True)
        self._entry_mode_file.toggled.connect(self._on_entry_mode_changed)
        self._entry_mode_module.toggled.connect(self._on_entry_mode_changed)
        self._entry_mode_runner.toggled.connect(self._on_entry_mode_changed)
        mode_grid.addWidget(self._entry_mode_file,   0, 0)
        mode_grid.addWidget(self._entry_mode_module, 0, 1)
        mode_grid.addWidget(self._entry_mode_runner, 1, 0)
        mode_grid.setColumnStretch(2, 1)
        layout.addLayout(mode_grid)

        entry_row = QHBoxLayout()
        entry_row.addWidget(QLabel("Entry / runner:"))
        self._app_entry = QLineEdit("main.py")
        entry_row.addWidget(self._app_entry, 1)
        self._btn_browse_py = QPushButton("Browse .py…")
        self._btn_browse_py.clicked.connect(self._browse_entry_file)
        entry_row.addWidget(self._btn_browse_py)
        layout.addLayout(entry_row)

        runner_row = QHBoxLayout()
        runner_row.addWidget(QLabel("Runner args:"))
        self._runner_args = QLineEdit("jobfit.main:app --host 0.0.0.0 --port 8080 --reload")
        self._runner_args.setPlaceholderText("e.g. jobfit.main:app --host 0.0.0.0 --port 8080 --reload")
        self._runner_args.setEnabled(False)
        runner_row.addWidget(self._runner_args, 1)
        layout.addLayout(runner_row)

        hint = QLabel('File: "main.py"   ·   Module: "desktop_companion"   ·   Runner: "uvicorn" + args')
        hint.setObjectName("hint")
        layout.addWidget(hint)

        return grp

    def _build_options_group(self) -> QGroupBox:
        grp = QGroupBox("Options")
        grid = QGridLayout(grp)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self._chk_overwrite    = QCheckBox("Overwrite existing .bat files")
        self._chk_requirements = QCheckBox("Create requirements.txt if missing")
        self._chk_requirements.setChecked(True)
        self._chk_webengine    = QCheckBox("Include WebEngine check in doctor.bat")
        self._chk_webengine.setChecked(True)
        self._chk_pause        = QCheckBox("Pause when run.bat exits")
        self._chk_pause.setChecked(True)
        self._chk_create_venv  = QCheckBox("Create .venv now  (python -m venv)")
        self._chk_test_bat     = QCheckBox("Include test.bat  (pytest runner)")
        self._chk_uv           = QCheckBox("Use uv  (faster installs)")
        self._chk_posix        = QCheckBox("Generate POSIX .sh scripts")
        self._chk_powershell   = QCheckBox("Generate PowerShell .ps1 scripts")
        self._chk_setup        = QCheckBox("Include setup script")
        self._chk_self_unpack  = QCheckBox("Repo mode: single self-unpacking setup.bat")

        grid.addWidget(self._chk_overwrite,    0, 0)
        grid.addWidget(self._chk_requirements, 0, 1)
        grid.addWidget(self._chk_webengine,    1, 0)
        grid.addWidget(self._chk_pause,        1, 1)
        grid.addWidget(self._chk_create_venv,  2, 0)
        grid.addWidget(self._chk_test_bat,     2, 1)
        grid.addWidget(self._chk_uv,           3, 0)
        grid.addWidget(self._chk_posix,        3, 1)
        grid.addWidget(self._chk_powershell,   4, 0)
        grid.addWidget(self._chk_setup,        4, 1)
        grid.addWidget(self._chk_self_unpack,  5, 0)

        # uv checkbox updates the "Create .venv" label to clarify which tool
        self._chk_uv.toggled.connect(self._on_uv_toggled)
        # self_unpack and setup are mutually exclusive
        self._chk_self_unpack.toggled.connect(self._on_self_unpack_toggled)
        self._chk_setup.toggled.connect(self._on_setup_toggled)

        return grp

    def _populate_action_row(self, row: QHBoxLayout) -> None:
        _fixed = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        btn_preview = QPushButton("⟳  Refresh Preview")
        btn_preview.setMinimumWidth(130)
        btn_preview.setSizePolicy(_fixed)
        btn_preview.clicked.connect(self._refresh_preview)
        row.addWidget(btn_preview)

        btn_generate = QPushButton("Generate Script Set")
        btn_generate.setObjectName("primary")
        btn_generate.setMinimumWidth(160)
        btn_generate.setSizePolicy(_fixed)
        btn_generate.clicked.connect(self._on_generate)
        row.addWidget(btn_generate)

        self._btn_open_folder = QPushButton("📂  Open Folder")
        self._btn_open_folder.setMinimumWidth(120)
        self._btn_open_folder.setSizePolicy(_fixed)
        self._btn_open_folder.setEnabled(False)
        self._btn_open_folder.clicked.connect(self._open_output_folder)
        row.addWidget(self._btn_open_folder)

        btn_clear = QPushButton("Clear Log")
        btn_clear.setObjectName("danger")
        btn_clear.setMinimumWidth(90)
        btn_clear.setSizePolicy(_fixed)
        btn_clear.clicked.connect(self._clear_log)
        row.addWidget(btn_clear)

        row.addStretch()

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(380)
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

        self._preview_editors: dict[str, QPlainTextEdit] = {}
        for name in ("run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat", "test.bat", "setup.bat",
                     "run.sh",  "pip.sh",  "shell.sh",  "sync.sh",  "doctor.sh",  "test.sh",  "setup.sh",
                     "run.ps1", "pip.ps1", "shell.ps1", "sync.ps1", "doctor.ps1", "test.ps1", "setup.ps1"):
            editor = QPlainTextEdit()
            editor.setReadOnly(True)
            if name.endswith(".sh"):
                BashHighlighter(editor.document())
            elif name.endswith(".ps1"):
                PowerShellHighlighter(editor.document())
            else:
                BatHighlighter(editor.document())
            self._preview_editors[name] = editor
            # .sh / .ps1 tabs hidden by default — shown when their
            # respective "generate ... equivalents" checkbox is active
            if not name.endswith(".sh") and not name.endswith(".ps1"):
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
        prefix = {"ok": "✔", "warn": "⚠", "error": "✖"}.get(tag, "·")
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
            use_uv=self._chk_uv.isChecked(),
            include_posix=self._chk_posix.isChecked(),
            include_powershell=self._chk_powershell.isChecked(),
            include_setup=self._chk_setup.isChecked(),
            self_unpack=self._chk_self_unpack.isChecked(),
        )

    # ------------------------------------------------------------------
    # Preset slots
    # ------------------------------------------------------------------

    def _on_preset_load(self) -> None:
        name = self._preset_combo.currentText()
        if not name:
            self._status("No preset selected.")
            return
        data = self._presets.get(name)
        if data is None:
            self._status(f'Preset "{name}" not found.')
            return
        self._apply_preset(data)
        self._status(f"Preset loaded: {name}")
        self._refresh_preview()

    def _on_preset_save(self) -> None:
        current    = self._preset_combo.currentText()
        suggestion = "" if self._presets.is_builtin(current) else current
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:", text=suggestion)
        if not ok or not name.strip():
            return
        name = name.strip()
        if self._presets.is_builtin(name):
            QMessageBox.warning(self, "Reserved name",
                f'"{name}" is a built-in preset and cannot be overwritten.\n'
                "Choose a different name.")
            return
        data = {
            "venv_dir":                self._venv_dir.text().strip() or ".venv",
            "entry_mode":              (
                "runner" if self._entry_mode_runner.isChecked() else
                "module" if self._entry_mode_module.isChecked() else "file"
            ),
            "app_entry":               self._app_entry.text().strip(),
            "runner_args":             self._runner_args.text().strip(),
            "overwrite_existing":      self._chk_overwrite.isChecked(),
            "create_requirements":     self._chk_requirements.isChecked(),
            "include_webengine_check": self._chk_webengine.isChecked(),
            "pause_on_exit":           self._chk_pause.isChecked(),
            "create_venv_now":         self._chk_create_venv.isChecked(),
            "include_test_bat":        self._chk_test_bat.isChecked(),
            "use_uv":                  self._chk_uv.isChecked(),
            "include_posix":           self._chk_posix.isChecked(),
            "include_powershell":      self._chk_powershell.isChecked(),
            "include_setup":           self._chk_setup.isChecked(),
            "self_unpack":             self._chk_self_unpack.isChecked(),
        }
        self._presets.save(name, data)
        self._reload_preset_combo(select=name)
        self._status(f"Preset saved: {name}")
        self._log_line(f"Preset saved: {name}", "ok")

    def _on_preset_delete(self) -> None:
        name = self._preset_combo.currentText()
        if not name:
            return
        if self._presets.is_builtin(name):
            QMessageBox.information(self, "Built-in preset",
                f'"{name}" is a built-in preset and cannot be deleted.')
            return
        confirm = QMessageBox.question(self, "Delete preset",
            f'Delete preset "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self._presets.delete(name)
            self._reload_preset_combo()
            self._status(f"Preset deleted: {name}")
            self._log_line(f"Preset deleted: {name}", "warn")

    def _apply_preset(self, data: dict) -> None:
        if "venv_dir" in data:
            self._venv_dir.setText(data["venv_dir"])
        mode = data.get("entry_mode", "file")
        if mode == "runner":
            self._entry_mode_runner.setChecked(True)
        elif mode == "module":
            self._entry_mode_module.setChecked(True)
        else:
            self._entry_mode_file.setChecked(True)
        if "app_entry"   in data: self._app_entry.setText(data["app_entry"])
        if "runner_args" in data: self._runner_args.setText(data["runner_args"])
        if "overwrite_existing"     in data: self._chk_overwrite.setChecked(data["overwrite_existing"])
        if "create_requirements"    in data: self._chk_requirements.setChecked(data["create_requirements"])
        if "include_webengine_check"in data: self._chk_webengine.setChecked(data["include_webengine_check"])
        if "pause_on_exit"          in data: self._chk_pause.setChecked(data["pause_on_exit"])
        if "create_venv_now"        in data: self._chk_create_venv.setChecked(data["create_venv_now"])
        if "include_test_bat"       in data: self._chk_test_bat.setChecked(data["include_test_bat"])
        if "use_uv"                 in data: self._chk_uv.setChecked(data["use_uv"])
        if "include_posix"          in data: self._chk_posix.setChecked(data["include_posix"])
        if "include_powershell"     in data: self._chk_powershell.setChecked(data["include_powershell"])
        if "include_setup"          in data: self._chk_setup.setChecked(data["include_setup"])
        if "self_unpack"            in data: self._chk_self_unpack.setChecked(data["self_unpack"])

    def _reload_preset_combo(self, select: str | None = None) -> None:
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItems(self._presets.names())
        if select and select in self._presets.names():
            self._preset_combo.setCurrentText(select)
        else:
            self._preset_combo.setCurrentIndex(-1)
        self._preset_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_uv_toggled(self, checked: bool) -> None:
        label = "Create .venv now  (uv venv)" if checked else "Create .venv now  (python -m venv)"
        self._chk_create_venv.setText(label)

    def _on_self_unpack_toggled(self, checked: bool) -> None:
        """When self-unpack is on, disable standalone setup (they're incompatible)."""
        if checked and self._chk_setup.isChecked():
            self._chk_setup.setChecked(False)
        self._chk_setup.setEnabled(not checked)
        self._refresh_preview()

    def _on_setup_toggled(self, checked: bool) -> None:
        """When standalone setup is on, disable self-unpack."""
        if checked and self._chk_self_unpack.isChecked():
            self._chk_self_unpack.setChecked(False)
        self._chk_self_unpack.setEnabled(not checked)

    def _on_project_dir_changed(self, text: str) -> None:
        if text.strip() and not self._project_name.text().strip():
            self._project_name.setText(Path(text.strip()).name)

    def _browse_project_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select project folder")
        if selected:
            self._project_dir.setText(selected)
            self._run_folder_scan(Path(selected))

    def _run_folder_scan(self, folder: Path) -> None:
        venv_dir = self._venv_dir.text().strip() or ".venv"
        scan = scan_project_folder(folder, venv_dir)
        self._last_scan = scan

        has_suggestions = scan.suggested_entry_mode is not None
        has_findings    = (scan.has_requirements or scan.has_pyproject
                           or scan.has_setup_py or scan.venv_found or scan.has_uv_lock)
        if not (has_suggestions or has_findings):
            self._detect_widget.setVisible(False)
            return

        self._detect_hints.setText("\n".join(scan.hints))
        self._btn_apply_scan.setVisible(
            has_suggestions or scan.suggested_use_uv or scan.suggested_use_posix
        )
        self._detect_widget.setVisible(True)

    def _on_apply_scan(self) -> None:
        if self._last_scan is None:
            return
        scan = self._last_scan
        if scan.suggested_entry_mode == "runner":
            self._entry_mode_runner.setChecked(True)
        elif scan.suggested_entry_mode == "module":
            self._entry_mode_module.setChecked(True)
        else:
            self._entry_mode_file.setChecked(True)
        if scan.suggested_app_entry:
            self._app_entry.setText(scan.suggested_app_entry)
        if scan.suggested_runner_args is not None:
            self._runner_args.setText(scan.suggested_runner_args)
        if scan.has_requirements:
            self._chk_requirements.setChecked(False)
        if scan.suggested_use_uv:
            self._chk_uv.setChecked(True)
        if scan.suggested_use_posix:
            self._chk_posix.setChecked(True)
        self._detect_widget.setVisible(False)
        self._status("Scan suggestions applied.")
        self._refresh_preview()

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
            if current in FILE_DEFAULTS or current in MODULE_DEFAULTS or current.endswith(".py"):
                self._app_entry.setText("uvicorn")
            self._app_entry.setPlaceholderText("e.g. uvicorn")
            self._runner_args.setEnabled(True)
            self._btn_browse_py.setEnabled(False)
            if not self._runner_args.text().strip():
                self._runner_args.setText("jobfit.main:app --host 0.0.0.0 --port 8080 --reload")
        elif self._entry_mode_module.isChecked():
            if current in FILE_DEFAULTS or current in RUNNER_DEFAULTS or current.endswith(".py"):
                self._app_entry.setText("desktop_companion")
            self._app_entry.setPlaceholderText("e.g. desktop_companion")
            self._runner_args.setEnabled(False)
            self._btn_browse_py.setEnabled(False)
        else:
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
                    if self._preview_tabs.indexOf(editor) == -1:
                        self._preview_tabs.addTab(editor, name)
                else:
                    # Remove tab if not in this config
                    idx = self._preview_tabs.indexOf(editor)
                    if idx != -1:
                        self._preview_tabs.removeTab(idx)
                    placeholder = (
                        "(not included — enable 'Include test.bat' to preview)"
                        if "test" in name
                        else "(not included — enable 'Include setup script' or 'Repo mode' to preview)"
                        if "setup" in name
                        else "(not included — enable 'Generate POSIX .sh scripts' to preview)"
                        if name.endswith(".sh")
                        else "(not included — enable 'Generate PowerShell .ps1 scripts' to preview)"
                        if name.endswith(".ps1")
                        else ""
                    )
                    editor.setPlainText(placeholder)
            detail = f"{cfg.entry_mode}: {cfg.app_entry}"
            if cfg.entry_mode == "runner" and cfg.runner_args:
                detail += f" {cfg.runner_args}"
            tags = []
            if cfg.use_uv:          tags.append("uv")
            if cfg.include_posix:   tags.append("posix")
            if cfg.include_setup:   tags.append("setup")
            if cfg.self_unpack:     tags.append("self-unpack")
            tag_str = "  [" + ", ".join(tags) + "]" if tags else ""
            self._status(f"Preview updated — {cfg.project_name}  [{detail}]{tag_str}")
        except ValueError as exc:
            self._status(f"Preview not available: {exc}")

    def _on_generate(self) -> None:
        try:
            cfg = self._read_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Configuration error", str(exc))
            return

        uv_tag = " [uv]" if cfg.use_uv else ""
        self._log_line(f"Generating for: {cfg.project_dir}{uv_tag}", "")
        self._left_tabs.setCurrentIndex(1)
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

        self._refresh_preview()
        self._last_written = written
        self._btn_open_folder.setEnabled(True)

        if cfg.create_venv_now:
            venv_path = cfg.project_dir / cfg.venv_dir
            if venv_path.exists():
                self._log_line(f".venv already exists at {venv_path} — skipped.", "warn")
                self._finish_generate(cfg)
            else:
                tool = "uv venv" if cfg.use_uv else "python -m venv"
                self._log_line(f"Creating .venv via {tool}…", "")
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
        file_count = len(self._last_written)
        self._log_line("Done.", "ok")
        self._status(
            f"Generated {file_count} files -> {cfg.project_dir}   "
            f"({cfg.entry_mode}: {cfg.app_entry}"
            f"{(' ' + cfg.runner_args) if cfg.entry_mode == 'runner' and cfg.runner_args else ''})"
        )
        QMessageBox.information(self, "Generated",
            f"{file_count} project helper files written to:\n{cfg.project_dir}")

    def _open_output_folder(self) -> None:
        if self._last_written:
            os.startfile(str(self._last_written[0].parent))

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
    app.setOrganizationName("Leon Priest / 7h3v01d")
    app.setStyleSheet(STYLESHEET)
    window = App()
    window.show()
    sys.exit(app.exec())
