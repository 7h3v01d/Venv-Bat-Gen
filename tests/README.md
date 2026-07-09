# Tests

Coverage for `venv_bat_gen.core` — the Qt-free module containing every
template generator, the file writer, the folder scanner, and the preset
system. `cli.py` and `gui.py` are not covered here (the latter needs
PyQt6 + a display; `core.py` is intentionally the part that's safe and
fast to test in isolation).

## Running

```bash
pip install -e ".[dev]"
pytest
```

With coverage:

```bash
pytest --cov=venv_bat_gen.core --cov-report=term-missing
```

Currently: **167 tests, 100% line coverage of `core.py`**.

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
