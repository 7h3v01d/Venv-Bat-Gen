"""
Tests for make_self_unpacking_setup_bat(): the single-file, repo-friendly
bootstrap script that embeds every companion script as base64 and decodes
them with certutil on first run.
"""

from __future__ import annotations

import base64
import re

from venv_bat_gen.core import (
    make_doctor_bat,
    make_pip_bat,
    make_run_bat,
    make_run_sh,
    make_self_unpacking_setup_bat,
    make_shell_bat,
    make_sync_bat,
    make_test_bat,
)


def _extract_embedded_b64(setup_content: str, filename: str) -> str:
    """
    Pull the base64 payload for `filename` out of the generated setup.bat
    by reproducing the same "echo <line>" scan the real script performs.
    """
    tag = f'set "OUTFILE={filename}"'
    assert tag in setup_content, f"{filename} block not found in setup.bat"

    start = setup_content.index(tag)
    # The block ends at the next "rem ──" marker or end of decode section.
    next_marker = setup_content.find("rem ── ", start + len(tag))
    block = setup_content[start:next_marker] if next_marker != -1 else setup_content[start:]

    lines = re.findall(r"^\s*echo (.*)$", block, flags=re.MULTILINE)
    # Content uses \r\n line endings; strip the trailing \r that `.` (which
    # matches \r but not \n) would otherwise capture as part of the line.
    lines = [ln.rstrip("\r") for ln in lines]
    # Drop trailing echoes that belong to status reporting, not payload —
    # every payload line is pure base64 (no spaces, no brackets).
    b64_lines = [ln for ln in lines if re.fullmatch(r"[A-Za-z0-9+/=]+", ln)]
    return "".join(b64_lines)


class TestSelfUnpackingSetupBat:
    def test_default_companions_present(self, base_cfg):
        content = make_self_unpacking_setup_bat(base_cfg)
        for name in ("run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat"):
            assert f'set "OUTFILE={name}"' in content

    def test_test_bat_only_embedded_when_flagged(self, cfg_factory):
        without = cfg_factory(self_unpack=True, include_test_bat=False)
        with_flag = cfg_factory(self_unpack=True, include_test_bat=True)
        assert 'OUTFILE=test.bat' not in make_self_unpacking_setup_bat(without)
        assert 'OUTFILE=test.bat' in make_self_unpacking_setup_bat(with_flag)

    def test_posix_scripts_only_embedded_when_flagged(self, cfg_factory):
        without = cfg_factory(self_unpack=True, include_posix=False)
        with_flag = cfg_factory(self_unpack=True, include_posix=True)
        assert 'OUTFILE=run.sh' not in make_self_unpacking_setup_bat(without)
        assert 'OUTFILE=run.sh' in make_self_unpacking_setup_bat(with_flag)

    def test_existing_files_are_never_overwritten(self, base_cfg):
        content = make_self_unpacking_setup_bat(base_cfg)
        assert 'if exist "%OUTFILE%" (' in content
        assert "[SKIP]" in content

    def test_reports_fail_when_certutil_unavailable(self, base_cfg):
        content = make_self_unpacking_setup_bat(base_cfg)
        assert "[FAIL]" in content
        assert "certutil" in content.lower()

    def test_pip_mode_bootstrap_uses_stdlib_venv(self, base_cfg):
        content = make_self_unpacking_setup_bat(base_cfg)
        assert "python -m venv" in content
        assert "where python" in content

    def test_uv_mode_bootstrap_uses_uv_venv(self, uv_cfg):
        content = make_self_unpacking_setup_bat(uv_cfg)
        assert "uv venv" in content
        assert "where uv" in content

    def test_bootstrap_skips_venv_creation_if_present(self, base_cfg):
        content = make_self_unpacking_setup_bat(base_cfg)
        assert "already exists" in content

    # -- Round-trip: the embedded base64 payload decodes back to exactly
    #    what the standalone generator would have produced -----------------

    def test_run_bat_payload_round_trips(self, base_cfg):
        setup_content = make_self_unpacking_setup_bat(base_cfg)
        b64 = _extract_embedded_b64(setup_content, "run.bat")
        decoded = base64.b64decode(b64).decode("utf-8")

        expected = make_run_bat(base_cfg).replace("\n", "\r\n")
        assert decoded == expected

    def test_doctor_bat_payload_round_trips(self, base_cfg):
        setup_content = make_self_unpacking_setup_bat(base_cfg)
        b64 = _extract_embedded_b64(setup_content, "doctor.bat")
        decoded = base64.b64decode(b64).decode("utf-8")

        expected = make_doctor_bat(base_cfg).replace("\n", "\r\n")
        assert decoded == expected

    def test_sh_payload_uses_lf_not_crlf(self, cfg_factory):
        cfg = cfg_factory(self_unpack=True, include_posix=True)
        setup_content = make_self_unpacking_setup_bat(cfg)
        b64 = _extract_embedded_b64(setup_content, "run.sh")
        decoded = base64.b64decode(b64).decode("utf-8")

        expected = make_run_sh(cfg).replace("\n", "\n")  # LF, unchanged
        assert decoded == expected
        assert "\r\n" not in decoded

    def test_bat_payload_uses_crlf(self, base_cfg):
        setup_content = make_self_unpacking_setup_bat(base_cfg)
        b64 = _extract_embedded_b64(setup_content, "pip.bat")
        decoded = base64.b64decode(b64).decode("utf-8")
        assert "\r\n" in decoded

    def test_full_companion_set_round_trips(self, cfg_factory):
        """Every embedded script, across the full feature matrix, decodes
        back to byte-identical content produced by its standalone maker."""
        cfg = cfg_factory(
            self_unpack=True, include_test_bat=True, include_posix=True, use_uv=True,
        )
        setup_content = make_self_unpacking_setup_bat(cfg)

        checks = {
            "run.bat": make_run_bat(cfg),
            "pip.bat": make_pip_bat(cfg),
            "shell.bat": make_shell_bat(cfg),
            "sync.bat": make_sync_bat(cfg),
            "doctor.bat": make_doctor_bat(cfg),
            "test.bat": make_test_bat(cfg),
        }
        for filename, expected_lf in checks.items():
            b64 = _extract_embedded_b64(setup_content, filename)
            decoded = base64.b64decode(b64).decode("utf-8")
            assert decoded == expected_lf.replace("\n", "\r\n"), filename
