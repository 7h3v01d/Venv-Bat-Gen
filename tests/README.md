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

Currently: **476 tests** (v3.6.0). On Linux with pwsh + uv installed, everything runs except the 9 Windows-only live tests; on Windows those run too (and the bash/pty ones skip). GUI tests auto-skip if PyQt6 isn't installed.

Optional tools that enable more live tests (each skips cleanly when absent):

| Tool | Enables |
|---|---|
| `bash` (POSIX) | live execution of generated `.sh` scripts |
| `pwsh` (PowerShell 7) — or set `VBG_PWSH` | live execution of `.ps1` scripts + a 5.1-decoding parse check |
| `uv` | live `uv sync` into a custom venv folder |
| Windows (`cmd.exe`, `powershell.exe` 5.1) | `test_windows_live.py` — `.bat` under real cmd.exe, `.ps1` under real 5.1 |

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
| `test_escaping.py` | `bat_escape`, `_sh_escape`, `_b64_encode`, `MODULE_RE`, `SCRIPT_RE`, and the v3.5 runner-arg model (`parse_runner_args`, `runner_args_problem`, per-shell arg-vector emitters) |
| `test_create_venv.py` | `create_venv()` uv-vs-stdlib decision logic (subprocess calls mocked) |
| `test_check_drift.py` | `check_drift()` — missing/match/drifted classification, the timestamp-normalization fix, self-unpack scope, corrupted-file handling |
| `test_gui_smoke.py` | Headless PyQt6/pytest-qt smoke tests for `gui.py`: window construction, checkbox wiring, live preview tab show/hide, preset save/apply round-trips. Requires `dev-gui` extra; auto-skips otherwise |
| `test_gui_launcher.py` | `gui_launcher.main()` — friendly-error path when PyQt6 is missing (simulated via `sys.meta_path`, works whether or not PyQt6 is really installed) and delegation path when it's present |
| `test_runner_launch_v35.py` | The v3.5.0 runner-launch overhaul: LIVE bash execution of generated `run.sh` (glob/space/`!`/`%` arg survival, empty-args `set -u` safety, script-mode dispatch, fail-closed missing script), static `run.bat`/`run.ps1` template guards (no delayed expansion, quoted literal arg vectors, `SCRIPT_EXE` branches), doctor script-mode checks, `[project.scripts]` scanner suggestions, and CLI `--script`/quoted-args end-to-end |
| `test_regressions_v36.py` | One test per bug fixed in v3.6.0, each written first and confirmed failing on v3.5.0: PS 5.1 BOM/parse, quoted `.bat` expansions, balanced cmd blocks, trailing-backslash argv round trip, `run.sh` pause exit code, `shell.sh` rcfile quoting, single-pass `.ps1` rendering, all-or-nothing generate, self-unpack and cross-platform `check`, preset validation, scanner name matching |
| `test_features_v36.py` | `.vbg.json` manifest, `update` (refresh / skip edits / force / prune / dry-run / backups), legacy adoption against real v3.5.0 output in `fixtures/v350_project`, `.gitignore` block, scanner (venv discovery, `src/` layout), validation, cp1252-safe output, live sync/doctor exit codes, pty pause tests, live `uv sync` |
| `test_ps1_live.py` | Generated `.ps1` scripts executed by pwsh: argv fidelity, exit codes, CI pause skipping, `[ ]` folders, sync/doctor exit codes |
| `test_windows_live.py` | Windows only: `.bat` under cmd.exe in a `Tom & Jerry (x86) 100%` folder, argv round trip of hostile runner args, doctor/sync exit codes, self-unpack via certutil, Windows PowerShell 5.1 parse + argument passing |
| `test_gui_v36.py` | GUI: cross-platform Open Folder, manifest/.gitignore options, Load saved settings, Check Drift, Safe Update, validation, QObject-on-QThread venv worker |
| `test_metadata.py` | Version and licence agree across `pyproject.toml`, `core.py`, `__init__.py`, `LICENSE`; no Keystone branding |
| `helpers.py` | Not tests: CommandLineToArgvW reference parser, cmd.exe quote/block guards, PS 5.1 decoder, fake venv builders |
| `test_cli.py` | The full argparse layer: subcommands (`generate`/`check`/`scan`/`presets`), `--self-unpack`/`--setup` mutex, CLI > preset > scan > default priority resolution, `MODULE_RE`/`SCRIPT_RE`/`runner_args_problem` validation, `--preview`, `--create-venv`, `check`'s `--diff` output and exit codes, and error handling around `generate_files`/`create_venv` |

## Notes for extending

- **Fix a bug → add a test that fails without the fix first.** Run it
  against the previous release to prove it (that is how every test in
  `test_regressions_v36.py` was written).
- Template changes are cross-checked three ways: static guards
  (`helpers.unquoted_bat_refs`, `helpers.bat_block_problems`), the PowerShell
  parser, and live execution. If you add a `.bat` echo of a path or name,
  quote it.

- Every generator test file follows the same shape: one `Test<Thing>` class
  per template function, one assertion per behavior. Add new cases there
  rather than starting new files, unless you're covering a genuinely new
  area of `core.py`.
- `test_self_unpack.py`'s round-trip check is the one most likely to break
  if you change how companions are embedded — if it fails, look at
  `_extract_embedded_b64()` first; it re-parses the `echo` lines the same
  way `certutil` would consume them.
- If you add a new `make_*_bat`/`make_*_sh` function, register it in
  `_MAKERS` / `companion_names()` in `core.py` *and* add it to the relevant
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

