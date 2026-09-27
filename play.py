#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
Launcher: runs the full-screen ASCII art version when the terminal can fit it,
otherwise falls back to the plain console version.

Run with: python play.py            (pick automatically)
          python play.py --console  (always use the console version)
"""

import shutil
import sys

# The full-screen layout needs roughly this much room
MIN_COLUMNS = 100
MIN_LINES = 30


def fullscreen_problem() -> str:
    """Why the full-screen version can't run here, or '' if it can"""
    if "--console" in sys.argv:
        return "console mode requested"
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return "not running in an interactive terminal"
    try:
        import textual  # noqa: F401
    except ImportError:
        return "Textual is not installed (pip install -r requirements.txt)"
    size = shutil.get_terminal_size()
    if size.columns < MIN_COLUMNS or size.lines < MIN_LINES:
        return (f"terminal is {size.columns}x{size.lines}, the ASCII art version needs "
                f"{MIN_COLUMNS}x{MIN_LINES}; enlarge the window and restart for the full experience")
    return ""


def main():
    problem = fullscreen_problem()
    if problem:
        if problem != "console mode requested":
            print(f"Starting the console version: {problem}.")
            try:
                input("Press Enter to continue...")
            except EOFError:
                pass
        import main_polished
        try:
            main_polished.main()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye, detective.")
    else:
        from tui import NoirApp
        NoirApp().run()


if __name__ == "__main__":
    main()
