# Changelog

All notable changes to venv-bat-gen. Every fix listed under "Fixed" was
reproduced first and is covered by a test that fails without it
(`tests/test_regressions_v36.py` and friends).

## v3.6.0

### Added
- **Project manifest (`.vbg.json`)** — `generate` records the settings that
  determine script content plus a fingerprint of each generated file.
  `check`, `update`, and a re-run `generate` all read it, so results no
  longer depend on which machine runs them. `--no-manifest` / GUI checkbox
  to opt out. A damaged or newer-schema manifest is reported, never ignored.
- **`update` subcommand** (GUI: *Safe Update…*) — regenerates scripts after a
  venv-bat-gen upgrade or a settings change, rewriting a file only when its
  fingerprint proves it is untouched. Hand-edited and foreign files are
  skipped (exit 1) unless `--force`; `--prune` removes untouched files the
  settings no longer generate; `--dry-run` shows the plan. Every overwritten
  or removed file is backed up to `.vbg-backup/<timestamp>/`.
- **Legacy adoption** — for projects generated before v3.6 (no manifest),
  settings are recovered from the scripts' own headers (including from the
  payloads inside a self-unpacking `setup.bat`), so `check` needs no flags
  and `update --adopt` upgrades them in one step.
- **Tri-state CLI options** — `--posix/--no-posix`, `--uv/--no-uv`,
  `--test/--no-test`, `--powershell/--no-powershell`, `--setup/--no-setup`,
  `--self-unpack/--no-self-unpack`, `--webengine/--no-webengine`,
  `--pause/--no-pause`, so saved settings can be switched off as well as on.
- **Non-interactive mode** — every pause is skipped when `CI` or
  `VBG_NO_PAUSE` is set (`.bat` via `%VBG_PAUSE%`, `.ps1` via
  `Invoke-VbgPause`); `.sh` scripts only pause on a terminal.
- **Honest exit codes** — `sync.*` exits 1 when an install or `pip check`
  fails (it used to report `SYNC COMPLETE` and exit 0); `doctor.*` exits 1
  when any `[FAIL]` is found; `setup.*` exits 1 on a failed install or
  failed companion decode.
- **pyproject-aware sync/setup** — with no `requirements.txt`, an
  installable `pyproject.toml` (`[project]` table) is installed with
  `pip install -e .`; tool-config-only pyprojects are left alone. `generate`
  no longer seeds an empty `requirements.txt` that would shadow this.
- **`--gitignore`** (GUI: *Manage a .gitignore block*) — a marked, idempotent
  block for the venv, `.vbg-backup/`, and repo-mode companion scripts.
- **Smarter scanner** — parses `pyproject.toml` with `tomllib` and matches
  dependency *names* (from `[project]`, optional/dependency groups, Poetry,
  and `requirements.txt`); finds an existing venv under any folder name
  (`venv`, `env`, `venv311`, …) via `pyvenv.cfg`; detects packages with
  `__main__.py` at the root or in a `src/` layout; reports manifests and
  unparseable pyprojects. `scan --json` for tooling.
- **Shared fail-closed validation** for CLI and GUI — venv folder must be a
  relative path inside the project with no shell-hostile characters;
  project names without control characters; file entries without quotes.
- **GUI** — *Load saved settings* when a folder has a `.vbg.json`, *Check
  Drift* and *Safe Update…* buttons (with legacy adoption prompt), manifest
  and `.gitignore` options, scanner venv suggestion; the venv worker now
  uses the QObject-on-QThread pattern instead of a QThread subclass that
  shadowed `QThread.finished`.
- **Tests** — 476 tests. New: live execution of generated `.ps1` scripts
  with PowerShell 7 (fake Windows-layout venv), a PowerShell-parser check of
  every `.ps1` as Windows PowerShell 5.1 would decode it, a live `uv sync`
  test, pty-driven pause tests, static cmd.exe guards (quoted expansions,
  balanced blocks, no unescaped `)` in block echoes), a CommandLineToArgvW
  reference parser for the `.bat` argument round trip, legacy-adoption
  tests against real v3.5.0 output (`tests/fixtures/v350_project`), and
  Windows-only live tests (`tests/test_windows_live.py`) that run the
  `.bat` files under cmd.exe and the `.ps1` files under Windows
  PowerShell 5.1 in folders like `Tom & Jerry (x86) 100%`.

### Fixed
1. **`shell.ps1` failed to parse on Windows PowerShell 5.1** — `.ps1` files
   were written without a BOM, so 5.1 decoded them as ANSI; an em dash in a
   string became U+201D, which PowerShell treats as a closing quote. All
   `.ps1` files (standalone and embedded) now carry a UTF-8 BOM, templates
   are pure ASCII, and non-ASCII project names survive.
2. **`.bat` banners broke on `&` / `^` / `|` / `<` / `>`** in project names
   or folder paths (`echo  Project : %CD%` in `C:\Tom & Jerry\` ran `Jerry`
   as a command). Every user- or filesystem-derived expansion in `echo` and
   `title` lines is now quoted.
3. **Runner args ending in a backslash were corrupted in `run.bat`** —
   `C:\out\` reached the program as `C:\out"`. Trailing backslashes are now
   doubled before the closing quote (CRT argv rules); Windows PowerShell 5.1
   legacy argument passing is compensated for in `run.ps1`.
4. **The self-unpacking `setup.bat` dropped `!` from project names** —
   delayed expansion is no longer used at all.
5. **`check` always reported drift for self-unpack projects** — timestamps
   inside the base64 payloads were compared raw. Payloads are now decoded
   and normalised before comparison (and `--diff` shows readable text).
6. **`check` was platform-dependent** — the POSIX auto-suggestion meant a
   project generated on Windows always "drifted" when checked on Linux CI.
7. **`generate` wrote partial output** — files before the first conflict were
   written, then it raised. Conflicts are now all detected (and all listed)
   before anything is written; each file is written atomically.
8. **`run.sh` with pause turned exit 0 into exit 1** under non-tty stdin
   (`read` hit EOF under `set -e`).
9. **`shell.sh` broke on an apostrophe** in the project path or name (the
   rcfile was assembled with single quotes); it now uses `printf %q`, and
   prompt-expansion characters are dropped from the prompt label.
10. **Every `.ps1` failed in folders containing `[` or `]`** —
    `Set-Location -Path` treats brackets as wildcards; now `-LiteralPath`.
11. **GUI "Open Folder" crashed on Linux/macOS** (`os.startfile` is
    Windows-only); now `QDesktopServices`.
- Also: the CLI crashed with `UnicodeEncodeError` when its output was
  redirected on Windows (cp1252); `--preset` could never set the venv
  folder (the CLI default masked it); `uv sync` ignored a custom venv folder
  (`UV_PROJECT_ENVIRONMENT` is now set); uv-mode `doctor` ran `pip`, which
  uv-created venvs don't have; keyword detection matched substrings
  (`click` in `clickhouse-driver`); a corrupt user preset could shadow a
  built-in or list it twice; `.ps1` templates were substituted in several
  passes, so a project named `__VENV_DIR__` was rewritten; piping CLI
  output into `head` printed a `BrokenPipeError` traceback.

### Changed
- **Licence**: `LICENSE` and package metadata are now Apache-2.0, matching
  the README (the file still said "MIT / KeystoneAI").
- **Lint**: explicit ruff rule set plus a pinned ruff version, so the CI
  lint gate can't go red when ruff's defaults change (it was failing on
  v3.5.0 for exactly that reason).
- CI adds Python 3.14, installs uv for the live uv test, and runs the GUI
  tests (`test_gui_smoke.py` + `test_gui_v36.py`) with the Qt system
  libraries installed.
- `shell.bat` now uses `setlocal`, so leaving the venv shell no longer
  leaves the calling console activated.
- GUI placeholders no longer reference other projects (`jobfit`,
  `desktop_companion`).
- SPDX headers on all source and test files.

## v3.5.0
- **Runner args rebuilt as a literal argument vector** — `--runner-args` is
  now parsed once with shell-style quoting (shlex) and emitted into every
  template as an individually quoted literal vector: quoted tokens in
  `run.bat`, a bash array (`set -u`-safe on bash 3.2) in `run.sh`, a
  splatted array literal in `run.ps1`. Fixes three v3.4 correctness bugs:
  `run.sh` word-split **and glob-expanded** args against the project
  directory (`--include *.py` silently became the folder's actual .py
  files); `run.bat` generation silently deleted double quotes, making
  spaced arguments impossible; `run.ps1` re-split the string on whitespace
  at runtime. The old blanket ban on `& | < > ^ "` is replaced by
  fail-closed validation of genuinely unrepresentable input only
  (unbalanced quotes, embedded literal `"`, quoted newlines).
- **New `script` entry mode** — `--script` (CLI) / "Console script" (GUI)
  runs the venv's own console-script binary
  (`.venv\Scripts\<name>.exe`, `.venv/bin/<name>` on POSIX) with a
  fail-closed existence check and a "fix with `pip.bat install -e .`"
  error path, wired through run/doctor in all three shells.
- **Scanner: `[project.scripts]` now suggests script mode** — previously it
  suggested `python -m <module>` on the entry's right-hand module path,
  which silently does nothing when that module lacks an
  `if __name__ == "__main__"` guard. Script names are now matched
  case-preserved (the whole pyproject was previously lowercased before
  matching).
- **`run.bat` no longer enables delayed expansion** — it never needed it,
  and it corrupted any `!` in passthrough `%*` arguments or runner args.
  (The self-unpacking `setup.bat` keeps its delayed expansion, which it
  genuinely requires.)
- **New regression suite** — `tests/test_runner_launch_v35.py` (20 tests),
  including live execution of generated `run.sh` against a fake venv
  proving glob/space/`!`/`%` survival, empty-args `set -u` safety, script
  dispatch, and fail-closed missing-script behaviour. Each headline fix
  proven to be caught by its test via revert.
- **Cleanup** — removed dead `_UV_INDICATORS` constant; removed a leftover
  "KeystoneAI" reference in the `__init__.py` docstring.

**Also shipping in v3.5.0** (completed earlier but previously unreleased):
- **GUI smoke-tested for real** — added `tests/test_gui_smoke.py` (PyQt6 + pytest-qt, runs headlessly via Qt's `offscreen` platform, `dev-gui` extra). This caught a real bug: `PresetManager`'s internal field allowlist hadn't been updated for the new `include_powershell` flag, so saving a custom preset via the GUI silently dropped that setting. Fixed, plus a standing regression guard so it can't happen again for any future flag.
- **New PowerShell (`.ps1`) variant** — `--powershell` (CLI) / "Generate PowerShell .ps1 scripts" (GUI) generates `.ps1` equivalents of every script, targeting the PowerShell 5.1 that ships with Windows (no `pwsh`/PowerShell 7 required). Useful where `.bat` execution is blocked by policy but PowerShell is allowed. Independent of `--posix`; both can be enabled together. Also embeds correctly in `--self-unpack` mode alongside `.bat`/`.sh`. Along the way, fixed a pre-existing bug in `make_test_sh`: under `set -euo pipefail`, an unguarded pytest invocation meant bash would abort the script on test failure before the pass/fail banner or correct exit code ever ran.
- **New `check` subcommand** — `venv-bat-gen check <folder>` recomputes what `generate` would currently produce (same CLI flag > preset > folder auto-detect > default priority) and compares it against what's on disk, without writing anything. Exits 1 if anything is missing or drifted (handy in CI after a template upgrade), 0 if up to date. `--diff` shows a unified diff per drifted file. The one-time `Generated on: <timestamp>` line is ignored for comparison so `check` doesn't false-positive purely from time passing.
- **PyQt6 is now optional** — moved to a `gui` extra (`pip install venv-bat-gen[gui]`). The CLI has zero dependencies. `venv-bat-gen-gui` / `python -m venv_bat_gen` (no args) now exit with an actionable install hint instead of a bare `ModuleNotFoundError` when PyQt6 isn't installed.
- **Test suite** — added `tests/`, covering every template generator (bat/sh/ps1), the self-unpacking round-trip, the folder scanner, the preset system, drift detection, and the full CLI argparse layer (100% line coverage of `core.py` and `cli.py`).
- **CI** — GitHub Actions workflow running the test suite across Windows/macOS/Linux × Python 3.11–3.13, a `ruff` lint gate, and package build verification.
- **Lint cleanup** — removed 3 unused imports and 2 stray f-string prefixes; the codebase's deliberate compact `if x: y` one-liner style is now a documented, project-wide `ruff` ignore (`E701`) rather than unaddressed noise.
- **Fixed stale metadata** — `__init__.py`'s `__version__`/`__author__` now match `pyproject.toml` and the current `Leon Priest / 7h3v01d` branding; project URLs across `README.md` and `pyproject.toml` now consistently point to `github.com/7h3v01d/Venv-Bat-Gen`.

## v3.4.0
- **Repo mode** — new `--self-unpack` CLI flag and "Repo mode" GUI checkbox. Generates a single `setup.bat` containing all companion scripts encoded as base64, decoded via `certutil` on first run. Safe to re-run — existing files are never overwritten.
- **Two new presets** — `Repo Self-Unpack` and `Repo Self-Unpack (uv)`
- **Branding** — updated throughout to `Leon Priest / 7h3v01d`
- **Preset storage** — moved from `~/.keystoneai/` to `~/.venv_bat_gen/`; automatic migration on first run
- **`--self-unpack` + `--setup` mutex** — these are mutually exclusive; the CLI errors clearly if both are passed
- **`certutil` failure detection** — the generated `setup.bat` now checks whether each output file was actually created and reports `[FAIL]` with a clear message if certutil is unavailable
- **GUI** — `self_unpack` checkbox disables standalone `setup` option and vice versa; round-trips through preset save/load

## v3.3.x
- uv support, POSIX `.sh` scripts, project folder scanner, preset system

