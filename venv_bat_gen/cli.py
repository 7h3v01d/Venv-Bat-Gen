"""
venv_bat_gen.cli
================
Command-line interface.  Imports directly from core — no Qt, no MagicMock.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    GeneratorConfig,
    FolderScan,
    PresetManager,
    MODULE_RE,
    RUNNER_ARGS_UNSAFE_RE,
    build_previews,
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
# Subcommand: generate
# ---------------------------------------------------------------------------

def _build_generate_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "generate",
        help="Generate the .bat helper set for a project folder.",
        description=(
            "Generate run.bat, pip.bat, shell.bat, sync.bat, doctor.bat\n"
            "(and optionally test.bat) in the target project folder.\n\n"
            "Priority: CLI flags > --preset > folder auto-detect > defaults."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument("folder", type=Path, help="Project folder (created if missing).")
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

    p.add_argument("--overwrite",       action="store_true",
                   help="Overwrite existing .bat files.")
    p.add_argument("--no-requirements", action="store_true",
                   help="Do not create requirements.txt if missing.")
    p.add_argument("--webengine",       action="store_true",
                   help="Include PyQt6 WebEngine check in doctor.bat.")
    p.add_argument("--no-pause",        action="store_true",
                   help="Do not pause run.bat on exit.")
    p.add_argument("--create-venv",     action="store_true",
                   help="Create the .venv now.")
    p.add_argument("--test-bat",        action="store_true",
                   help="Include test.bat (pytest runner).")
    p.add_argument("--uv",             action="store_true",
                   help="Use uv instead of pip in generated scripts.")
    p.add_argument("--posix",          action="store_true",
                   help="Also generate POSIX .sh equivalents of all scripts.")
    p.add_argument("--setup",          action="store_true",
                   help="Include setup.bat / setup.sh bootstrap script.")

    p.add_argument("--no-detect", action="store_true",
                   help="Skip folder auto-detection.")
    p.add_argument("--dry-run",   action="store_true",
                   help="Print what would be written without writing anything.")

    return p


def _resolve(cli_val, preset_data: dict, preset_key: str, scan_val, default):
    """Priority: CLI arg > preset > scan > default.

    cli_val should be None when the user did not supply the flag (argparse
    default=None), not False — booleans should use _resolve_flag instead.
    """
    if cli_val is not None:
        return cli_val
    if preset_key in preset_data:
        return preset_data[preset_key]
    if scan_val is not None:
        return scan_val
    return default


def _resolve_flag(cli_flag: bool, preset_data: dict, preset_key: str, default: bool) -> bool:
    """For boolean flags: CLI True beats preset beats default."""
    if cli_flag:
        return True
    if preset_key in preset_data:
        return bool(preset_data[preset_key])
    return default


def _cmd_generate(args: argparse.Namespace) -> int:
    folder: Path = args.folder.resolve()

    # --- Preset ---
    preset_data: dict = {}
    if args.preset:
        pm = PresetManager()
        preset_data = pm.get(args.preset) or {}
        if not preset_data:
            print(C.err(f"Preset not found: {args.preset!r}"))
            print(C.dim("  Run `venv-bat-gen presets` to list available presets."))
            return 1
        print(C.dim(f"  Loaded preset: {args.preset}"))

    # --- Auto-detect ---
    scan: FolderScan | None = None
    if not args.no_detect and folder.exists():
        venv_dir_hint = args.venv_dir or preset_data.get("venv_dir", ".venv")
        scan = scan_project_folder(folder, venv_dir_hint)
        if scan.hints:
            _print_header("Folder scan")
            for h in scan.hints:
                print(f"  {h}")

    # --- Resolve config ---
    entry_mode = _resolve(args.entry_mode,  preset_data, "entry_mode",
                          scan.suggested_entry_mode if scan else None, "file")
    app_entry  = _resolve(args.entry or None, preset_data, "app_entry",
                          scan.suggested_app_entry if scan else None, "main.py")
    runner_args = _resolve(args.runner_args or None, preset_data, "runner_args",
                           scan.suggested_runner_args if scan else None, "")
    project_name = args.name or folder.name
    venv_dir     = args.venv_dir or preset_data.get("venv_dir", ".venv")

    overwrite        = _resolve_flag(args.overwrite,     preset_data, "overwrite_existing",     False)
    create_req       = not args.no_requirements and _resolve_flag(False, preset_data, "create_requirements", True)
    webengine        = _resolve_flag(args.webengine,     preset_data, "include_webengine_check", False)
    pause_on_exit    = not args.no_pause and _resolve_flag(False, preset_data, "pause_on_exit", True)
    create_venv_now  = _resolve_flag(args.create_venv,  preset_data, "create_venv_now",         False)
    include_test_bat = _resolve_flag(args.test_bat,      preset_data, "include_test_bat",        False)
    use_uv           = _resolve_flag(
        args.uv,
        preset_data, "use_uv",
        scan.suggested_use_uv if scan else False,
    )
    include_posix    = _resolve_flag(
        args.posix,
        preset_data, "include_posix",
        scan.suggested_use_posix if scan else False,
    )
    include_setup    = _resolve_flag(
        args.setup,
        preset_data, "include_setup",
        False,
    )

    # --- Validate ---
    if entry_mode in ("module", "runner"):
        if not MODULE_RE.match(app_entry):
            print(C.err(f"Invalid module name for {entry_mode} mode: {app_entry!r}"))
            return 1
    if entry_mode == "runner" and RUNNER_ARGS_UNSAFE_RE.search(runner_args):
        print(C.err('Runner args contain unsafe batch characters: & | < > ^ "'))
        return 1

    cfg = GeneratorConfig(
        project_dir=folder,
        project_name=project_name,
        venv_dir=venv_dir,
        entry_mode=entry_mode,
        app_entry=app_entry,
        runner_args=runner_args,
        overwrite_existing=overwrite,
        create_requirements=create_req,
        include_webengine_check=webengine,
        pause_on_exit=pause_on_exit,
        create_venv_now=create_venv_now,
        include_test_bat=include_test_bat,
        use_uv=use_uv,
        include_posix=include_posix,
        include_setup=include_setup,
    )

    # --- Summary ---
    _print_header("Generate")
    print(f"  Folder  : {C.bold(str(folder))}")
    print(f"  Name    : {project_name}")
    print(f"  Venv    : {venv_dir}/")
    print(f"  Mode    : {entry_mode}  →  {app_entry}"
          + (f"  {runner_args}" if entry_mode == "runner" and runner_args else ""))
    flags = []
    if use_uv:           flags.append("uv")
    if include_posix:    flags.append("posix")
    if include_setup:    flags.append("setup")
    if overwrite:        flags.append("overwrite")
    if create_req:       flags.append("requirements.txt")
    if webengine:        flags.append("webengine-check")
    if not pause_on_exit: flags.append("no-pause")
    if create_venv_now:  flags.append("create-venv")
    if include_test_bat: flags.append("test.bat")
    if flags:
        print(f"  Options : {', '.join(flags)}")
    print()

    if args.dry_run:
        files = list(build_previews(cfg).keys())
        if create_req:
            files.append("requirements.txt")
        print(C.warn("  DRY RUN — no files written."))
        for f in files:
            print(C.dim(f"    {folder / f}"))
        print()
        return 0

    # --- Write ---
    try:
        written = generate_files(cfg)
    except FileExistsError as exc:
        print(C.err(f"  File exists: {exc}"))
        print(C.dim("  Use --overwrite to replace existing files."))
        return 1
    except Exception as exc:
        print(C.err(f"  Error: {exc}"))
        return 1

    for path in written:
        print(f"  {C.ok('✔')}  {path.name}")

    if create_venv_now:
        venv_path = folder / venv_dir
        if venv_path.exists():
            print(C.warn(f"\n  ⚠  .venv already exists at {venv_path} — skipped."))
        else:
            tool = "uv" if use_uv else "python -m venv"
            print(C.dim(f"\n  Creating .venv via {tool} …"))
            try:
                create_venv(cfg)
                print(C.ok("  ✔  .venv created."))
            except Exception as exc:
                print(C.err(f"  ✖  venv creation failed: {exc}"))
                return 1

    print()
    print(C.ok(f"  Done — {len(written)} file(s) written to {folder}"))
    print()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: scan
# ---------------------------------------------------------------------------

def _build_scan_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "scan",
        help="Inspect a folder and report what was found.",
    )
    p.add_argument("folder", type=Path)
    p.add_argument("--venv-dir", metavar="DIR", default=".venv")
    return p


def _cmd_scan(args: argparse.Namespace) -> int:
    folder = args.folder.resolve()
    if not folder.exists():
        print(C.err(f"Folder does not exist: {folder}"))
        return 1

    scan = scan_project_folder(folder, args.venv_dir)
    _print_header(f"Scan: {folder.name}")
    for h in scan.hints:
        print(f"  {h}")

    if scan.suggested_entry_mode:
        print()
        print(C.accent("  Suggested generate command:"))
        mode_flag = {"runner": "--runner", "module": "--module", "file": "--file"}.get(
            scan.suggested_entry_mode, "--file"
        )
        cmd = f"  venv-bat-gen generate {folder} {mode_flag} --entry {scan.suggested_app_entry}"
        if scan.suggested_runner_args:
            cmd += f' --runner-args "{scan.suggested_runner_args}"'
        if scan.suggested_use_uv:
            cmd += " --uv"
        if scan.suggested_use_posix:
            cmd += " --posix"
        print(C.bold(cmd))

    print()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: presets
# ---------------------------------------------------------------------------

def _build_presets_parser(sub) -> argparse.ArgumentParser:
    p = sub.add_parser("presets", help="List all available presets.")
    p.add_argument("--detail", action="store_true", help="Show full preset contents.")
    return p


def _cmd_presets(args: argparse.Namespace) -> int:
    pm    = PresetManager()
    names = pm.names()

    if not names:
        print(C.dim("  No presets found."))
        return 0

    _print_header("Presets")
    for name in names:
        tag    = C.dim("(built-in)") if pm.is_builtin(name) else C.accent("(user)")
        data   = pm.get(name) or {}
        mode   = data.get("entry_mode", "?")
        entry  = data.get("app_entry", "?")
        rargs  = data.get("runner_args", "")
        uv_tag = C.accent("  [uv]") if data.get("use_uv") else ""
        summary = f"{mode}: {entry}" + (f"  {rargs}" if rargs else "")
        print(f"  {C.bold(name)}  {tag}{uv_tag}")
        print(f"    {C.dim(summary)}")
        if args.detail:
            for k, v in data.items():
                if k not in ("entry_mode", "app_entry", "runner_args"):
                    print(f"    {C.dim(k + ':')} {v}")
        print()

    print(C.dim('  Use: venv-bat-gen generate <folder> --preset "<name>" [...overrides]'))
    print()
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="venv-bat-gen",
        description=(
            "Venv Batch Template Generator  —  CLI\n"
            "Generates project-local .bat helper scripts that call\n"
            r".venv\Scripts\python.exe directly — no manual activation needed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="venv-bat-gen 3.3.0")

    sub = parser.add_subparsers(dest="subcommand", metavar="<subcommand>")
    sub.required = True

    _build_generate_parser(sub)
    _build_scan_parser(sub)
    _build_presets_parser(sub)

    args = parser.parse_args()
    dispatch = {
        "generate": _cmd_generate,
        "scan":     _cmd_scan,
        "presets":  _cmd_presets,
    }
    sys.exit(dispatch[args.subcommand](args))
