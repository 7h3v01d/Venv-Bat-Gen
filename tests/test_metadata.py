# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Leon Priest (7h3v01d)
"""Release metadata must agree everywhere it is stated."""

from __future__ import annotations

import tomllib
from pathlib import Path

import venv_bat_gen
from venv_bat_gen.core import _VERSION

ROOT = Path(__file__).resolve().parent.parent


def test_versions_agree():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == _VERSION == venv_bat_gen.__version__


def test_license_is_apache_everywhere():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["license"]["text"] == "Apache-2.0"
    assert "Apache License" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert not any("MIT License" in c for c in pyproject["project"]["classifiers"])


def test_no_keystone_branding_in_shipped_code():
    # The legacy ~/.keystoneai preset path is still *migrated from*, so the
    # identifier may appear in core.py — but never as branding text.
    for path in (ROOT / "venv_bat_gen").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "KeystoneAI" not in text, path.name
        assert "Keystone " not in text, path.name
