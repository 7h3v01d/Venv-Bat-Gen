"""Enable `python -m venv_bat_gen` entry point.

With no arguments: launches the GUI.
With arguments: runs the CLI.
"""
import sys

if len(sys.argv) > 1:
    from venv_bat_gen.cli import main
else:
    from venv_bat_gen.gui_launcher import main

main()
