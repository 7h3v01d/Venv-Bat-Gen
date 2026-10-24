# SPDX-License-Identifier: Apache-2.0
# Copyright 2025-2026 Leon Priest (7h3v01d)
"""
venv_bat_gen.cli
================
Command-line interface.  Imports directly from core — no Qt.

Settings resolution (every subcommand that needs a config):

    CLI flag  >  .vbg.json manifest  >  --preset  >  inferred from existing
    scripts (check/update only, no manifest)  >  folder scan  >  default
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from .core import (
    _VERSION,
    MANIFEST_NAME,
    GeneratorConfig,
    ManifestError,
    PresetManager,
    apply_update,
    build_previews,
    check_drift,
    companion_names,
    config_problem,
    create_venv,
    generate_files,
    gitignore_entries,
    infer_settings_from_scripts,
    plan_update,
    read_manifest,
    scan_project_folder,
    update_gitignore,
)

# ---------------------------------------------------------------------------
# Terminal output (stdlib only)
# ---------------------------------------------------------------------------

class C:
    _on = sys.stdout.isatty()

    @staticmethod
    def _w(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if C._on else text

    ok     = staticmethod(lambda t: C._w("32", t))
    warn   = staticmethod(lambda t: C._w("33", t))
    err    = staticmethod(lambda t: C._w("31", t))
    bold   = staticmethod(lambda t: C._w("1",  t))
    dim    = staticmethod(lambda t: C._w("2",  t))
    accent = staticmethod(lambda t: C._w("35", t))


def _safe_console() -> None:
    """Never crash on output. When stdout/stderr is redirected on Windows,
    Python encodes with the ANSI code page (cp1252), which has no ✔ / ─ / →;
    v3.5.0 died with UnicodeEncodeError on `venv-bat-gen check . > log.txt`.
    Unencodable characters are now replaced instead."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):  # pragma: no cover - exotic streams
                pass


def _rule(width: int = 60) -> str:
    return C.dim("─" * width)


def _print_header(title: str) -> None:
    print()
    print(_rule())
    print(C.bold(f"  {title}"))
    print(_rule())


def _error(msg: str) -> None:
    print(C.err(f"[ERROR] {msg}"), file=sys.stderr)


# ---------------------------------------------------------------------------
# Shared: arguments and resolution logic common to generate / check / update
# ---------------------------------------------------------------------------

_BOOL = argparse.BooleanOptionalAction


def _add_shared_config_args(p: argparse.ArgumentParser) -> None:
    """Arguments that affect *what* would be generated. Shared between
    `generate`, `check`, and `update` so they can never disagree about what
    "the current settings" mean for a given invocation.

    Boolean options are tri-state (--x / --no-x / unset): unset means
    "inherit from the manifest / preset / scan", so a saved setting can be
    switched off from the command line as well as on."""
    p.add_argument("--preset", metavar="NAME",
                   help="Load a named preset as defaults.")

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--file",   dest="entry_mode", action="store_const", const="file",
                      help="Entry mode: python <entry>  (default)")
    mode.add_argument("--module", dest="entry_mode", action="store_const", const="module",
                      help="Entry mode: python -m <entry>")
    mode.add_argument("--runner", dest="entry_mode", action="store_const", const="runner",
                      help="Entry mode: python -m <entry> [runner-args]")
    mode.add_argument("--script", dest="entry_mode", action="store_const", const="script",
                      help="Entry mode: venv console script <entry>[.exe] [runner-args]")

    p.add_argument("--entry",       metavar="VALUE",
                   help="Entry file, module, runner, or console-script name.")
    p.add_argument("--runner-args", metavar="ARGS", default=None,
                   help="Args appended after the runner module or console script "
                        "(runner/script modes). Shell-style quoting supported: "
                        "--runner-args 'serve --name \"My App\"'")
    p.add_argument("--name",        metavar="NAME",
                   help="Project name in script headers (default: folder name).")
    p.add_argument("--venv-dir",    metavar="DIR", default=None,
                   help="Venv folder inside the project (default: .venv, or an "
                        "existing venv the scan finds).")

    p.add_argument("--webengine",   action=_BOOL, default=None,
                   help="Include the PyQt6 WebEngine check in doctor scripts.")
    p.add_argument("--pause",       action=_BOOL, default=None,
                   help="Pause when run.* exits (default: on). --no-pause disables.")
    p.add_argument("--test",        action=_BOOL, default=None,
                   help="Include test.* (pytest runner).")
    p.add_argument("--uv",          action=_BOOL, default=None,
                   help="Generate uv-flavoured scripts instead of pip.")
    p.add_argument("--posix",       action=_BOOL, default=None,
                   help="Also generate POSIX .sh equivalents.")
    p.add_argument("--powershell",  action=_BOOL, default=None,
                   help="Also generate PowerShell .ps1 equivalents.")
    p.add_argument("--setup",       action=_BOOL, default=None,
                   help="Include standalone setup.* bootstrap scripts.")
    p.add_argument("--self-unpack", action=_BOOL, default=None,
                   help=("Generate a single self-unpacking setup.bat for repo distribution "
                         "(companions embedded as base64, written via certutil on first "
                         "run). Mutually exclusive with --setup."))


_DEFAULTS: dict = {
    "venv_dir": ".venv", "entry_mode": "file", "app_entry": "main.py", "runner_args": "",
    "include_webengine_check": False, "pause_on_exit": True, "include_test_bat": False,
    "use_uv": False, "include_posix": False, "include_powershell": False,
    "include_setup": False, "self_unpack": False,
}

#: CLI dest -> GeneratorConfig field
_CLI_FIELDS = {
    "venv_dir": "venv_dir", "entry_mode": "entry_mode", "entry": "app_entry",
    "runner_args": "runner_args", "name": "project_name",
    "webengine": "include_webengine_check", "pause": "pause_on_exit",
    "test": "include_test_bat", "uv": "use_uv", "posix": "include_posix",
    "powershell": "include_powershell", "setup": "include_setup",
    "self_unpack": "self_unpack",
}


@dataclasses.dataclass
class Resolved:
    cfg: GeneratorConfig
    preset: dict
    manifest: object | None  # core.Manifest
    sources: dict[str, str]  # field -> where the value came from


def _resolve_generator_config(
    args: argparse.Namespace, folder: Path, pm: PresetManager, *, purpose: str = "generate",
) -> tuple[Resolved | None, int]:
    """
    Resolve CLI args + manifest + preset + inference + folder scan into a
    GeneratorConfig. Returns (Resolved, 0) or (None, exit_code) after
    printing the reason.

    purpose="generate" uses every scan suggestion. purpose="check"/"update"
    never use the *platform-dependent* POSIX suggestion (v3.5.0 did, so a
    project generated on Windows and checked on Linux CI always "drifted"),
    and, when there is no manifest, recover settings from the scripts
    already on disk instead.
    """
    if args.self_unpack and args.setup:
        _error("--self-unpack and --setup are mutually exclusive.")
        print("        --self-unpack already embeds the bootstrap logic inside the single file.",
              file=sys.stderr)
        return None, 1

    try:
        manifest = read_manifest(folder)
    except ManifestError as exc:
        _error(f"{exc}\n        Fix or delete {folder / MANIFEST_NAME} and re-run.")
        return None, 1

    preset: dict = {}
    if args.preset:
        preset = pm.get(args.preset) or {}
        if not preset:
            print(C.warn(f"[WARN] Preset '{args.preset}' not found — ignoring."))

    inferred: dict = {}
    if manifest is None and purpose in {"check", "update"}:
        inferred = infer_settings_from_scripts(folder)

    scan = scan_project_folder(folder, args.venv_dir or (manifest.settings.get("venv_dir")
                                                         if manifest else None) or ".venv")
    if manifest is None and purpose == "generate" and scan.hints:
        _print_header(f"Folder scan: {folder.name}")
        for h in scan.hints:
            print(f"  {h}")
        print()

    scanned: dict = {
        "venv_dir": scan.suggested_venv_dir,
        "entry_mode": scan.suggested_entry_mode,
        "app_entry": scan.suggested_app_entry,
        "runner_args": scan.suggested_runner_args,
        "use_uv": True if scan.suggested_use_uv else None,
        "include_posix": (True if scan.suggested_use_posix else None)
        if purpose == "generate" else None,
    }

    cli_vals = {f: getattr(args, d) for d, f in _CLI_FIELDS.items()}
    layers = (
        ("command line", cli_vals),
        (MANIFEST_NAME, manifest.settings if manifest else {}),
        ("preset", preset),
        ("existing scripts", inferred),
        ("folder scan", scanned),
    )

    values: dict = {}
    sources: dict[str, str] = {}
    for fld in list(_DEFAULTS) + ["project_name"]:
        for label, layer in layers:
            if layer.get(fld) is not None:
                values[fld], sources[fld] = layer[fld], label
                break
        else:
            values[fld] = _DEFAULTS.get(fld, folder.name)
            sources[fld] = "default"

    # setup / self-unpack exclusivity across layers: an explicit choice wins
    if values["self_unpack"] and values["include_setup"]:
        if args.setup:
            values["self_unpack"] = False
        else:
            values["include_setup"] = False

    cfg = GeneratorConfig(
        project_dir=folder,
        project_name=values["project_name"],
        venv_dir=values["venv_dir"],
        entry_mode=values["entry_mode"],
        app_entry=values["app_entry"],
        runner_args=values["runner_args"] if values["entry_mode"] in {"runner", "script"} else "",
        overwrite_existing=False,
        create_requirements=True,
        include_webengine_check=values["include_webengine_check"],
        pause_on_exit=values["pause_on_exit"],
        create_venv_now=False,
        include_test_bat=values["include_test_bat"],
        use_uv=values["use_uv"],
        include_posix=values["include_posix"],
        include_powershell=values["include_powershell"],
        include_setup=values["include_setup"],
        self_unpack=values["self_unpack"],
    )

    problem = config_problem(cfg)
    if problem:
        _error(problem)
        return None, 1

    return Resolved(cfg, preset, manifest, sources), 0


def _print_settings_source(res: Resolved) -> None:
    if res.manifest is not None:
        print(C.dim(f"  Settings: {MANIFEST_NAME} (saved by v{res.manifest.version})"
                    + ("" if all(v != "command line" for v in res.sources.values())
                       else " + command-line overrides")))
    elif "existing scripts" in res.sources.values():
        print(C.dim(f"  Settings: recovered from existing scripts (no {MANIFEST_NAME} yet)"))


# ---------------------------------------------------------------------------
# Subcommand: generate
# ---------------------------------------------------------------------------

def _build_generate_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "generate",
        help="Generate the helper-script set for a project folder.",
        description=(
            "Generate run, pip, shell, sync, doctor (and optionally test / setup)\n"
            "scripts in the target project folder, plus a .vbg.json manifest that\n"
            "records the settings so `check` and `update` can reproduce them.\n\n"
            "Use --self-unpack to generate a single repo-friendly setup.bat that\n"
            "bootstraps the venv and writes all companion scripts on first run.\n\n"
            "Priority: CLI flags > .vbg.json > --preset > folder auto-detect > defaults."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument("folder", type=Path, help="Project folder (created if missing).")
    _add_shared_config_args(p)

    p.add_argument("--overwrite",       action="store_true",
                   help="Overwrite existing script files.")
    p.add_argument("--no-requirements", action="store_true",
                   help="Do not create requirements.txt if missing.")
    p.add_argument("--create-venv",     action="store_true",
                   help="Create the venv immediately after generating scripts.")
    p.add_argument("--no-manifest",     action="store_true",
                   help=f"Do not write {MANIFEST_NAME}.")
    p.add_argument("--gitignore",       action="store_true",
                   help="Add/refresh a managed .gitignore block (venv, backups, and — in "
                        "self-unpack mode — the companion scripts).")
    p.add_argument("--preview",         action="store_true",
                   help="Print generated content to stdout instead of writing files.")
    p.add_argument("--list-presets",    action="store_true",
                   help="List available presets and exit.")

    return p


def _cmd_generate(args: argparse.Namespace) -> int:
    pm = PresetManager()

    if args.list_presets:
        return _cmd_presets(args)

    folder = args.folder.resolve()

    res, code = _resolve_generator_config(args, folder, pm, purpose="generate")
    if res is None:
        return code
    cfg = res.cfg

    cfg = replace(
        cfg,
        overwrite_existing=args.overwrite or res.preset.get("overwrite_existing", False),
        create_requirements=not args.no_requirements and res.preset.get("create_requirements", True),
        create_venv_now=args.create_venv or res.preset.get("create_venv_now", False),
        write_manifest=not args.no_manifest,
    )

    if args.preview:
        for name, content in build_previews(cfg).items():
            _print_header(name)
            print(content)
        return 0

    _print_header(f"Generating for: {folder}")
    _print_settings_source(res)
    mode_str  = "self-unpack" if cfg.self_unpack else cfg.entry_mode
    uv_str    = "  [uv]" if cfg.use_uv else ""
    posix_str = "  [+posix]" if cfg.include_posix else ""
    ps_str    = "  [+powershell]" if cfg.include_powershell else ""
    print(f"  Mode  : {mode_str}{uv_str}{posix_str}{ps_str}")
    print(f"  Entry : {cfg.app_entry}")
    if cfg.entry_mode in {"runner", "script"} and cfg.runner_args:
        print(f"  Args  : {cfg.runner_args}")
    print()

    try:
        written = generate_files(cfg)
    except FileExistsError as exc:
        _error(str(exc))
        return 1
    except (ValueError, OSError) as exc:
        _error(str(exc))
        return 1

    for path in written:
        print(f"  {C.ok('✔')}  {path.name}")

    if args.gitignore:
        if update_gitignore(folder, gitignore_entries(cfg)):
            print(f"  {C.ok('✔')}  .gitignore  {C.dim('(managed block updated)')}")
    elif cfg.self_unpack:
        print()
        print(C.dim("  Tip: these are written on first run — keep them out of git with"))
        print(C.dim("  `--gitignore`, or add them to .gitignore yourself:"))
        print(C.dim("\n".join("    " + n for n in companion_names(cfg))))

    if cfg.create_venv_now:
        venv_path = folder / cfg.venv_dir
        if venv_path.exists():
            print(C.warn(f"\n  [SKIP] venv already exists at {venv_path}"))
        else:
            tool = "uv venv" if cfg.use_uv else "python -m venv"
            print(f"\n  Creating venv via {tool}…")
            try:
                create_venv(cfg)
                print(C.ok(f"  ✔  venv created at {venv_path}"))
            except Exception as exc:  # noqa: BLE001 - CalledProcessError, OSError, ...
                print(C.err(f"  [ERROR] venv creation failed: {exc}"), file=sys.stderr)

    print()
    print(C.ok(f"  Done — {len(written)} file(s) written to {folder}"))
    print()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: check
# ---------------------------------------------------------------------------

def _build_check_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "check",
        help="Check whether generated files have drifted from current settings.",
        description=(
            "Recompute what `generate` would currently produce for this project\n"
            "and compare it against what's already on disk. Nothing is written.\n\n"
            "Settings come from .vbg.json when present (so the result is the same\n"
            "on every machine), otherwise they are recovered from the existing\n"
            "scripts. CLI flags override either.\n\n"
            "Exits 0 if everything matches; exits 1 if anything is missing or drifted\n"
            "— useful in CI to catch a project that's fallen behind a template change."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("folder", type=Path, help="Project folder to check.")
    _add_shared_config_args(p)
    p.add_argument("--diff", action="store_true",
                   help="Show a unified diff for each drifted file.")
    return p


def _cmd_check(args: argparse.Namespace) -> int:
    pm = PresetManager()
    folder = args.folder.resolve()

    res, code = _resolve_generator_config(args, folder, pm, purpose="check")
    if res is None:
        return code
    cfg = res.cfg

    _print_header(f"Checking: {folder}")
    _print_settings_source(res)
    entries = check_drift(cfg)

    any_issue = False
    for entry in entries:
        if entry.status == "match":
            print(f"  {C.ok('✔')}  {entry.filename}")
        elif entry.status == "missing":
            print(f"  {C.warn('○')}  {entry.filename}  {C.dim('(missing — would be created)')}")
            any_issue = True
        else:
            print(f"  {C.warn('⚠')}  {entry.filename}  {C.dim('(drifted from current settings)')}")
            any_issue = True
    print()

    if args.diff:
        for entry in entries:
            if entry.status != "drifted":
                continue
            print(_rule())
            print(C.bold(f"  {entry.filename}"))
            print(_rule())
            diff_lines = difflib.unified_diff(
                (entry.actual or "").splitlines(keepends=True),
                entry.expected.splitlines(keepends=True),
                fromfile=f"{entry.filename} (on disk)",
                tofile=f"{entry.filename} (current settings)",
            )
            sys.stdout.writelines(diff_lines)
            print()

    if any_issue:
        print(C.warn("  Drift detected — run `update` to refresh untouched scripts safely"
                     " (or `generate --overwrite`)."))
    else:
        print(C.ok("  Up to date — no drift detected."))
    print()

    return 1 if any_issue else 0


# ---------------------------------------------------------------------------
# Subcommand: update
# ---------------------------------------------------------------------------

def _build_update_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "update",
        help="Safely regenerate scripts (new templates or settings), keeping hand edits.",
        description=(
            "Regenerate a project's scripts from its saved settings (.vbg.json) —\n"
            "e.g. after upgrading venv-bat-gen — or with changed settings (flags).\n\n"
            "A file is only rewritten when it is provably untouched since it was\n"
            "generated (its fingerprint matches .vbg.json). Hand-edited or foreign\n"
            "files are skipped unless --force. Every overwritten or removed file is\n"
            "first copied to .vbg-backup/<timestamp>/.\n\n"
            "Projects generated before v3.6 have no .vbg.json: their settings are\n"
            "recovered from the existing scripts, and --adopt lets update take over\n"
            "files that carry the venv-bat-gen header.\n\n"
            "Exits 1 if any file had to be skipped."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("folder", type=Path, help="Project folder to update.")
    _add_shared_config_args(p)
    p.add_argument("--dry-run", action="store_true", help="Show the plan; write nothing.")
    p.add_argument("--force",   action="store_true",
                   help="Also overwrite edited or foreign files (backed up first).")
    p.add_argument("--adopt",   action="store_true",
                   help="No .vbg.json: take over existing venv-bat-gen scripts (backed up first).")
    p.add_argument("--prune",   action="store_true",
                   help="Remove untouched files that the settings no longer generate.")
    return p


_ACTION_STYLE = {
    "create":    ("+", C.ok),   "update": ("↻", C.ok), "unchanged": ("✔", C.dim),
    "skip":      ("⚠", C.warn), "remove": ("−", C.warn), "stale": ("○", C.warn),
}


def _cmd_update(args: argparse.Namespace) -> int:
    pm = PresetManager()
    folder = args.folder.resolve()

    res, code = _resolve_generator_config(args, folder, pm, purpose="update")
    if res is None:
        return code
    cfg = res.cfg

    if res.manifest is None and "existing scripts" not in res.sources.values() and not any(
            (folder / n).exists() for n in build_previews(cfg)):
        _error(f"Nothing to update in {folder}: no {MANIFEST_NAME} and no generated "
               "scripts. Use `generate` first.")
        return 1

    actions = plan_update(cfg, res.manifest, force=args.force, adopt=args.adopt,
                          prune=args.prune)

    _print_header(f"{'Update plan' if args.dry_run else 'Updating'}: {folder}")
    _print_settings_source(res)
    for act in actions:
        symbol, colour = _ACTION_STYLE[act.action]
        print(f"  {colour(symbol)}  {act.filename:<12} {C.dim(act.action + ' — ' + act.reason)}")
    print()

    skipped = [a for a in actions if a.action == "skip"]
    changes = [a for a in actions if a.action in {"create", "update", "remove"}]

    if not args.dry_run:
        backup = apply_update(cfg, actions, res.manifest)
        gi = folder / ".gitignore"
        if gi.exists() and "venv-bat-gen (managed block" in gi.read_text(encoding="utf-8",
                                                                          errors="replace"):
            update_gitignore(folder, gitignore_entries(cfg))
        if backup is not None:
            print(C.dim(f"  Backups: {backup}"))
        print(C.ok(f"  {len(changes)} file(s) changed; {MANIFEST_NAME} updated."))
    else:
        print(C.dim(f"  Dry run — {len(changes)} file(s) would change. Nothing written."))

    if skipped:
        hint = "--adopt" if res.manifest is None else "--force"
        print(C.warn(f"  {len(skipped)} file(s) skipped to protect local changes — "
                     f"review them, then re-run with {hint} if you want them replaced."))
    print()
    return 1 if skipped else 0


# ---------------------------------------------------------------------------
# Subcommand: scan
# ---------------------------------------------------------------------------

def _build_scan_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "scan",
        help="Inspect a project folder and show detected settings.",
        description="Scan a project folder and print what venv-bat-gen would auto-detect.",
    )
    p.add_argument("folder",    type=Path, help="Project folder to scan.")
    p.add_argument("--venv-dir", metavar="DIR", default=".venv",
                   help="Venv subdirectory to check (default: .venv).")
    p.add_argument("--json", action="store_true", help="Machine-readable output.")
    return p


def _cmd_scan(args: argparse.Namespace) -> int:
    folder = args.folder.resolve()
    scan   = scan_project_folder(folder, args.venv_dir)
    if args.json:
        data = dataclasses.asdict(scan)
        data["venv_path"] = str(scan.venv_path) if scan.venv_path else None
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    _print_header(f"Scan: {folder}")
    for h in scan.hints:
        print(f"  {h}")
    print()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: presets
# ---------------------------------------------------------------------------

def _build_presets_parser(sub) -> argparse.ArgumentParser:
    return sub.add_parser("presets", help="List available presets.")


def _cmd_presets(_args: argparse.Namespace) -> int:
    pm = PresetManager()
    _print_header("Available Presets")
    for name in pm.names():
        marker = C.dim("(built-in)") if pm.is_builtin(name) else C.accent("(user)")
        print(f"  {C.bold(name)}  {marker}")
    print()
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    _safe_console()
    parser = argparse.ArgumentParser(
        prog="venv-bat-gen",
        description=(
            f"Venv Batch Template Generator v{_VERSION}  (Leon Priest / 7h3v01d)\n"
            "Generate project-local venv helper scripts (.bat, plus optional .sh / .ps1).\n\n"
            "Quick start:\n"
            "  venv-bat-gen generate ./my_project --entry main.py\n"
            "  venv-bat-gen generate ./my_project --entry main.py --self-unpack --gitignore\n"
            "  venv-bat-gen check ./my_project\n"
            "  venv-bat-gen update ./my_project\n"
            "  venv-bat-gen scan ./my_project"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"venv-bat-gen {_VERSION}")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    _build_generate_parser(sub)
    _build_check_parser(sub)
    _build_update_parser(sub)
    _build_scan_parser(sub)
    _build_presets_parser(sub)

    args = parser.parse_args(argv)

    commands = {
        "generate": _cmd_generate, "check": _cmd_check, "update": _cmd_update,
        "scan": _cmd_scan, "presets": _cmd_presets,
    }
    if args.command in commands:
        try:
            code = commands[args.command](args)
            sys.stdout.flush()
        except BrokenPipeError:
            # Output piped into e.g. `head` that stopped reading: exit quietly
            # (Python docs' recommended handling — no traceback).
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            sys.exit(1)
        sys.exit(code)
    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
