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
- `noir_game_optionA.html` - Main game
- `riddles_db.json` - 50+ riddles
- `app_brainstorm.md` - Original concept

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
Edit riddles_db.json with this template.

### Test
1. Open noir_game_optionA.html
2. Mobile: Chrome DevTools -> Toggle Device Toolbar
3. Console: F12 for errors

---

## Changelog

### v0.5 - Core Complete (2026-09-24)
- 50+ riddles
- Save/load
- Mobile optimization

### v0.4 - Option A (2026-09-24)
- Sanity meter
- Inventory system
- Multiple endings
