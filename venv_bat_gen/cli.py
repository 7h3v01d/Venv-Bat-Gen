"""
venv_bat_gen.cli
================
Command-line interface.  Imports directly from core — no Qt, no MagicMock.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from dataclasses import replace
from pathlib import Path

from .core import (
    GeneratorConfig,
    PresetManager,
    MODULE_RE,
    RUNNER_ARGS_UNSAFE_RE,
    _VERSION,
    build_previews,
    check_drift,
    create_venv,
    generate_files,
    scan_project_folder,
)


# ---------------------------------------------------------------------------
# Terminal colours (stdlib only)
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


def _rule(width: int = 60) -> str:
    return C.dim("─" * width)


def _print_header(title: str) -> None:
    print()
    print(_rule())
    print(C.bold(f"  {title}"))
    print(_rule())


# ---------------------------------------------------------------------------
# Shared: arguments and resolution logic common to `generate` and `check`
# ---------------------------------------------------------------------------

def _add_shared_config_args(p: argparse.ArgumentParser) -> None:
    """Arguments that affect *what* would be generated. Shared between
    `generate` and `check` so both subcommands can never disagree about
    what "the current settings" mean for a given invocation."""
    p.add_argument("--preset", metavar="NAME",
                   help="Load a named preset as defaults.")

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--file",   dest="entry_mode", action="store_const", const="file",
                      help="Entry mode: python <entry>  (default)")
    mode.add_argument("--module", dest="entry_mode", action="store_const", const="module",
                      help="Entry mode: python -m <entry>")
    mode.add_argument("--runner", dest="entry_mode", action="store_const", const="runner",
                      help="Entry mode: python -m <entry> [runner-args]")

    p.add_argument("--entry",       metavar="VALUE",
                   help="Entry file, module, or runner.")
    p.add_argument("--runner-args", metavar="ARGS", default="",
                   help="Args appended after runner module (runner mode only).")
    p.add_argument("--name",        metavar="NAME",
                   help="Project name in .bat headers (default: folder name).")
    p.add_argument("--venv-dir",    metavar="DIR", default=".venv",
                   help="Venv subdirectory name (default: .venv).")

    p.add_argument("--webengine",       action="store_true",
                   help="Include PyQt6 WebEngine check in doctor.bat.")
    p.add_argument("--no-pause",        action="store_true",
                   help="Do not pause run.bat on exit.")
    p.add_argument("--test",            action="store_true",
                   help="Include test.bat (pytest runner).")
    p.add_argument("--uv",              action="store_true",
                   help="Generate uv-flavoured scripts instead of pip.")
    p.add_argument("--posix",           action="store_true",
                   help="Also generate POSIX .sh equivalents.")
    p.add_argument("--powershell",      action="store_true",
                   help="Also generate PowerShell .ps1 equivalents.")
    p.add_argument("--setup",           action="store_true",
                   help="Include a standalone setup.bat bootstrap script.")
    p.add_argument("--self-unpack",     action="store_true",
                   help=(
                       "Generate a single self-unpacking setup.bat for repo distribution. "
                       "Encodes all companion scripts as base64 and writes them via certutil "
                       "on first run. Mutually exclusive with --setup."
                   ))


def _resolve_generator_config(
    args: argparse.Namespace, folder: Path, pm: PresetManager,
) -> tuple[GeneratorConfig | None, dict, int]:
    """
    Resolve CLI args + preset + folder scan into a GeneratorConfig, using
    CLI flag > preset > scan suggestion > hardcoded default priority.

    Returns (cfg, preset_data, 0) on success, or (None, {}, exit_code) if
    resolution should abort (mutex violation or invalid entry point).
    Prints folder-scan hints / preset-not-found warnings as a side effect.

    overwrite_existing / create_requirements / create_venv_now are set to
    harmless placeholder values here (GeneratorConfig has no field defaults
    of its own) — they only affect generate_files()'s write behavior, never
    generated *content*, so callers that only need content (like `check`)
    can use the result as-is; `generate` merges its own write-behavior
    flags in afterwards via dataclasses.replace().
    """
    if args.self_unpack and args.setup:
        print(C.err("[ERROR] --self-unpack and --setup are mutually exclusive."), file=sys.stderr)
        print("        --self-unpack already embeds the bootstrap logic inside the single file.")
        return None, {}, 1

    project_name = args.name or folder.name

    preset_data: dict = {}
    if args.preset:
        preset_data = pm.get(args.preset) or {}
        if not preset_data:
            print(C.warn(f"[WARN] Preset '{args.preset}' not found — ignoring."))

    # Auto-detect from folder (lower priority than explicit flags)
    scan = scan_project_folder(folder, args.venv_dir)
    if scan.hints:
        _print_header(f"Folder scan: {folder.name}")
        for h in scan.hints:
            print(f"  {h}")
        print()

    # Resolve each setting: CLI flag > preset > scan suggestion > hardcoded default
    def _pick(cli_val, preset_key, scan_val, default):
        if cli_val is not None:
            return cli_val
        if preset_key in preset_data:
            return preset_data[preset_key]
        if scan_val is not None:
            return scan_val
        return default

    entry_mode  = _pick(args.entry_mode,  "entry_mode", scan.suggested_entry_mode,  "file")
    app_entry   = _pick(args.entry,       "app_entry",  scan.suggested_app_entry,   "main.py")
    runner_args = _pick(args.runner_args or None, "runner_args", scan.suggested_runner_args, "")
    use_uv      = _pick(True if args.uv else None, "use_uv", scan.suggested_use_uv if scan.suggested_use_uv else None, False)
    include_pos = _pick(True if args.posix else None, "include_posix", scan.suggested_use_posix if scan.suggested_use_posix else None, False)
    include_ps1 = _pick(True if args.powershell else None, "include_powershell", None, False)

    self_unpack = args.self_unpack or preset_data.get("self_unpack", False)

    cfg = GeneratorConfig(
        project_dir=folder,
        project_name=project_name,
        venv_dir=args.venv_dir,
        entry_mode=entry_mode,
        app_entry=app_entry or "main.py",
        runner_args=runner_args or "",
        overwrite_existing=False,
        create_requirements=True,
        include_webengine_check=args.webengine or preset_data.get("include_webengine_check", False),
        pause_on_exit=not args.no_pause and preset_data.get("pause_on_exit", True),
        create_venv_now=False,
        include_test_bat=args.test or preset_data.get("include_test_bat", False),
        use_uv=use_uv,
        include_posix=include_pos,
        include_powershell=include_ps1,
        include_setup=args.setup or preset_data.get("include_setup", False),
        self_unpack=self_unpack,
    )

    # Validate entry point
    if cfg.entry_mode in {"module", "runner"}:
        if not MODULE_RE.match(cfg.app_entry):
            print(C.err(f"[ERROR] Invalid module name: '{cfg.app_entry}'"), file=sys.stderr)
            return None, {}, 1
    if cfg.entry_mode == "runner" and RUNNER_ARGS_UNSAFE_RE.search(cfg.runner_args):
        print(C.err("[ERROR] Runner args contain unsafe characters: & | < > ^ \""), file=sys.stderr)
        return None, {}, 1

    return cfg, preset_data, 0


# ---------------------------------------------------------------------------
# Subcommand: generate
# ---------------------------------------------------------------------------

def _build_generate_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "generate",
        help="Generate the .bat helper set for a project folder.",
        description=(
            "Generate run.bat, pip.bat, shell.bat, sync.bat, doctor.bat\n"
            "(and optionally test.bat / setup.bat) in the target project folder.\n\n"
            "Use --self-unpack to generate a single repo-friendly setup.bat that\n"
            "bootstraps the venv and writes all companion scripts on first run.\n\n"
            "Priority: CLI flags > --preset > folder auto-detect > defaults."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument("folder", type=Path, help="Project folder (created if missing).")
    _add_shared_config_args(p)

    p.add_argument("--overwrite",       action="store_true",
                   help="Overwrite existing .bat files.")
    p.add_argument("--no-requirements", action="store_true",
                   help="Do not create requirements.txt if missing.")
    p.add_argument("--create-venv",     action="store_true",
                   help="Create the .venv immediately after generating scripts.")
    p.add_argument("--preview",         action="store_true",
                   help="Print generated content to stdout instead of writing files.")
    p.add_argument("--list-presets",    action="store_true",
                   help="List available presets and exit.")

    return p


def _cmd_generate(args: argparse.Namespace) -> int:
    pm = PresetManager()

    if args.list_presets:
        _print_header("Available Presets")
        for name in pm.names():
            marker = C.dim("(built-in)") if pm.is_builtin(name) else C.accent("(user)")
            print(f"  {C.bold(name)}  {marker}")
        print()
        return 0

    folder = args.folder.resolve()

    cfg, preset_data, code = _resolve_generator_config(args, folder, pm)
    if cfg is None:
        return code

    cfg = replace(
        cfg,
        overwrite_existing=args.overwrite or preset_data.get("overwrite_existing", False),
        create_requirements=not args.no_requirements and preset_data.get("create_requirements", True),
        create_venv_now=args.create_venv or preset_data.get("create_venv_now", False),
    )

    if args.preview:
        previews = build_previews(cfg)
        for name, content in previews.items():
            _print_header(name)
            print(content)
        return 0

    _print_header(f"Generating for: {folder}")
    mode_str = cfg.entry_mode
    if cfg.self_unpack:
        mode_str = "self-unpack"
    uv_str   = "  [uv]" if cfg.use_uv else ""
    posix_str = "  [+posix]" if cfg.include_posix else ""
    print(f"  Mode  : {mode_str}{uv_str}{posix_str}")
    print(f"  Entry : {cfg.app_entry}")
    if cfg.entry_mode == "runner" and cfg.runner_args:
        print(f"  Args  : {cfg.runner_args}")
    print()

    try:
        written = generate_files(cfg)
    except FileExistsError as exc:
        print(C.err(f"[ERROR] {exc}"), file=sys.stderr)
        return 1
    except Exception as exc:
        print(C.err(f"[ERROR] {exc}"), file=sys.stderr)
        return 1

    for path in written:
        print(f"  {C.ok('✔')}  {path.name}")

    if cfg.self_unpack:
        print()
        print(C.dim("  Tip: add these to .gitignore (generated on first run):"))
        names = ["run.bat", "pip.bat", "shell.bat", "sync.bat", "doctor.bat"]
        if cfg.include_test_bat: names.append("test.bat")
        if cfg.include_posix:
            names += ["run.sh", "pip.sh", "shell.sh", "sync.sh", "doctor.sh"]
            if cfg.include_test_bat: names.append("test.sh")
        if cfg.include_powershell:
            names += ["run.ps1", "pip.ps1", "shell.ps1", "sync.ps1", "doctor.ps1"]
            if cfg.include_test_bat: names.append("test.ps1")
        print(f"  {C.dim(chr(10).join('    ' + n for n in names))}")

    if cfg.create_venv_now:
        venv_path = folder / cfg.venv_dir
        if venv_path.exists():
            print(C.warn(f"\n  [SKIP] .venv already exists at {venv_path}"))
        else:
            tool = "uv venv" if cfg.use_uv else "python -m venv"
            print(f"\n  Creating .venv via {tool}…")
            try:
                create_venv(cfg)
                print(C.ok(f"  ✔  .venv created at {venv_path}"))
            except Exception as exc:
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
            "(same CLI flag > preset > folder auto-detect > default priority) and\n"
            "compare it against what's already on disk. Nothing is written.\n\n"
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

    cfg, _preset_data, code = _resolve_generator_config(args, folder, pm)
    if cfg is None:
        return code

    _print_header(f"Checking: {folder}")
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
        print(C.warn("  Drift detected — run `generate --overwrite` to update."))
    else:
        print(C.ok("  Up to date — no drift detected."))
    print()

    return 1 if any_issue else 0


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
    return p


def _cmd_scan(args: argparse.Namespace) -> int:
    folder = args.folder.resolve()
    scan   = scan_project_folder(folder, args.venv_dir)
    _print_header(f"Scan: {folder}")
    for h in scan.hints:
        print(f"  {h}")
    print()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: presets
# ---------------------------------------------------------------------------

def _build_presets_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "presets",
        help="List available presets.",
    )
    return p


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
    parser = argparse.ArgumentParser(
        prog="venv-bat-gen",
        description=(
            f"Venv Batch Template Generator v{_VERSION}  (Leon Priest / 7h3v01d)\n"
            "Generate project-local venv helper scripts (.bat + optional .sh).\n\n"
            "Quick start:\n"
            "  venv-bat-gen generate ./my_project --entry main.py\n"
            "  venv-bat-gen generate ./my_project --entry main.py --self-unpack\n"
            "  venv-bat-gen check ./my_project\n"
            "  venv-bat-gen scan ./my_project"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"venv-bat-gen {_VERSION}")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    _build_generate_parser(sub)
    _build_check_parser(sub)
    _build_scan_parser(sub)
    _build_presets_parser(sub)

    args = parser.parse_args(argv)

    if args.command == "generate":
        sys.exit(_cmd_generate(args))
    elif args.command == "check":
        sys.exit(_cmd_check(args))
    elif args.command == "scan":
        sys.exit(_cmd_scan(args))
    elif args.command == "presets":
        sys.exit(_cmd_presets(args))
    else:
        parser.print_help()
        sys.exit(0)
