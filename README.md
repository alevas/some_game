# Noir Language Riddles: The Babel Conspiracy

An ASCII art detective game about etymology and linguistic mysteries set in post-war Berlin, 1947.

## Quick Start

```bash
pip install -r requirements.txt
python play.py
```

`play.py` starts the full-screen ASCII art version when your terminal is at least 100x30,
and the plain console version otherwise. You can also start either one directly:

- `python tui.py` - full-screen ASCII art version (needs Textual)
- `python main_polished.py` - console version (no dependencies)
- `python play.py --console` - force the console version

On Linux/Mac you can also run `./run_game.sh`; on Windows, double-click `run_game.bat`.

### Play in a Browser

```bash
python serve.py                  # then open http://localhost:8000
python serve.py --host 0.0.0.0   # let others on your network play
```

Each browser tab gets its own game. To share it beyond your network, run it on a server
(or behind a tunnel) and pass the address players will use with `--public-url`.

### Standalone Executable (No Python Required)

```bash
pip install pyinstaller
pyinstaller --onefile --name NoirRiddles --collect-submodules textual \
    --collect-submodules rich --collect-data textual play.py
```

The executable lands in `dist/` (`dist/NoirRiddles`, or `dist/NoirRiddles.exe` when built on Windows).
PyInstaller only builds for the system it runs on, so build on Windows for Windows players.

## How the Case Works

The case runs Weber's Office → Staatsbibliothek → Café Mozart → St. Nicholas Church → Secret Archive.
Each location has its own riddles. Solve enough of them and a **lead** riddle appears; solving it
unlocks the next location. You can follow the lead right away or keep digging, and travel back later.

- **Riddle types.** Multiple choice, odd one out, *sound shifts* (apply Grimm's law and type the
  English word), *match the pairs*, and one cipher.
- **No brute-forcing.** A wrong answer costs a heart, and the option you picked is replaced
  by a new decoy before the choices reshuffle.
- **Streaks.** Consecutive first-try answers earn bonus points, and every third one restores a heart.
- **Evidence** is only kept if you solve its riddle on the first try. Use it three ways:
  show it to a character to learn something new, trade it for a hint, or save it for Volkov.
- **People talk.** Characters react to how you're doing, and reveal more as you solve riddles
  at their location. Everything they tell you goes into your case notes.
- **The finale.** In the Archive you can confront Volkov whenever you like. First you must say
  where Elena is being held (the answer is hidden in your case notes). Then Volkov asks three
  riddles of his own: a wrong answer costs a heart, and throwing a piece of evidence at him
  dodges a question.
- **Etymology notebook.** Every explanation you unlock is kept, across all your cases.

The ending depends on whether you beat Volkov, whether you found Elena, and how many riddles you solved.

## Controls (Full-Screen Version)

| Key | Action |
|-----|--------|
| `1`-`4` | Answer (multiple choice) |
| type + `Enter` | Answer (sound shifts, matching, cipher); `Esc` leaves the text box |
| `h` | Hint (free after a wrong answer, otherwise costs a piece of evidence) |
| `e` | Evidence: show it to someone, or throw it at Volkov |
| `Enter` | Continue |
| `g` | Follow a new lead |
| `n` | Case notes |
| `b` | Etymology notebook |
| `t` | Travel |
| `v` | Confront Volkov (in the Archive) |
| `m` / `Esc` | Menu (save, load, title screen) |

The console version uses the same letters, typed at the prompt.

## Files

- `play.py` - Launcher that picks the right version for your terminal
- `tui.py` - Full-screen ASCII art version
- `main_polished.py` - Console version
- `serve.py` - Serves the full-screen version as a web page
- `engine.py` - Game data (riddles, locations, story) and logic shared by both versions
- `art.py` - ASCII art: scenes, character portraits with expressions, the Berlin map
- `test_engine.py` - Engine tests (`python -m unittest`)
- Saves (and the notebook) are stored in `~/.babel_conspiracy_saves/`; the game autosaves after every move

## System Requirements

- **Python 3.9+** (Textual needs 3.9; the console version runs on 3.8)
- Works on **Windows, Mac, Linux**
- A terminal with ANSI color and UTF-8 support

## Troubleshooting

- If characters look wrong, try running with the `PYTHONUTF8=1` environment variable
- On Windows, use Windows Terminal or PowerShell (not old cmd.exe)
- Make sure you have read/write permissions in your home directory for saves

## License

Free to share and play. Created by Alex.
