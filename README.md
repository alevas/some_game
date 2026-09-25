# Noir Language Riddles: The Babel Conspiracy

A text-based detective game about etymology and linguistic mysteries set in post-war Berlin, 1947.

## Quick Start

### Option A: Run Directly (Requires Python)

1. **Install Python 3.6 or higher** from [python.org](https://www.python.org/downloads/)
2. **Run the game:**
   ```bash
   python main_polished.py
   ```
   Or on Linux/Mac:
   ```bash
   chmod +x main_polished.py
   ./main_polished.py
   ```

### Option B: Standalone Executable (No Python Required)

Use PyInstaller to create an executable:

```bash
# Install PyInstaller
pip install pyinstaller

# Create executable (replace 'main_polished' with your preferred name)
pyinstaller --onefile --name "NoirRiddles" main_polished.py

# The executable will be in the 'dist/' folder
# On Windows: dist/NoirRiddles.exe
# On Mac/Linux: dist/NoirRiddles
```

## Game Controls

- **Answer riddles** by entering the number of your choice
- **Open menu** by typing `m` at any prompt
- **Save game** to one of 3 slots
- **Load game** from any saved slot

## Files

- `main_polished.py` - Main game file
- `riddles_db.json` - Riddle database (30+ linguistic puzzles)
- Saves are stored in `~/.babel_conspiracy_saves/` on your home directory

## Features

- 30+ linguistic riddles across 7 languages
- 5 unique locations in 1947 Berlin
- Sanity meter - lose sanity for wrong answers!
- Inventory system - collect items as you solve riddles
- Multiple endings based on your progress
- Save/load system
- Noir atmosphere with ASCII art

## System Requirements

- **Python 3.6+** (for dataclasses)
- Works on **Windows, Mac, Linux**
- Terminal/Command Prompt with ANSI color support

## Troubleshooting

- If colors don't display properly, try running with `PYTHONUTF8=1` environment variable
- On Windows, use Command Prompt or PowerShell (not old cmd.exe)
- Make sure you have read/write permissions in your home directory for saves

## License

Free to share and play. Created by Alex.
