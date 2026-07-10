"""
Tests for check_drift() and DriftEntry — the comparison logic behind the
`venv-bat-gen check` subcommand.
"""

from __future__ import annotations

from venv_bat_gen.core import check_drift, generate_files


class TestCheckDrift:
    def test_all_missing_when_nothing_generated_yet(self, base_cfg):
        entries = check_drift(base_cfg)
        statuses = {e.filename: e.status for e in entries}
        assert statuses["run.bat"] == "missing"
        assert all(s == "missing" for s in statuses.values())

    def test_missing_entry_has_no_actual_text(self, base_cfg):
        entries = check_drift(base_cfg)
        run_bat = next(e for e in entries if e.filename == "run.bat")
        assert run_bat.actual is None
        assert run_bat.expected  # still has the expected content

    def test_all_match_immediately_after_generate(self, base_cfg):
        generate_files(base_cfg)
        entries = check_drift(base_cfg)
        assert all(e.status == "match" for e in entries)

    def test_match_status_has_identical_expected_and_actual(self, base_cfg):
        generate_files(base_cfg)
        entries = check_drift(base_cfg)
        for e in entries:
            assert e.expected == e.actual

    def test_drift_detected_when_content_changes(self, cfg_factory):
        from dataclasses import replace

        cfg = cfg_factory(project_name="Original")
        generate_files(cfg)

        renamed_cfg = replace(cfg, project_name="Renamed")
        entries = check_drift(renamed_cfg)
        run_bat = next(e for e in entries if e.filename == "run.bat")
        assert run_bat.status == "drifted"
        assert "Original" in run_bat.actual
        assert "Renamed" in run_bat.expected

    def test_unaffected_files_still_match_when_only_some_drift(self, cfg_factory):
        from dataclasses import replace

        # project_name only appears in run.bat/shell.bat/etc headers, not in
        # every file identically — but changing use_uv affects pip.bat's
        # actual logic while doctor.bat's non-uv-specific lines may not
        # differ in every branch. Simplest robust case: change something
        # that clearly only affects one or two files.
        cfg = cfg_factory(pause_on_exit=True)
        generate_files(cfg)

        changed_cfg = replace(cfg, pause_on_exit=False)
        entries = check_drift(changed_cfg)
        statuses = {e.filename: e.status for e in entries}
        # run.bat/run.sh embed the pause behavior; pip.bat does not.
        assert statuses["run.bat"] == "drifted"
        assert statuses["pip.bat"] == "match"

    def test_generation_timestamp_alone_does_not_count_as_drift(self, base_cfg, monkeypatch):
        import venv_bat_gen.core as core_module
        from datetime import datetime as real_datetime

        generate_files(base_cfg)

        class _LaterDatetime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return real_datetime(2099, 1, 1, 0, 0)

        monkeypatch.setattr(core_module, "datetime", _LaterDatetime)
        entries = check_drift(base_cfg)
        assert all(e.status == "match" for e in entries), (
            "check_drift must ignore the 'Generated on: <timestamp>' line; "
            "otherwise every file would show as drifted on every run."
        )

    def test_expected_and_actual_have_normalized_timestamp_placeholder(self, base_cfg):
        generate_files(base_cfg)
        entries = check_drift(base_cfg)
        run_bat = next(e for e in entries if e.filename == "run.bat")
        assert "Generated on: <normalized>" in run_bat.expected
        assert "Generated on: <normalized>" in run_bat.actual

    def test_self_unpack_mode_only_checks_setup_bat(self, cfg_factory):
        cfg = cfg_factory(self_unpack=True)
        generate_files(cfg)
        entries = check_drift(cfg)
        assert [e.filename for e in entries] == ["setup.bat"]
        assert entries[0].status == "match"

    def test_requirements_txt_is_never_checked(self, base_cfg):
        generate_files(base_cfg)
        entries = check_drift(base_cfg)
        assert "requirements.txt" not in {e.filename for e in entries}

    def test_sh_files_compared_with_lf_semantics(self, cfg_factory):
        cfg = cfg_factory(include_posix=True)
        generate_files(cfg)
        entries = check_drift(cfg)
        run_sh = next(e for e in entries if e.filename == "run.sh")
        assert run_sh.status == "match"

    def test_ps1_files_compared_with_crlf_semantics(self, cfg_factory):
        cfg = cfg_factory(include_powershell=True)
        generate_files(cfg)
        entries = check_drift(cfg)
        run_ps1 = next(e for e in entries if e.filename == "run.ps1")
        assert run_ps1.status == "match"

    def test_corrupted_file_on_disk_is_detected_as_drifted(self, cfg_factory, tmp_path):
        cfg = cfg_factory()
        generate_files(cfg)
        (tmp_path / "run.bat").write_bytes(b"not a valid batch file at all")
        entries = check_drift(cfg)
        run_bat = next(e for e in entries if e.filename == "run.bat")
        assert run_bat.status == "drifted"

    def test_does_not_write_or_modify_anything(self, base_cfg, tmp_path):
        generate_files(base_cfg)
        before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
        check_drift(base_cfg)
        after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
        assert before == after
