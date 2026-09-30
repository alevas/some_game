"""
Noir Language Riddles: The Babel Conspiracy
Achievements, kept across cases in the save folder (achievements.json), like the notebook.

Each achievement is a condition over the engine and the event that just happened. The engine
tells its listeners about every move ("answer", "present", "showdown", "case_end"), and the
tracker checks the locked achievements each time. Riddles are found by category and language,
never by id, so new riddles and random riddle pools count automatically.
Nothing in here prints or reads input.
"""

import json
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

from engine import GameEngine, Riddle, DIFFICULTIES, ALL_RIDDLES, ELENA_ANSWER

FILE = "achievements.json"

# check(engine, event, info) -> True once the achievement is earned
Check = Callable[[GameEngine, str, dict], bool]


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    hint: str   # how to earn it, shown while it is locked
    text: str   # shown once it is unlocked
    check: Check


# =============================================================================
# CONDITIONS
# =============================================================================

def case_riddles(engine: GameEngine) -> List[Riddle]:
    """Every riddle placed in this case"""
    ids = dict.fromkeys(i for loc_id in engine.locations for i in engine.riddles_at(loc_id))
    return [engine.riddles[i] for i in ids if i in engine.riddles]


def case_won(engine: GameEngine, event: str, info: dict) -> bool:
    return event == "case_end" and info["showdown"].won


def found_elena(engine, event, info):
    return event == "case_end" and info["showdown"].elena_guess == ELENA_ANSWER


def clean_sweep(engine, event, info):
    return (event == "case_end" and engine.all_riddles_solved()
            and not engine.state.fumbled_riddles and info["showdown"].mistakes == 0)


def bare_hands(engine, event, info):
    return case_won(engine, event, info) and info["showdown"].dodges == 0


def close_shave(engine, event, info):
    return case_won(engine, event, info) and engine.state.sanity == 1


def every_sound_shift(engine, event, info):
    shifts = [r.id for r in case_riddles(engine) if "sound shift" in r.category.lower()]
    return event == "answer" and bool(shifts) and all(i in engine.state.solved_riddles for i in shifts)


def every_reveal(engine, event, info):
    reveals = {f"{loc.id}:{item}" for loc in engine.locations.values() for item in loc.present}
    return event == "present" and bool(reveals) and reveals <= set(engine.state.presented)


def hot_streak(engine, event, info):
    return engine.state.streak >= 10


def polyglot(engine, event, info):
    """Counted from the notebook, so it adds up across cases"""
    languages = {r.language for r in engine.notebook_entries() if r.category.lower() != "cipher"}
    return len(languages) >= 10


def bookworm(engine, event, info):
    return len(engine.notebook) * 2 >= len(ALL_RIDDLES)


def victory(level: str) -> Check:
    """Beat Volkov on this difficulty or a harder one"""
    rank = list(DIFFICULTIES).index(level)

    def check(engine, event, info):
        return case_won(engine, event, info) and list(DIFFICULTIES.values()).index(engine.difficulty()) >= rank
    return check


# =============================================================================
# ACHIEVEMENTS
# =============================================================================

ACHIEVEMENTS: List[Achievement] = [
    Achievement("sherlock", "Sherlock", "Work out where Elena is being held.",
                "You found Elena Weber.", found_elena),
    Achievement("clean_sweep", "Clean Sweep", "Solve every riddle in a case and face Volkov without a wrong answer.",
                "A whole case without a single wrong answer.", clean_sweep),
    Achievement("bare_hands", "Bare Hands", "Beat Volkov without throwing any evidence at him.",
                "You beat Volkov with words alone.", bare_hands),
    Achievement("close_shave", "Close Shave", "Beat Volkov with one heart left.",
                "One heart left, and it was enough.", close_shave),
    Achievement("grimm_reaper", "Grimm Reaper", "Solve every sound-shift riddle in a case.",
                "Grimm's law holds no secrets from you.", every_sound_shift),
    Achievement("show_and_tell", "Show and Tell", "In one case, show everyone the evidence that makes them talk.",
                "Every piece of evidence found its witness.", every_reveal),
    Achievement("hot_streak", "Hot Streak", "Answer 10 riddles in a row on the first try.",
                "Ten clean answers in a row.", hot_streak),
    Achievement("polyglot", "Polyglot", "Solve riddles in 10 languages, over all your cases.",
                "Riddles solved in 10 languages.", polyglot),
    Achievement("bookworm", "Bookworm", "Fill half of the etymology notebook.",
                "Half the notebook filled in.", bookworm),
    Achievement("rookie_win", "First Collar", "Beat Volkov on any difficulty.",
                "Volkov beaten. Every detective starts somewhere.", victory("rookie")),
    Achievement("detective_win", "Private Eye", "Beat Volkov on Detective or Noir.",
                "Volkov beaten without a rookie's safety net.", victory("detective")),
    Achievement("noir_win", "Film Noir", "Beat Volkov on Noir.",
                "Two hearts, no hints, and still you won.", victory("noir")),
]
BY_ID: Dict[str, Achievement] = {a.id: a for a in ACHIEVEMENTS}


# =============================================================================
# TRACKER
# =============================================================================

class Achievements:
    """What the player has unlocked, updated as the engine reports each move"""

    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.unlocked: List[str] = self._load()
        self.pending: List[Achievement] = []  # unlocked but not shown yet
        self.on_unlock: Callable[[Achievement], None] = self.pending.append  # a UI may show them at once instead
        engine.listeners.append(self.check)

    def _load(self) -> List[str]:
        try:
            with open(self.engine.SAVE_DIR / FILE) as f:
                return [i for i in json.load(f) if i in BY_ID]
        except (OSError, ValueError, TypeError):
            return []

    def check(self, engine: GameEngine, event: str, info: dict):
        for achievement in ACHIEVEMENTS:
            if achievement.id not in self.unlocked and achievement.check(engine, event, info):
                self.unlocked.append(achievement.id)
                with open(self.engine.SAVE_DIR / FILE, "w") as f:
                    json.dump(self.unlocked, f)
                self.on_unlock(achievement)

    def take_pending(self) -> List[Achievement]:
        new = list(self.pending)
        self.pending.clear()
        return new

    def entries(self) -> List[Tuple[Achievement, bool]]:
        """Every achievement, and whether it is unlocked"""
        return [(a, a.id in self.unlocked) for a in ACHIEVEMENTS]
