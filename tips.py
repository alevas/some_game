"""
Noir Language Riddles: The Babel Conspiracy
First-time tips: short explanations shown once each, at the moment they matter.

The texts for both UIs live here ("tui" for tui.py, "console" for main_polished.py).
Which tips have been seen, and whether tips are on at all, is kept in tips.json in
the save folder, separately from the saves themselves. Nothing in here prints.
"""

import json
from pathlib import Path
from typing import List, Optional


TIPS = {
    "case": {
        "title": "Your first case",
        "tui": "Answer with the number keys 1-4. The case file on the right keeps count: ♥ is your "
               "sanity (a wrong answer costs a heart; lose them all and the case is over), and every "
               "third clean answer in a row wins one back. Below that: evidence, leads and notes. "
               "The keys along the bottom are your commands; i questions whoever is here.",
        "console": "Type the number of your answer and press Enter. The line above the scene keeps "
                   "count: ♥ is your sanity (a wrong answer costs a heart; lose them all and the case "
                   "is over), and every third clean answer in a row (the ◆ streak) wins one back. The "
                   "letters under each riddle are your commands; i questions whoever is here.",
    },
    "typing": {
        "title": "Type the answer",
        "tui": "This riddle is answered in the text box: type and press Enter. Capitals and "
               "punctuation don't matter. Esc steps out of the box so the one-key commands "
               "(h, e, n...) work again; Enter steps back in.",
        "console": "This riddle wants a word, not a number: type it and press Enter (for matching, "
                   "type the letters in order, like BCA). Capitals and punctuation don't matter. "
                   "Single letters such as h or n are still commands.",
    },
    "evidence": {
        "title": "Evidence",
        "tui": "You kept a piece of evidence (you only keep it when you answer first try). Press e "
               "to show it to whoever is here; some of it makes people talk. Press h to trade it for "
               "a hint. Or save it for Volkov: in the showdown, throwing evidence at him dodges a question.",
        "console": "You kept a piece of evidence (you only keep it when you answer first try). Type e "
                   "to show it to whoever is here; some of it makes people talk. Type h to trade it "
                   "for a hint. Or save it for Volkov: in the showdown, throwing evidence at him "
                   "dodges a question.",
    },
    "lead": {
        "title": "A new lead",
        "tui": "A new place is open. Press g to go now, or Enter to keep digging here. t travels "
               "between open places at any time, so you can come back for what you left behind: "
               "unsolved riddles count against you at the end.",
        "console": "A new place is open. Type 1 to go now, or press Enter to keep digging here. t "
                   "travels between open places at any time, so you can come back for what you left "
                   "behind: unsolved riddles count against you at the end.",
    },
    "archive": {
        "title": "Volkov's archive",
        "tui": "Press v to confront Volkov whenever you're ready; it ends the case. First you must "
               "say where Elena is being held, and the answer is scattered through your case notes "
               "(n). Then he asks three riddles of his own. The more you've solved, the better the ending.",
        "console": "Type v to confront Volkov whenever you're ready; it ends the case. First you must "
                   "say where Elena is being held, and the answer is scattered through your case "
                   "notes (n). Then he asks three riddles of his own. The more you've solved, the "
                   "better the ending.",
    },
    "interrogation": {
        "title": "Questioning",
        "tui": "Pick a question. Some answers are lies: press one (p) with the evidence that "
               "contradicts it. The right piece breaks the lie and wins their trust, and people who "
               "trust you owe you a free hint (h). The wrong piece costs trust and a heart (never "
               "your last), and a distrustful witness goes quiet until you solve another riddle here.",
        "console": "Type a question's number. Some answers are lies: press one (p) with the evidence "
                   "that contradicts it. The right piece breaks the lie and wins their trust, and "
                   "people who trust you owe you a free hint (h). The wrong piece costs trust and a "
                   "heart (never your last), and a distrustful witness goes quiet until you solve "
                   "another riddle here.",
    },
}


class Tips:
    """Which tips have been shown, and whether tips are on. Kept in tips.json."""

    def __init__(self, save_dir: Path):
        self.path = Path(save_dir) / "tips.json"
        self.enabled = True
        self.seen: List[str] = []
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.enabled = bool(data.get("enabled", True))
            self.seen = [key for key in data.get("seen", []) if key in TIPS]
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def take(self, *keys: str) -> Optional[str]:
        """The first of these tips that hasn't been shown yet, now marked as shown; None if there is none"""
        if not self.enabled:
            return None
        for key in keys:
            if key in TIPS and key not in self.seen:
                self.seen.append(key)
                self._save()
                return key
        return None

    def set_enabled(self, on: bool):
        self.enabled = on
        self._save()

    def reset(self):
        """Show every tip again"""
        self.seen = []
        self._save()

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump({"enabled": self.enabled, "seen": self.seen}, f, indent=2)
        except OSError:
            pass  # tips are a nicety; a read-only save folder shouldn't stop the game
