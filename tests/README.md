# Tests

Coverage for `venv_bat_gen.core`, `venv_bat_gen.cli`, and `venv_bat_gen.gui_launcher`
— everything that doesn't require PyQt6 to import — plus a separate,
optional GUI smoke-test suite for `gui.py` itself.

## Running the core suite (no PyQt6 needed)

```bash
pip install -e ".[dev]"
pytest
```

With coverage:

```bash
pytest --cov=venv_bat_gen.core --cov=venv_bat_gen.cli --cov=venv_bat_gen.gui_launcher --cov-report=term-missing
```

Currently: **313 tests. 100% line coverage of `core.py` and `cli.py`; 92% of `gui_launcher.py`** (the one uncovered line is its `if __name__ == "__main__"` guard). This count includes `test_gui_smoke.py`, which auto-skips if PyQt6 isn't installed.

## Running the GUI smoke tests

`test_gui_smoke.py` needs the `dev-gui` extra (PyQt6 + pytest-qt) and runs headlessly via Qt's `offscreen` platform plugin — no real display required, works in CI/containers:

```bash
pip install -e ".[dev-gui]"
QT_QPA_PLATFORM=offscreen pytest tests/test_gui_smoke.py -v
```

If PyQt6 isn't installed, `pytest.importorskip("PyQt6")` at the top of the file skips the whole module cleanly rather than erroring.

## Layout

| File | Covers |
|---|---|
| `conftest.py` | Shared `GeneratorConfig` fixtures (`base_cfg`, `uv_cfg`, `runner_cfg`, `module_cfg`, `cfg_factory`) |
| `test_bat_generators.py` | Every `make_*_bat()` template (run/pip/shell/sync/doctor/test/setup) |
| `test_sh_generators.py` | Every `make_*_sh()` POSIX equivalent, including a real-bash regression test for a `set -e` early-exit bug found and fixed in `make_test_sh` |
| `test_ps1_generators.py` | Every `make_*_ps1()` PowerShell equivalent, plus `_ps1_escape` quoting behavior |
| `test_self_unpack.py` | `make_self_unpacking_setup_bat()` — companion inclusion by flag (bat/sh/ps1, independently and combined), and a byte-for-byte base64 round-trip against each standalone generator |
| `test_generate_files.py` | `build_previews()` dict shape and `generate_files()` disk-writing behavior (CRLF/LF, chmod +x, overwrite protection, requirements.txt) |
| `test_scanner.py` | `scan_project_folder()` auto-detection heuristics (venv, uv, pyproject keywords, entry-file fallback) |
| `test_presets.py` | `PresetManager` — built-ins, user save/delete, legacy-path migration, corrupt-storage resilience |
| `test_escaping.py` | `bat_escape`, `_sh_escape`, `_b64_encode`, `MODULE_RE`, `RUNNER_ARGS_UNSAFE_RE` |
| `test_create_venv.py` | `create_venv()` uv-vs-stdlib decision logic (subprocess calls mocked) |
| `test_check_drift.py` | `check_drift()` — missing/match/drifted classification, the timestamp-normalization fix, self-unpack scope, corrupted-file handling |
| `test_gui_smoke.py` | Headless PyQt6/pytest-qt smoke tests for `gui.py`: window construction, checkbox wiring, live preview tab show/hide, preset save/apply round-trips. Requires `dev-gui` extra; auto-skips otherwise |
| `test_gui_launcher.py` | `gui_launcher.main()` — friendly-error path when PyQt6 is missing (simulated via `sys.meta_path`, works whether or not PyQt6 is really installed) and delegation path when it's present |
| `test_cli.py` | The full argparse layer: subcommands (`generate`/`check`/`scan`/`presets`), `--self-unpack`/`--setup` mutex, CLI > preset > scan > default priority resolution, `MODULE_RE`/`RUNNER_ARGS_UNSAFE_RE` validation, `--preview`, `--create-venv`, `check`'s `--diff` output and exit codes, and error handling around `generate_files`/`create_venv` |

## Notes for extending

- Every generator test file follows the same shape: one `Test<Thing>` class
  per template function, one assertion per behavior. Add new cases there
  rather than starting new files, unless you're covering a genuinely new
  area of `core.py`.
- `test_self_unpack.py`'s round-trip check is the one most likely to break
  if you change how companions are embedded — if it fails, look at
  `_extract_embedded_b64()` first; it re-parses the `echo` lines the same
  way `certutil` would consume them.
- If you add a new `make_*_bat`/`make_*_sh` function, also add it to
  `build_previews()` (already required by the app) *and* to the relevant
  loop lists in `test_bat_generators.py::test_all_bat_generators_include_attribution_line`
  or `test_sh_generators.py::ALL_SH_GENERATORS`.
- `test_cli.py` always invokes `cli.main()` through the `run_cli()` helper,
  since `main()` calls `sys.exit()` on every path (success included).
  Assertions strip ANSI color codes first (`_strip_ansi()`) so they aren't
  order-dependent on whether stdout looks like a tty.
- `test_gui_launcher.py` blocks PyQt6 imports via a temporary `sys.meta_path`
  finder rather than relying on it being genuinely absent — that keeps the
  "missing PyQt6" test deterministic even on a machine with the `gui` extra
  installed (e.g. via the `dev-gui` extra).
- `test_gui_smoke.py` caught a real bug during development: `PresetManager`
  has its own internal field allowlist (`_PRESET_FIELDS`) separate from
  `GeneratorConfig`'s fields, and it's easy to add a new boolean flag to
  one without remembering the other — `save()` would then silently drop
  the new field from any preset a user saves via the GUI. `test_presets.py`
  now has a standing regression guard (`TestPresetFieldsCompleteness`) that
  fails immediately if a future bool field is ever added to `GeneratorConfig`
  without a matching entry in `_PRESET_FIELDS`.

