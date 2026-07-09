"""
Tests for create_venv(): wraps `python -m venv` / `uv venv` via subprocess.
Subprocess calls are mocked — these tests verify the *decision logic*
(which command gets built, and when it's skipped), not real venv creation.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from venv_bat_gen.core import create_venv


class TestCreateVenv:
    def test_skips_if_venv_already_exists(self, base_cfg, tmp_path):
        (tmp_path / ".venv").mkdir()
        with patch("venv_bat_gen.core.subprocess.run") as mock_run:
            create_venv(base_cfg)
        mock_run.assert_not_called()

    def test_uses_stdlib_venv_when_use_uv_false(self, base_cfg):
        with patch("venv_bat_gen.core.subprocess.run") as mock_run:
            create_venv(base_cfg)
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert args[0] == sys.executable
        assert "-m" in args and "venv" in args

    def test_uses_uv_venv_when_use_uv_true_and_uv_available(self, uv_cfg):
        with patch("shutil.which", return_value="/usr/bin/uv"), \
             patch("venv_bat_gen.core.subprocess.run") as mock_run:
            create_venv(uv_cfg)
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert args[:2] == ["uv", "venv"]

    def test_falls_back_to_stdlib_when_uv_requested_but_missing(self, uv_cfg, capsys):
        with patch("shutil.which", return_value=None), \
             patch("venv_bat_gen.core.subprocess.run") as mock_run:
            create_venv(uv_cfg)
        args = mock_run.call_args.args[0]
        assert args[0] == sys.executable
        captured = capsys.readouterr()
        assert "falling back to python -m venv" in captured.err

    def test_venv_path_is_project_dir_plus_venv_dir(self, cfg_factory, tmp_path):
        cfg = cfg_factory(venv_dir="custom_env")
        with patch("venv_bat_gen.core.subprocess.run") as mock_run:
            create_venv(cfg)
        args = mock_run.call_args.args[0]
        assert str(tmp_path / "custom_env") in args
