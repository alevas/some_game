# Noir Language Riddles: Development Roadmap

## Game Concept
A noir detective game where players solve etymological riddles across Greek, German, English, Spanish, Russian, and Arvanitika to unravel the Babel Conspiracy in 1947 Berlin.

**Unique Selling Points:**
- Noir storytelling + linguistic education
- Features Arvanitika (your heritage dialect)
- Teaches real etymology
- Short, replayable (30-60 min)

---

## Current Status

### Implemented
- Core riddle system
- 5-location narrative
- Sanity meter (3 points, game over at 0)
- Inventory system
- Multiple endings (4 variants)
- JSON database
- Noir aesthetic
- Hint system
- Mobile optimization
- Save/load system

### Files
- `play.py` - Launcher (full-screen or console)
- `tui.py` - Full-screen ASCII art version
- `main_polished.py` - Console version
- `serve.py` - Browser version (textual-serve)
- `engine.py` - Riddles, locations, story beats, game logic
- `art.py` - Scenes and portraits

---

## Development Priorities

### Phase 1: Core Completion
1. 50+ Riddles
2. Save/Load System
3. Mobile Optimization

### Phase 2: Gameplay Depth
4. Branching narrative
5. Mini-games
6. Suspect system

### Phase 3: Polish
7. Visual upgrades
8. Sound & music
9. Achievements

### Phase 4: Advanced
10. Live API integration
11. Multiplayer
12. Map system

---

## Backlog

### Gameplay
- Time pressure
- Sanity regeneration
- Item combinations
- Different riddle types
- Language selection
- Difficulty scaling

### Story
- Multiple cases
- Character trust system
- Red herrings
- Flashbacks
- Newspaper clippings

### Technical
- Progress tracking
- Riddle book
- Glossary
- Settings menu

### Visual
- ASCII art portraits
- Animated transitions
- Day/night cycle
- Weather effects

### Audio
- Location music
- Ambient sounds
- Dynamic music

### Educational
- Etymology dictionary
- Language family tree
- PIE explorer
- Learning mode

---

## Quick Reference

### Add a Riddle
Add a `Riddle(...)` to `RIDDLES` in `engine.py`, then add its id to a location's `riddle_ids`.
Multiple choice needs two `decoys`; typed riddles use `kind="type"` (plus `accepted` spellings);
matching uses `kind="match"` with `pairs`. Run `python -m unittest` to check it.

### Test
1. `python -m unittest`
2. Play `python tui.py` in a 120x50 terminal

---

## Changelog

### v0.7 - Evidence & Showdown (2026-09-27)
- Evidence can be shown to characters, traded for hints, or used against Volkov
- Final showdown: three riddles from Volkov
- New riddle types: sound shifts (typed), match the pairs, odd one out, a cipher (39 riddles)
- Etymology notebook that persists across cases
- Rain on the title screen, typewriter dialogue, Berlin map for travel
- Play in the browser with serve.py

### v0.6 - ASCII Art Overhaul (2026-09-27)
- Full-screen ASCII art version (Textual) with scenes and reacting portraits
- Location progression with leads, story beats and case notes
- Final deduction: where is Elena?
- Anti-guessing: decoy swaps, first-try streaks restore hearts
- Riddle fact-check; all endings reachable
- Launcher with console fallback; engine tests

### v0.5 - Core Complete (2026-09-24)
- 50+ riddles
- Save/load
- Mobile optimization

### v0.4 - Option A (2026-09-24)
- Sanity meter
- Inventory system
- Multiple endings
