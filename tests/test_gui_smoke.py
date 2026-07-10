"""
GUI smoke tests for venv_bat_gen.gui — specifically verifying the
`--powershell` / .ps1 wiring added alongside the CLI feature, since that
part of the change couldn't be visually verified without PyQt6 installed.

Requires the `dev-gui` extra (PyQt6 + pytest-qt); skipped automatically if
PyQt6 isn't importable. Runs via the Qt "offscreen" platform plugin, so no
real display is needed — works in CI/containers.

    pip install -e ".[dev-gui]"
    pytest tests/test_gui_smoke.py
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from venv_bat_gen.gui import App, PowerShellHighlighter  # noqa: E402
from venv_bat_gen.core import PresetManager  # noqa: E402


@pytest.fixture
def isolated_presets(tmp_path, monkeypatch):
    """Redirect PresetManager storage into tmp_path so GUI preset-save
    tests never touch the real user's home directory."""
    storage_dir = tmp_path / "storage" / ".venv_bat_gen"
    legacy_dir = tmp_path / "legacy" / ".keystoneai"
    monkeypatch.setattr(PresetManager, "_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(PresetManager, "_STORAGE_FILE", storage_dir / "presets.json")
    monkeypatch.setattr(PresetManager, "_LEGACY_DIR", legacy_dir)
    monkeypatch.setattr(
        PresetManager, "_LEGACY_FILE", legacy_dir / "venv_generator_presets.json"
    )


@pytest.fixture
def window(qtbot, tmp_path, isolated_presets):
    w = App()
    qtbot.addWidget(w)
    w._project_dir.setText(str(tmp_path))
    w._app_entry.setText("main.py")
    return w


# ---------------------------------------------------------------------------
# Window construction
# ---------------------------------------------------------------------------

class TestWindowCreation:
    def test_window_constructs_without_error(self, window):
        assert window is not None

    def test_all_checkboxes_present(self, window):
        for attr in (
            "_chk_overwrite", "_chk_requirements", "_chk_webengine", "_chk_pause",
            "_chk_create_venv", "_chk_test_bat", "_chk_uv", "_chk_posix",
            "_chk_powershell", "_chk_setup", "_chk_self_unpack",
        ):
            assert hasattr(window, attr), f"missing widget: {attr}"

    def test_powershell_checkbox_label(self, window):
        assert window._chk_powershell.text() == "Generate PowerShell .ps1 scripts"

    def test_preview_editors_include_all_three_script_families(self, window):
        names = set(window._preview_editors)
        for ext in (".bat", ".sh", ".ps1"):
            assert any(n.endswith(ext) for n in names), f"no {ext} preview editors found"

    def test_powershell_highlighter_class_importable(self):
        assert PowerShellHighlighter is not None


# ---------------------------------------------------------------------------
# Config reading (_read_config)
# ---------------------------------------------------------------------------

class TestConfigReading:
    def test_default_include_powershell_is_false(self, window):
        cfg = window._read_config()
        assert cfg.include_powershell is False

    def test_checking_box_sets_config_true(self, window):
        window._chk_powershell.setChecked(True)
        cfg = window._read_config()
        assert cfg.include_powershell is True

    def test_posix_and_powershell_are_independent_in_config(self, window):
        window._chk_posix.setChecked(True)
        window._chk_powershell.setChecked(False)
        cfg = window._read_config()
        assert cfg.include_posix is True
        assert cfg.include_powershell is False

    def test_missing_project_dir_raises(self, qtbot, isolated_presets):
        w = App()
        qtbot.addWidget(w)
        with pytest.raises(ValueError):
            w._read_config()


# ---------------------------------------------------------------------------
# Live preview refresh (_refresh_preview)
# ---------------------------------------------------------------------------

class TestPreviewRefresh:
    def test_ps1_tab_hidden_by_default(self, window):
        window._refresh_preview()
        idx = window._preview_tabs.indexOf(window._preview_editors["run.ps1"])
        assert idx == -1

    def test_ps1_tab_shows_placeholder_when_unchecked(self, window):
        window._refresh_preview()
        text = window._preview_editors["run.ps1"].toPlainText()
        assert "not included" in text
        assert "Generate PowerShell .ps1 scripts" in text

    def test_ps1_tab_appears_when_checked(self, window):
        window._chk_powershell.setChecked(True)
        window._refresh_preview()
        idx = window._preview_tabs.indexOf(window._preview_editors["run.ps1"])
        assert idx != -1

    def test_ps1_tab_content_matches_generator_output(self, window):
        window._chk_powershell.setChecked(True)
        window._refresh_preview()
        content = window._preview_editors["run.ps1"].toPlainText()
        assert content.startswith("#Requires -Version 5.1")
        assert "Set-Location -Path $PSScriptRoot" in content

    def test_unchecking_hides_tab_again(self, window):
        window._chk_powershell.setChecked(True)
        window._refresh_preview()
        window._chk_powershell.setChecked(False)
        window._refresh_preview()
        idx = window._preview_tabs.indexOf(window._preview_editors["run.ps1"])
        assert idx == -1

    def test_posix_and_powershell_tabs_are_independent_in_ui(self, window):
        window._chk_posix.setChecked(True)
        window._chk_powershell.setChecked(False)
        window._refresh_preview()
        sh_idx = window._preview_tabs.indexOf(window._preview_editors["run.sh"])
        ps1_idx = window._preview_tabs.indexOf(window._preview_editors["run.ps1"])
        assert sh_idx != -1
        assert ps1_idx == -1

    def test_both_families_visible_when_both_checked(self, window):
        window._chk_posix.setChecked(True)
        window._chk_powershell.setChecked(True)
        window._refresh_preview()
        sh_idx = window._preview_tabs.indexOf(window._preview_editors["run.sh"])
        ps1_idx = window._preview_tabs.indexOf(window._preview_editors["run.ps1"])
        assert sh_idx != -1
        assert ps1_idx != -1


# ---------------------------------------------------------------------------
# Preset apply (_apply_preset)
# ---------------------------------------------------------------------------

class TestApplyPreset:
    def test_apply_preset_checks_powershell_box(self, window):
        window._apply_preset({"include_powershell": True})
        assert window._chk_powershell.isChecked() is True

    def test_apply_preset_unchecks_powershell_box(self, window):
        window._chk_powershell.setChecked(True)
        window._apply_preset({"include_powershell": False})
        assert window._chk_powershell.isChecked() is False

    def test_apply_preset_missing_key_leaves_state_unchanged(self, window):
        window._chk_powershell.setChecked(True)
        window._apply_preset({})  # no include_powershell key present
        assert window._chk_powershell.isChecked() is True


# ---------------------------------------------------------------------------
# Preset save (_on_preset_save) — the actual button-wired method
# ---------------------------------------------------------------------------

class TestSavePreset:
    def test_saved_preset_includes_powershell_flag(self, window, monkeypatch):
        from PyQt6.QtWidgets import QInputDialog

        monkeypatch.setattr(
            QInputDialog, "getText",
            staticmethod(lambda *args, **kwargs: ("SmokeTestPreset", True)),
        )

        window._chk_powershell.setChecked(True)
        window._on_preset_save()

        saved = window._presets.get("SmokeTestPreset")
        assert saved is not None
        assert saved["include_powershell"] is True

    def test_saved_preset_reflects_unchecked_state(self, window, monkeypatch):
        from PyQt6.QtWidgets import QInputDialog

        monkeypatch.setattr(
            QInputDialog, "getText",
            staticmethod(lambda *args, **kwargs: ("AnotherPreset", True)),
        )

        window._chk_powershell.setChecked(False)
        window._on_preset_save()

        saved = window._presets.get("AnotherPreset")
        assert saved["include_powershell"] is False
