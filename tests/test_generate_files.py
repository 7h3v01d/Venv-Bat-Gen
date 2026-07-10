"""
Tests for build_previews() (in-memory {filename: content} map) and
generate_files() (actually writes scripts to disk).
"""

from __future__ import annotations

import os
import stat
import sys

import pytest

from venv_bat_gen.core import build_previews, generate_files


# ---------------------------------------------------------------------------
# build_previews
# ---------------------------------------------------------------------------

class TestBuildPreviews:
    def test_default_set_of_five_bat_scripts(self, base_cfg):
        previews = build_previews(base_cfg)
        assert set(previews) == {
            "run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat",
        }

    def test_test_bat_added_when_flagged(self, cfg_factory):
        cfg = cfg_factory(include_test_bat=True)
        assert "test.bat" in build_previews(cfg)

    def test_setup_bat_added_when_flagged(self, cfg_factory):
        cfg = cfg_factory(include_setup=True)
        assert "setup.bat" in build_previews(cfg)

    def test_posix_scripts_added_when_flagged(self, cfg_factory):
        cfg = cfg_factory(include_posix=True, include_test_bat=True, include_setup=True)
        previews = build_previews(cfg)
        for name in ("run.sh", "pip.sh", "shell.sh", "sync.sh", "doctor.sh",
                     "test.sh", "setup.sh"):
            assert name in previews

    def test_no_posix_test_sh_without_test_bat_flag(self, cfg_factory):
        cfg = cfg_factory(include_posix=True, include_test_bat=False)
        assert "test.sh" not in build_previews(cfg)

    def test_powershell_scripts_added_when_flagged(self, cfg_factory):
        cfg = cfg_factory(include_powershell=True, include_test_bat=True, include_setup=True)
        previews = build_previews(cfg)
        for name in ("run.ps1", "pip.ps1", "shell.ps1", "sync.ps1", "doctor.ps1",
                     "test.ps1", "setup.ps1"):
            assert name in previews

    def test_no_powershell_test_ps1_without_test_bat_flag(self, cfg_factory):
        cfg = cfg_factory(include_powershell=True, include_test_bat=False)
        assert "test.ps1" not in build_previews(cfg)

    def test_posix_and_powershell_are_independent(self, cfg_factory):
        cfg = cfg_factory(include_posix=True, include_powershell=False)
        previews = build_previews(cfg)
        assert "run.sh" in previews
        assert "run.ps1" not in previews

    def test_self_unpack_returns_only_setup_bat(self, cfg_factory):
        cfg = cfg_factory(self_unpack=True, include_test_bat=True, include_posix=True)
        previews = build_previews(cfg)
        assert set(previews) == {"setup.bat"}


# ---------------------------------------------------------------------------
# generate_files
# ---------------------------------------------------------------------------

class TestGenerateFiles:
    def test_writes_all_expected_files(self, base_cfg, tmp_path):
        written = generate_files(base_cfg)
        names = {p.name for p in written}
        assert {"run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat"} <= names
        for name in ("run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat"):
            assert (tmp_path / name).exists()

    def test_creates_project_dir_if_missing(self, cfg_factory, tmp_path):
        new_dir = tmp_path / "nested" / "project"
        cfg = cfg_factory(project_dir=new_dir)
        generate_files(cfg)
        assert new_dir.is_dir()
        assert (new_dir / "run.bat").exists()

    def test_bat_files_written_with_crlf(self, base_cfg, tmp_path):
        generate_files(base_cfg)
        raw = (tmp_path / "run.bat").read_bytes()
        assert b"\r\n" in raw

    def test_sh_files_written_with_lf_only(self, cfg_factory, tmp_path):
        cfg = cfg_factory(include_posix=True)
        generate_files(cfg)
        raw = (tmp_path / "run.sh").read_bytes()
        assert b"\r\n" not in raw
        assert b"\n" in raw

    def test_sh_files_marked_executable(self, cfg_factory, tmp_path):
        # os.chmod's execute bits are a POSIX concept; NTFS has no user
        # execute permission to set, so core.generate_files()'s chmod call
        # is a correct no-op on Windows. Only assert the bit on POSIX.
        if sys.platform == "win32":
            pytest.skip("execute bit is not a meaningful concept on Windows/NTFS")
        cfg = cfg_factory(include_posix=True)
        generate_files(cfg)
        mode = os.stat(tmp_path / "run.sh").st_mode
        assert mode & stat.S_IXUSR

    def test_ps1_files_written_with_crlf(self, cfg_factory, tmp_path):
        cfg = cfg_factory(include_powershell=True)
        generate_files(cfg)
        raw = (tmp_path / "run.ps1").read_bytes()
        assert b"\r\n" in raw

    def test_ps1_files_marked_executable(self, cfg_factory, tmp_path):
        # Mainly useful for `pwsh` on Linux/macOS (`./run.ps1`); harmless
        # no-op on Windows/NTFS for the same reason as .sh above.
        if sys.platform == "win32":
            pytest.skip("execute bit is not a meaningful concept on Windows/NTFS")
        cfg = cfg_factory(include_powershell=True)
        generate_files(cfg)
        mode = os.stat(tmp_path / "run.ps1").st_mode
        assert mode & stat.S_IXUSR

    def test_bat_files_not_forced_executable_bit_untouched(self, base_cfg, tmp_path):
        # Not a strict requirement on Windows, but we shouldn't crash or
        # special-case .bat files through the chmod path.
        generate_files(base_cfg)
        assert (tmp_path / "run.bat").exists()

    def test_creates_empty_requirements_when_missing_and_flagged(self, base_cfg, tmp_path):
        written = generate_files(base_cfg)
        assert (tmp_path / "requirements.txt").exists()
        assert any(p.name == "requirements.txt" for p in written)
        assert (tmp_path / "requirements.txt").read_text() == ""

    def test_does_not_overwrite_existing_requirements(self, base_cfg, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
        generate_files(base_cfg)
        assert (tmp_path / "requirements.txt").read_text() == "requests==2.31.0\n"

    def test_no_requirements_created_when_flag_disabled(self, cfg_factory, tmp_path):
        cfg = cfg_factory(create_requirements=False)
        generate_files(cfg)
        assert not (tmp_path / "requirements.txt").exists()

    def test_no_requirements_created_in_self_unpack_mode(self, cfg_factory, tmp_path):
        cfg = cfg_factory(self_unpack=True, create_requirements=True)
        generate_files(cfg)
        assert not (tmp_path / "requirements.txt").exists()

    def test_raises_if_file_exists_and_overwrite_disabled(self, base_cfg, tmp_path):
        (tmp_path / "run.bat").write_text("old content")
        with pytest.raises(FileExistsError):
            generate_files(base_cfg)

    def test_overwrites_when_flagged(self, cfg_factory, tmp_path):
        (tmp_path / "run.bat").write_text("old content")
        cfg = cfg_factory(overwrite_existing=True)
        generate_files(cfg)
        assert "old content" not in (tmp_path / "run.bat").read_text()

    def test_self_unpack_writes_only_setup_bat(self, cfg_factory, tmp_path):
        cfg = cfg_factory(self_unpack=True)
        written = generate_files(cfg)
        assert {p.name for p in written} == {"setup.bat"}
        assert (tmp_path / "setup.bat").exists()
        assert not (tmp_path / "run.bat").exists()
