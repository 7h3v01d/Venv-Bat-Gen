# Tests

Coverage for `venv_bat_gen.core`, `venv_bat_gen.cli`, and `venv_bat_gen.gui_launcher`
— everything that doesn't require PyQt6 to import. `gui.py` itself isn't
covered here (it needs the `gui` extra installed plus a display; `pytest-qt`
is available via the `dev-gui` extra for anyone who wants to add that later).

## Running

```bash
pip install -e ".[dev]"
pytest
```

With coverage:

```bash
pytest --cov=venv_bat_gen.core --cov=venv_bat_gen.cli --cov=venv_bat_gen.gui_launcher --cov-report=term-missing
```

Currently: **213 tests. 100% line coverage of `core.py` and `cli.py`; 92% of `gui_launcher.py`** (the one uncovered line is its `if __name__ == "__main__"` guard).

## Layout

| File | Covers |
|---|---|
| `conftest.py` | Shared `GeneratorConfig` fixtures (`base_cfg`, `uv_cfg`, `runner_cfg`, `module_cfg`, `cfg_factory`) |
| `test_bat_generators.py` | Every `make_*_bat()` template (run/pip/shell/sync/doctor/test/setup) |
| `test_sh_generators.py` | Every `make_*_sh()` POSIX equivalent |
| `test_self_unpack.py` | `make_self_unpacking_setup_bat()` — companion inclusion by flag, and a byte-for-byte base64 round-trip against each standalone generator |
| `test_generate_files.py` | `build_previews()` dict shape and `generate_files()` disk-writing behavior (CRLF/LF, chmod +x, overwrite protection, requirements.txt) |
| `test_scanner.py` | `scan_project_folder()` auto-detection heuristics (venv, uv, pyproject keywords, entry-file fallback) |
| `test_presets.py` | `PresetManager` — built-ins, user save/delete, legacy-path migration, corrupt-storage resilience |
| `test_escaping.py` | `bat_escape`, `_sh_escape`, `_b64_encode`, `MODULE_RE`, `RUNNER_ARGS_UNSAFE_RE` |
| `test_create_venv.py` | `create_venv()` uv-vs-stdlib decision logic (subprocess calls mocked) |
| `test_gui_launcher.py` | `gui_launcher.main()` — friendly-error path when PyQt6 is missing (simulated via `sys.meta_path`, works whether or not PyQt6 is really installed) and delegation path when it's present |
| `test_cli.py` | The full argparse layer: subcommands (`generate`/`scan`/`presets`), `--self-unpack`/`--setup` mutex, CLI > preset > scan > default priority resolution, `MODULE_RE`/`RUNNER_ARGS_UNSAFE_RE` validation, `--preview`, `--create-venv`, and error handling around `generate_files`/`create_venv` |

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

