"""
Tests for PresetManager: built-in preset catalogue, user preset persistence,
and migration from the legacy ~/.keystoneai/ storage location.

All tests patch PresetManager's class-level storage paths to tmp_path so
we never touch the real user's home directory.
"""

from __future__ import annotations

import json

import pytest

from venv_bat_gen.core import PresetManager


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    """Redirect PresetManager storage + legacy paths into tmp_path."""
    storage_dir = tmp_path / "storage" / ".venv_bat_gen"
    legacy_dir = tmp_path / "legacy" / ".keystoneai"
    monkeypatch.setattr(PresetManager, "_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(PresetManager, "_STORAGE_FILE", storage_dir / "presets.json")
    monkeypatch.setattr(PresetManager, "_LEGACY_DIR", legacy_dir)
    monkeypatch.setattr(
        PresetManager, "_LEGACY_FILE", legacy_dir / "venv_generator_presets.json"
    )
    return storage_dir, legacy_dir


class TestBuiltinPresets:
    def test_expected_builtin_presets_present(self, isolated_paths):
        pm = PresetManager()
        names = set(pm.names())
        for expected in (
            "FastAPI / Uvicorn", "PyQt6 Desktop App", "CLI Script",
            "CLI Script (Cross-Platform)", "Streamlit App", "uv Project",
            "Repo Self-Unpack", "Repo Self-Unpack (uv)",
        ):
            assert expected in names

    def test_is_builtin_true_for_builtin(self, isolated_paths):
        pm = PresetManager()
        assert pm.is_builtin("FastAPI / Uvicorn") is True

    def test_is_builtin_false_for_unknown(self, isolated_paths):
        pm = PresetManager()
        assert pm.is_builtin("Nonexistent Preset") is False

    def test_get_returns_dict_for_builtin(self, isolated_paths):
        pm = PresetManager()
        preset = pm.get("uv Project")
        assert preset is not None
        assert preset["use_uv"] is True

    def test_get_returns_none_for_unknown(self, isolated_paths):
        pm = PresetManager()
        assert pm.get("Nonexistent Preset") is None

    def test_repo_self_unpack_presets_have_self_unpack_true(self, isolated_paths):
        pm = PresetManager()
        assert pm.get("Repo Self-Unpack")["self_unpack"] is True
        assert pm.get("Repo Self-Unpack (uv)")["self_unpack"] is True

    def test_cannot_overwrite_builtin(self, isolated_paths):
        pm = PresetManager()
        with pytest.raises(ValueError):
            pm.save("FastAPI / Uvicorn", {"venv_dir": ".venv2"})

    def test_cannot_delete_builtin(self, isolated_paths):
        pm = PresetManager()
        with pytest.raises(ValueError):
            pm.delete("FastAPI / Uvicorn")


class TestUserPresets:
    def test_save_and_reload_round_trips(self, isolated_paths):
        pm = PresetManager()
        pm.save("My Preset", {
            "venv_dir": ".venv", "entry_mode": "file", "app_entry": "main.py",
            "runner_args": "", "overwrite_existing": False,
            "create_requirements": True, "include_webengine_check": False,
            "pause_on_exit": True, "create_venv_now": False,
            "include_test_bat": False, "use_uv": False, "include_posix": False,
            "include_setup": False, "self_unpack": False,
        })

        pm2 = PresetManager()
        assert "My Preset" in pm2.names()
        assert pm2.get("My Preset")["entry_mode"] == "file"

    def test_save_persists_only_known_fields(self, isolated_paths):
        pm = PresetManager()
        pm.save("Junk Fields", {
            "venv_dir": ".venv", "entry_mode": "file", "app_entry": "main.py",
            "runner_args": "", "overwrite_existing": False,
            "create_requirements": True, "include_webengine_check": False,
            "pause_on_exit": True, "create_venv_now": False,
            "include_test_bat": False, "use_uv": False, "include_posix": False,
            "include_setup": False, "self_unpack": False,
            "not_a_real_field": "should be dropped",
        })
        stored = pm.get("Junk Fields")
        assert "not_a_real_field" not in stored

    def test_delete_removes_user_preset(self, isolated_paths):
        pm = PresetManager()
        pm.save("Temp", {"venv_dir": ".venv"})
        pm.delete("Temp")
        assert "Temp" not in PresetManager().names()

    def test_delete_unknown_user_preset_raises_keyerror(self, isolated_paths):
        pm = PresetManager()
        with pytest.raises(KeyError):
            pm.delete("Does Not Exist")

    def test_names_are_sorted(self, isolated_paths):
        pm = PresetManager()
        pm.save("Zeta", {"venv_dir": ".venv"})
        pm.save("Alpha", {"venv_dir": ".venv"})
        user_names = [n for n in pm.names() if not pm.is_builtin(n)]
        assert user_names == sorted(user_names)


class TestLegacyMigration:
    def test_migrates_legacy_presets_file_on_first_load(self, isolated_paths):
        storage_dir, legacy_dir = isolated_paths
        legacy_dir.mkdir(parents=True)
        legacy_file = legacy_dir / "venv_generator_presets.json"
        legacy_file.write_text(json.dumps({
            "Old Preset": {"venv_dir": ".venv", "entry_mode": "file"}
        }))

        pm = PresetManager()
        assert "Old Preset" in pm.names()
        assert (storage_dir / "presets.json").exists()

    def test_does_not_migrate_if_new_storage_already_exists(self, isolated_paths):
        storage_dir, legacy_dir = isolated_paths
        storage_dir.mkdir(parents=True)
        (storage_dir / "presets.json").write_text(json.dumps({
            "New Preset": {"venv_dir": ".venv"}
        }))
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "venv_generator_presets.json").write_text(json.dumps({
            "Old Preset": {"venv_dir": ".venv"}
        }))

        pm = PresetManager()
        assert "New Preset" in pm.names()
        assert "Old Preset" not in pm.names()

    def test_no_legacy_or_new_file_starts_empty(self, isolated_paths):
        pm = PresetManager()
        assert [n for n in pm.names() if not pm.is_builtin(n)] == []


class TestCorruptStorage:
    def test_malformed_json_does_not_crash_load(self, isolated_paths):
        storage_dir, _ = isolated_paths
        storage_dir.mkdir(parents=True)
        (storage_dir / "presets.json").write_text("{not valid json")

        pm = PresetManager()
        assert [n for n in pm.names() if not pm.is_builtin(n)] == []

    def test_migration_copy_failure_does_not_crash(self, isolated_paths, monkeypatch):
        _, legacy_dir = isolated_paths
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "venv_generator_presets.json").write_text(
            json.dumps({"Old Preset": {"venv_dir": ".venv"}})
        )

        def _boom(*a, **kw):
            raise OSError("permission denied")

        monkeypatch.setattr("shutil.copy2", _boom)
        pm = PresetManager()
        # Migration silently failed; no user presets loaded, no crash.
        assert [n for n in pm.names() if not pm.is_builtin(n)] == []

    def test_persist_failure_does_not_raise(self, isolated_paths, monkeypatch, capsys):
        pm = PresetManager()

        def _boom(*a, **kw):
            raise OSError("disk full")

        monkeypatch.setattr("pathlib.Path.write_text", _boom)
        pm.save("Won't Persist", {"venv_dir": ".venv"})  # should not raise
        captured = capsys.readouterr()
        assert "Could not save presets" in captured.err
