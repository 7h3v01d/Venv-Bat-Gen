"""
Shared pytest fixtures for venv_bat_gen tests.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from venv_bat_gen.core import GeneratorConfig


def make_config(tmp_path: Path, **overrides) -> GeneratorConfig:
    """Build a GeneratorConfig with sane defaults, overridable per-test."""
    defaults = dict(
        project_dir=tmp_path,
        project_name="MyProject",
        venv_dir=".venv",
        entry_mode="file",
        app_entry="main.py",
        runner_args="",
        overwrite_existing=False,
        create_requirements=True,
        include_webengine_check=False,
        pause_on_exit=True,
        create_venv_now=False,
        include_test_bat=False,
        use_uv=False,
        include_posix=False,
        include_powershell=False,
        include_setup=False,
        self_unpack=False,
    )
    defaults.update(overrides)
    return GeneratorConfig(**defaults)


@pytest.fixture
def base_cfg(tmp_path) -> GeneratorConfig:
    """A minimal, default 'file' mode pip-based config."""
    return make_config(tmp_path)


@pytest.fixture
def uv_cfg(tmp_path) -> GeneratorConfig:
    """Same as base_cfg but with use_uv=True."""
    return make_config(tmp_path, use_uv=True)


@pytest.fixture
def runner_cfg(tmp_path) -> GeneratorConfig:
    """A 'runner' mode config (e.g. uvicorn-style)."""
    return make_config(
        tmp_path,
        entry_mode="runner",
        app_entry="uvicorn",
        runner_args="app.main:app --host 0.0.0.0 --port 8000 --reload",
    )


@pytest.fixture
def module_cfg(tmp_path) -> GeneratorConfig:
    """A 'module' mode config (e.g. python -m mypackage)."""
    return make_config(tmp_path, entry_mode="module", app_entry="mypackage")


@pytest.fixture
def cfg_factory(tmp_path):
    """Factory fixture: cfg_factory(**overrides) -> GeneratorConfig."""
    def _factory(**overrides):
        return make_config(tmp_path, **overrides)
    return _factory


def with_cfg(cfg: GeneratorConfig, **overrides) -> GeneratorConfig:
    """Convenience: derive a new frozen GeneratorConfig from an existing one."""
    return replace(cfg, **overrides)
