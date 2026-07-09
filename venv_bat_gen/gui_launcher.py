"""
venv_bat_gen.gui_launcher
==========================
Thin wrapper around venv_bat_gen.gui:main().

PyQt6 lives behind the optional `gui` extra (`pip install venv-bat-gen[gui]`),
so importing venv_bat_gen.gui directly raises a bare ModuleNotFoundError if
it isn't installed. This module defers that import to inside main() so we
can catch it and print an actionable message instead.

Deliberately has NO import of venv_bat_gen.gui (and therefore no PyQt6
import) at module scope — that's the entire point of this file existing.
"""

from __future__ import annotations

import sys

_INSTALL_HINT = (
    "[ERROR] The GUI requires PyQt6, which is not installed.\n"
    "        Install it with:\n"
    "            pip install venv-bat-gen[gui]\n"
    "        Or use the CLI instead, which has no GUI dependencies:\n"
    "            venv-bat-gen generate . --entry main.py\n"
)


def main() -> None:
    try:
        from venv_bat_gen.gui import main as _gui_main
    except ImportError as exc:
        # venv-bat-gen-gui is registered as a gui-script (no console window
        # on Windows), so this text is only guaranteed visible when the
        # launcher is run from a terminal (e.g. `python -m venv_bat_gen`).
        # A double-clicked shortcut with PyQt6 missing will exit silently —
        # documented in the README rather than solved with a native
        # message-box fallback, which is out of scope for this wrapper.
        print(f"{_INSTALL_HINT}        (underlying error: {exc})", file=sys.stderr)
        sys.exit(1)

    _gui_main()


if __name__ == "__main__":
    main()
