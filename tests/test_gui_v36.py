# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Leon Priest (7h3v01d)
"""
Headless GUI tests for the v3.6.0 additions: cross-platform Open Folder,
the manifest / .gitignore options, Load saved settings, Check Drift,
Safe Update, shared validation, and the QObject-on-QThread venv worker.
Requires the dev-gui extra; skipped when PyQt6 is missing.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from PyQt6.QtWidgets import QMessageBox  # noqa: E402

from venv_bat_gen import gui  # noqa: E402
from venv_bat_gen.core import MANIFEST_NAME, read_manifest  # noqa: E402


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    # Never block on modal dialogs.
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    w = gui.App()
    qtbot.addWidget(w)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "main.py").write_text("")
    w._project_dir.setText(str(proj))
    w._app_entry.setText("main.py")
    w._chk_webengine.setChecked(False)
    return w


def _log(w) -> str:
    return w._log.toPlainText()


def test_open_folder_is_cross_platform(window, monkeypatch):
    opened = []
    monkeypatch.setattr(gui.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    window._on_generate()
    window._open_output_folder()
    assert opened and opened[0].toLocalFile().endswith("proj")


def test_generate_writes_manifest_by_default_and_gitignore_on_request(window):
    proj = window._read_config().project_dir
    window._chk_gitignore.setChecked(True)
    window._on_generate()
    assert (proj / MANIFEST_NAME).exists()
    assert "/.venv/" in (proj / ".gitignore").read_text()


def test_manifest_checkbox_off_skips_manifest(window):
    window._chk_manifest.setChecked(False)
    window._on_generate()
    assert not (window._read_config().project_dir / MANIFEST_NAME).exists()


def test_load_saved_settings_restores_everything(window):
    window._chk_uv.setChecked(True)
    window._chk_posix.setChecked(True)
    window._venv_dir.setText("venv311")
    window._project_name.setText("Saved Name")
    window._on_generate()
    # scramble the form, then reload from .vbg.json
    window._chk_uv.setChecked(False)
    window._chk_posix.setChecked(False)
    window._venv_dir.setText(".venv")
    window._project_name.setText("Other")
    window._run_folder_scan(window._read_config().project_dir)
    assert not window._btn_load_manifest.isHidden()
    window._on_load_manifest()
    cfg = window._read_config()
    assert (cfg.use_uv, cfg.include_posix, cfg.venv_dir, cfg.project_name) == \
        (True, True, "venv311", "Saved Name")


def test_check_drift_logs_status(window):
    window._on_generate()
    window._on_check()
    assert "run.bat — match" in _log(window)
    window._chk_uv.setChecked(True)
    window._on_check()
    assert "pip.bat — drifted" in _log(window)


def test_safe_update_refreshes_untouched_and_keeps_edits(window):
    window._on_generate()
    proj = window._read_config().project_dir
    (proj / "doctor.bat").write_text("rem my edit\n")
    window._chk_uv.setChecked(True)
    window._on_update()
    assert "uv pip wrapper" in (proj / "pip.bat").read_text()
    assert (proj / "doctor.bat").read_text() == "rem my edit\n"
    assert read_manifest(proj).settings["use_uv"] is True
    assert (proj / ".vbg-backup").is_dir()


def test_invalid_venv_dir_is_rejected(window):
    window._venv_dir.setText("..\\elsewhere")
    with pytest.raises(ValueError, match="inside the project"):
        window._read_config()


def test_scan_suggests_existing_venv_folder(window):
    proj = window._read_config().project_dir
    (proj / "env").mkdir()
    (proj / "env" / "pyvenv.cfg").write_text("")
    window._run_folder_scan(proj)
    window._on_apply_scan()
    assert window._venv_dir.text() == "env"


def test_venv_worker_runs_off_thread_and_reports_back(window, qtbot, monkeypatch):
    calls = []
    monkeypatch.setattr(gui, "create_venv", lambda cfg: calls.append(cfg))
    window._chk_create_venv.setChecked(True)
    window._on_generate()
    qtbot.waitUntil(lambda: ".venv created" in _log(window), timeout=5000)
    assert len(calls) == 1
    qtbot.waitUntil(lambda: window._worker_refs == [], timeout=5000)


def test_venv_worker_failure_is_logged(window, qtbot, monkeypatch):
    def boom(cfg):
        raise OSError("disk on fire")
    monkeypatch.setattr(gui, "create_venv", boom)
    window._chk_create_venv.setChecked(True)
    window._on_generate()
    qtbot.waitUntil(lambda: "disk on fire" in _log(window), timeout=5000)
