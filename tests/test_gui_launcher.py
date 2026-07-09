"""
Tests for venv_bat_gen.gui_launcher — the thin wrapper that lets
`venv-bat-gen-gui` / `python -m venv_bat_gen` fail with an actionable
message instead of a bare ModuleNotFoundError when PyQt6 (the `gui`
optional extra) isn't installed.

Both the failure path and the success path are simulated via sys.modules /
sys.meta_path so these tests are deterministic whether or not PyQt6 is
actually installed in the environment running pytest.
"""

from __future__ import annotations

import sys
import types

import pytest


class _BlockPyQt6Finder:
    """A meta_path finder that makes any `PyQt6*` import fail, regardless
    of whether PyQt6 is genuinely installed."""

    def find_spec(self, name, path, target=None):
        if name == "PyQt6" or name.startswith("PyQt6."):
            raise ImportError(f"simulated: {name} is not installed")
        return None


@pytest.fixture
def block_pyqt6(monkeypatch):
    # Evict any already-imported PyQt6* modules and venv_bat_gen.gui itself
    # (it does `from PyQt6.X import Y` at module scope, so a cached copy
    # would make this fixture a no-op), then block all future PyQt6 imports.
    for name in list(sys.modules):
        if name == "PyQt6" or name.startswith("PyQt6.") or name == "venv_bat_gen.gui":
            monkeypatch.delitem(sys.modules, name, raising=False)

    finder = _BlockPyQt6Finder()
    sys.meta_path.insert(0, finder)
    yield
    sys.meta_path.remove(finder)


class TestGuiLauncherMissingPyQt6:
    def test_exits_with_status_1(self, block_pyqt6):
        from venv_bat_gen import gui_launcher

        with pytest.raises(SystemExit) as excinfo:
            gui_launcher.main()
        assert excinfo.value.code == 1

    def test_prints_install_hint_to_stderr(self, block_pyqt6, capsys):
        from venv_bat_gen import gui_launcher

        with pytest.raises(SystemExit):
            gui_launcher.main()
        captured = capsys.readouterr()
        assert "pip install venv-bat-gen[gui]" in captured.err
        assert "PyQt6" in captured.err

    def test_mentions_cli_as_an_alternative(self, block_pyqt6, capsys):
        from venv_bat_gen import gui_launcher

        with pytest.raises(SystemExit):
            gui_launcher.main()
        captured = capsys.readouterr()
        assert "venv-bat-gen generate" in captured.err

    def test_includes_underlying_import_error(self, block_pyqt6, capsys):
        from venv_bat_gen import gui_launcher

        with pytest.raises(SystemExit):
            gui_launcher.main()
        captured = capsys.readouterr()
        assert "underlying error" in captured.err

    def test_does_not_write_anything_to_stdout(self, block_pyqt6, capsys):
        from venv_bat_gen import gui_launcher

        with pytest.raises(SystemExit):
            gui_launcher.main()
        captured = capsys.readouterr()
        assert captured.out == ""


class TestGuiLauncherWithPyQt6Available:
    def test_delegates_to_real_gui_main(self, monkeypatch):
        calls = []
        fake_gui = types.ModuleType("venv_bat_gen.gui")
        fake_gui.main = lambda: calls.append("called")
        monkeypatch.setitem(sys.modules, "venv_bat_gen.gui", fake_gui)

        # Force re-import of the launcher's local import statement to pick
        # up the fake module rather than any previously cached real one.
        monkeypatch.delitem(sys.modules, "venv_bat_gen.gui_launcher", raising=False)
        from venv_bat_gen import gui_launcher

        gui_launcher.main()
        assert calls == ["called"]

    def test_does_not_swallow_exceptions_raised_by_real_gui_main(self, monkeypatch):
        fake_gui = types.ModuleType("venv_bat_gen.gui")

        def _boom():
            raise RuntimeError("something else broke")

        fake_gui.main = _boom
        monkeypatch.setitem(sys.modules, "venv_bat_gen.gui", fake_gui)
        monkeypatch.delitem(sys.modules, "venv_bat_gen.gui_launcher", raising=False)
        from venv_bat_gen import gui_launcher

        with pytest.raises(RuntimeError, match="something else broke"):
            gui_launcher.main()
