# App Brainstorming: Side Project Ideas for Alex V.
**Date:** 2026-09-15
**Goal:** Monetize technical and creative skills with a small, feasible app.
**Constraints:** No prior mobile/game dev experience; limited time (PhD student).

---

## 🎯 Top Ideas
   Idea | Description | Pros | Cons | Feasibility | Monetization |
 |------|------------|------|------|-------------|--------------|
 | **Guitar Fretboard Game** | Pacman-like game on a guitar fretboard; traverse scales/arpeggios to make music. | Unique, combines music + gaming, niche but passionate audience. | Requires game dev learning, asset creation. | Medium-High | One-time purchase ($2.99–$4.99) |
 | **On-Device LLM Fine-Tuning** | Fine-tune a small LLM on-device for specific tasks (e.g., writing lyrics). | Leverages ML expertise, privacy-focused, high potential. | Technically complex, mobile optimization needed. | Low (for now) | Subscription or one-time fee |
 | **Color Theory Riddles** | Puzzle game based on color theory (e.g., mixing, cultural meanings). | Creative, visual, broad appeal. | Market saturation, needs unique twist. | High | Ads or one-time fee |
 | **Noir Language Riddles** | Text-based riddle game exploring language interconnections. | Niche but viral potential, aligns with linguistics interest. | Complex riddle design, smaller audience. | Medium | One-time purchase |

---

## 🚀 Recommended Starting Point: **Guitar Fretboard Game**
### Why?
- Combines **music passion** + **game dev** (new skill to learn).
- **Clear monetization** (musicians pay for tools).
- **Prototyping is feasible** in Python (Pygame) before mobile.

### Action Plan
#### Phase 1: Prototype (2–4 weeks)
- **Tools:** Pygame (Python), `mingus` (MIDI library for note generation).
- **Goal:** Validate core gameplay (navigate fretboard, collect notes, play sounds).
- **Tasks:**
  - [ ] Install Pygame: `pip install pygame mingus`
  - [ ] Create a **fretboard grid** (e.g., 6 strings × 12 frets).
  - [ ] Implement **player movement** (arrow keys or touch).
  - [ ] Generate **note sounds** when player "hits" a note (use `mingus` or pre-recorded samples).
  - [ ] Design **1 level** (e.g., C major scale).
  - [ ] Add **tempo control** (BPM slider).

#### Phase 2: Test & Iterate (1–2 weeks)
- **Share prototype** with musician friends for feedback.
- **Refine mechanics** (e.g., scoring, lives, power-ups).
- **Add visuals** (e.g., Pacman-style sprites for notes).

#### Phase 3: Mobile Port (4–6 weeks)
- **Tools:** Godot (GDScript) or Unity (C#).
- **Goal:** Port prototype to Android/iOS.
- **Tasks:**
  - [ ] Recreate fretboard in Godot/Unity.
  - [ ] Implement touch controls.
  - [ ] Optimize for mobile performance.
  - [ ] Add **monetization** (one-time purchase via Google Play/App Store).

#### Phase 4: Launch & Market
- **Platforms:** Google Play, App Store, itch.io (for desktop).
- **Marketing:**
  - Post on **r/guitar, r/musictheory, r/indiegames**.
  - Reach out to **music YouTubers** for demos.
  - Offer **free demo** with paid full version.

---
### Starter Code: Pygame Fretboard Prototype
```python
# guitar_game.py - Basic Pygame fretboard prototype
import pygame
import sys

# Initialize Pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Guitar Fretboard Game")
clock = pygame.time.Clock()

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)

# Fretboard dimensions
STRING_SPACING = 10
FRET_SPACING = 50
NUM_FRETS = 12
NUM_STRINGS = 6

# Player
player_pos = [3, 5]  # [string, fret]
player_size = 20

def draw_fretboard():
    for string in range(NUM_STRINGS):
        for fret in range(NUM_FRETS):
            pygame.draw.rect(
                screen,
                WHITE,
                (100 + fret * FRET_SPACING, 100 + string * STRING_SPACING * 10, FRET_SPACING, STRING_SPACING),
                1
            )
    # Draw player
    pygame.draw.circle(
        screen,
        GOLD,
        (100 + player_pos[1] * FRET_SPACING + FRET_SPACING // 2, 100 + player_pos[0] * STRING_SPACING * 10 + STRING_SPACING // 2),
        player_size
    )

def main():
    global player_pos
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP and player_pos[0] > 0:
                    player_pos[0] -= 1
                elif event.key == pygame.K_DOWN and player_pos[0] < NUM_STRINGS - 1:
                    player_pos[0] += 1
                elif event.key == pygame.K_LEFT and player_pos[1] > 0:
                    player_pos[1] -= 1
                elif event.key == pygame.K_RIGHT and player_pos[1] < NUM_FRETS - 1:
                    player_pos[1] += 1

        screen.fill(BLACK)
        draw_fretboard()
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
