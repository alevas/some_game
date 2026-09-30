"""
Noir Language Riddles: The Babel Conspiracy
Player settings, kept in the save folder (settings.json) and shared by both versions.
Nothing in here prints or reads input.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Tuple

FILE = "settings.json"


def motion_reduced_by_default() -> bool:
    """Start with reduce motion on for slow hosts: on Render (RENDER is set) the free instance
    has a tenth of a CPU and the rain alone would use it all. NOIR_REDUCE_MOTION=1 does the same anywhere."""
    wanted = os.environ.get("NOIR_REDUCE_MOTION", "").strip().lower()
    return bool(os.environ.get("RENDER")) or wanted not in ("", "0", "false", "no", "off")


@dataclass
class Settings:
    reduce_motion: bool = field(default_factory=motion_reduced_by_default)  # no rain, no typewriter

    @classmethod
    def load(cls, save_dir: Path) -> "Settings":
        """The saved settings; anything missing or unreadable keeps its default"""
        settings = cls()
        try:
            with open(Path(save_dir) / FILE) as f:
                data = json.load(f)
            for key, value in data.items():
                if key in cls.__dataclass_fields__ and isinstance(value, bool):
                    setattr(settings, key, value)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return settings

    def save(self, save_dir: Path):
        with open(Path(save_dir) / FILE, "w") as f:
            json.dump(asdict(self), f, indent=2)


# What the settings screens offer: (field, label, what it does)
TOGGLES: List[Tuple[str, str, str]] = [
    ("reduce_motion", "Reduce motion", "No falling rain, and text appears at once instead of being typed out."),
    # Kept by tips.py (tips.json), not a Settings field; the settings screens route it there
    ("tips", "First-time tips", "Short tips that explain each part of the game the first time you meet it."),
]
