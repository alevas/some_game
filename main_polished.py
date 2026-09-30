#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
A polished text-based detective game about etymology

Run with: python main_polished.py
(For the full-screen ASCII art version, run: python tui.py)
"""

import os
import random
import sys
import textwrap
import time
from typing import List, Optional, Tuple

import art
import savecode
from achievements import Achievements
from engine import (GameEngine, Riddle, Showdown, LOCATIONS, STORY_ORDER, ALL_RIDDLES,
                    ELENA_QUESTION, ELENA_OPTIONS, FINAL_LOCATION, SHOWDOWN_INTRO,
                    DIFFICULTIES, DEFAULT_DIFFICULTY, SaveCodeError)
from engine import Question
from settings import Settings, TOGGLES
from tips import TIPS, Tips


# =============================================================================
# ANSI COLORS FOR TERMINAL
# =============================================================================

class Color:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    ITALIC = "\033[3m"
    RESET = "\033[0m"


COMMANDS = {"n", "b", "t", "m", "v", "e", "h", "a"}
TRUST_COLORS = {"distrustful": "red", "guarded": "bright_black", "trusting": "green"}


def c(text: str, color: Optional[str] = None) -> str:
    """Colorize text"""
    if color:
        return f"{getattr(Color, color.upper(), '')}{text}{Color.RESET}"
    return text


def rule(color: str = "yellow", char: str = "=") -> str:
    return c(char * 60, color)


def ask(prompt: str = "Choose: ") -> str:
    return input(f"\n{c(prompt, 'bright_white')}").strip().lower()


def pause():
    input(f"\n{c('Press Enter to continue...', 'bright_black')}")


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def typewrite(text: str, color: str = 'italic', instant: bool = False):
    """Print a line a few characters at a time (instantly when asked, or when not in a terminal)"""
    if instant or not sys.stdout.isatty():
        print(c(text, color))
        return
    sys.stdout.write(getattr(Color, color.upper(), ''))
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(0.008)
    print(Color.RESET)


# =============================================================================
# TEXT UI
# =============================================================================

class TextUI:
    """Console interface with colors and ASCII art"""

    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.tips = Tips(engine.SAVE_DIR)
        self.settings = Settings.load(engine.SAVE_DIR)
        self.achievements = Achievements(engine)

    def print_header(self):
        print(c(art.LOGO, 'cyan'))
        print(rule())
        print(c('  NOIR LANGUAGE RIDDLES', 'bright_white'))
        print(c('  The Babel Conspiracy', 'bright_white'))
        print(rule())

    def print_status(self):
        s = self.engine.state
        rules = self.engine.difficulty()
        hearts = "".join(c("♥", "red") if i < s.sanity else c("♡", "bright_black") for i in range(s.max_sanity))
        every = rules.streak_heart  # progress toward the next heart, if streaks restore any
        streak = "◆" * (s.streak % every) + "◇" * (every - s.streak % every) if every else str(s.streak)
        status = f"| SCORE: {s.score} | STREAK: {streak} | EVIDENCE: {len(s.inventory)} | {rules.name.upper()}"
        print(f"\n{c('SANITY: ', 'bright_white')}{hearts} {c(status, 'bright_white')}")
        print(rule())
        self.print_unlocked()

    def print_unlocked(self):
        """A banner for each achievement unlocked since the last screen"""
        for a in self.achievements.take_pending():
            print(c(f"★ ACHIEVEMENT UNLOCKED: {a.name}. {a.text}", 'bright_yellow'))

    def print_scene(self, showdown: Optional[Showdown] = None):
        if showdown:
            print(c(art.SHOWDOWN_SCENE, 'bright_black'))
            round_no = min(showdown.index + 1, len(showdown.riddles))
            print(c(f":: THE SHOWDOWN :: round {round_no} of {len(showdown.riddles)}", 'bright_red'))
            print(c("A wrong answer costs a heart. Type e to throw evidence at him and dodge a question.", 'white'))
            return
        loc = self.engine.location()
        print(c(art.SCENES[loc.id], 'bright_black'))
        print(c(f':: {loc.name.upper()} ::', 'bright_yellow'))
        print(c(loc.description, "white"))

    def print_character(self, mood: str = "neutral", line: Optional[str] = None, showdown: bool = False):
        loc = LOCATIONS[FINAL_LOCATION] if showdown else self.engine.location()
        if line is None:
            beats = self.engine.beats_unlocked(loc.id)
            if showdown:
                line = SHOWDOWN_INTRO
            elif self.engine.current_riddle() is None:
                line = f'"{loc.done_text}"'
            else:
                line = f'"{beats[-1] if beats else loc.greeting}"'
        print(c(art.PORTRAITS[loc.character][mood], 'white'))
        if showdown or not self.engine.interrogation(loc.id):
            print(c(f"{loc.character}:", 'bright_yellow'))
        else:
            trust = self.engine.trust_label(loc.character)
            print(f"{c(loc.character, 'bright_yellow')} {c(f'({trust})', TRUST_COLORS[trust])}{c(':', 'bright_yellow')}")
        typewrite(line, instant=self.settings.reduce_motion)

    def print_riddle(self, riddle: Riddle, options: List[str], eliminated: List[str],
                     hint_shown: bool, label: str):
        print(f"\n{rule('yellow', '-')}")
        print(c(f"[{label}: {riddle.language} · {riddle.category}]", 'bright_cyan'))
        print(c(f'Clue: {riddle.clue}', 'bright_magenta'))
        print(c(riddle.text, 'italic'))
        print(rule('yellow', '-'))

        if riddle.kind == "choice":
            print(f"\n{c('Answer choices:', 'bright_white')}")
            for i, option in enumerate(options, 1):
                print(f"  {c(f'[{i}]', 'yellow')} {option}")
        elif riddle.kind == "match":
            width = max(len(left) for left, _ in riddle.pairs) + 4
            print()
            for i, (left, _) in enumerate(riddle.pairs):
                print(f"  {i + 1}. {left:<{width}}{c(chr(ord('A') + i) + '.', 'yellow')} {options[i]}")
            print(c("\nType the letters for 1, 2, 3 in order (e.g. BCA).", 'bright_black'))
        else:
            print(c("\nType the word.", 'bright_black'))

        help_text = self.engine.item_help(riddle)
        if help_text:
            print(c(help_text, 'bright_green'))
        if eliminated:
            kind = "Ruled out" if riddle.kind == "choice" else "Tried"
            print(c(f"\n  {kind}: {', '.join(eliminated)}", 'bright_black'))
        if hint_shown:
            print(c(f"Hint: {riddle.hint}", 'bright_magenta'))

    def print_commands(self, showdown: bool = False):
        print()
        if showdown:
            print(c("[e] Throw evidence   [n] Notes", 'bright_black'))
            return
        print(c("[h] Hint   [e] Evidence   [n] Notes   [b] Notebook   [t] Travel   [m] Menu", 'bright_black'))
        if self.engine.interrogation():
            print(c(f"[i] Question {self.engine.location().character}", 'bright_black'))
        print(c("[a] Achievements", 'bright_black'))
        if self.engine.can_confront():
            print(c("[v] Confront Volkov (ends the case)", 'bright_red'))

    def print_end(self, title: str, text: str, color: str, triumph: bool):
        s = self.engine.state
        print(f"\n{rule(color)}")
        print(c(f'          {title}', f'bright_{color}'))
        print(rule(color))
        print(c(text, color))
        print(c(f"\nRiddles solved: {len(s.solved_riddles)}/{len(self.engine.riddles)}", 'white'))
        print(c(f"Evidence kept: {len(s.inventory)}/{self.engine.total_items()}", 'white'))
        print(c(f"Difficulty: {self.engine.difficulty().name}", 'white'))
        print(c(f"Final score: {s.score}", 'white'))
        tagline = "All our words are connected." if triumph else "The Babel Society wins. For now."
        print(f"\n{c(tagline, 'italic')}\n")
        self.print_unlocked()
        pause()

    def print_notes(self):
        print(f"\n{rule()}\n{c('          CASE NOTES', 'bright_white')}\n{rule()}")
        notes = self.engine.case_notes()
        current = None
        for place, note in notes:
            if place != current:
                print(c(f"\n{place.upper()}", 'bright_yellow'))
                current = place
            print(f"  · {note}")
        if not notes:
            print(c("\nNothing yet. Solve riddles and people will start talking.", 'bright_black'))
        pause()

    def print_notebook(self):
        entries = self.engine.notebook_entries()
        print(f"\n{rule()}\n{c('          ETYMOLOGY NOTEBOOK', 'bright_white')}\n{rule()}")
        print(c(f"{len(entries)} of {len(ALL_RIDDLES)} entries. It carries over between cases.", 'bright_black'))
        current = None
        for r in entries:
            if r.language != current:
                print(c(f"\n{r.language.upper()}", 'bright_yellow'))
                current = r.language
            print(f"  {c(r.clue, 'bright_magenta')}  →  {r.display_answer()}")
            print(f"     {r.explanation}")
        pause()

    def choose_item(self, prompt: str) -> Optional[str]:
        items = self.engine.state.inventory
        if not items:
            print(c("\nYou have no evidence.", 'bright_black'))
            pause()
            return None
        print(f"\n{c(prompt, 'bright_white')}")
        for i, item in enumerate(items, 1):
            print(f"  {c(f'[{i}]', 'yellow')} {item}")
        choice = ask("Which one (Enter to cancel): ")
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            return items[int(choice) - 1]
        return None

    def pay_for_hint(self, evidence: bool = True) -> bool:
        """A hint costs a favor from someone who trusts you, or (unless the difficulty
        rules out hints) a piece of evidence. True if paid."""
        favors = self.engine.favors()
        if not favors:
            if not evidence:
                print(c(f"\nNo hints on {self.engine.difficulty().name}. You're on your own, detective.", 'bright_black'))
                pause()
                return False
            item = self.choose_item("Trade which evidence for a hint? You lose it.")
            return bool(item and self.engine.spend_item(item))
        choices = [f"Call in {who}'s favor (free)" for who in favors] + (self.engine.state.inventory if evidence else [])
        title = "Call in a favor, or trade evidence for a hint?" if evidence else "Call in a favor?"
        print(f"\n{c(title, 'bright_white')}")
        for i, label in enumerate(choices, 1):
            print(f"  {c(f'[{i}]', 'yellow')} {label}")
        choice = ask("Which one (Enter to cancel): ")
        if not (choice.isdigit() and 1 <= int(choice) <= len(choices)):
            return False
        n = int(choice) - 1
        if n >= len(favors):
            return self.engine.spend_item(choices[n])
        who = favors[n]
        print(c(f'\n{who}: "{self.engine.call_in_favor(who)}"', 'italic'))
        pause()
        return True

    def tip(self, *keys: str):
        """Show the first of these tips that hasn't been seen yet. Typing off turns tips off."""
        key = self.tips.take(*keys)
        if not key:
            return
        print(f"\n{c('TIP · ' + TIPS[key]['title'].upper(), 'bright_cyan')}")
        for text in textwrap.wrap(TIPS[key]["console"], 58):
            print(c(f"  {text}", 'cyan'))
        if input(c("  Enter to continue, or type off to turn tips off: ", 'bright_black')).strip().lower() == "off":
            self.tips.set_enabled(False)
            print(c("  Tips are off. Turn them back on in Settings (menu, [7]).", 'bright_black'))

    def ask_elena(self) -> str:
        """The final deduction. Returns the chosen place."""
        while True:
            print(f"\n{rule('red')}\n{c(ELENA_QUESTION, 'bright_red')}\n{rule('red')}\n")
            for i, place in enumerate(ELENA_OPTIONS, 1):
                print(f"{c(f'[{i}]', 'yellow')} {place}")
            print(f"\n{c('[n] Review your case notes first', 'bright_black')}")
            choice = ask()
            if choice == "n":
                self.print_notes()
            elif choice.isdigit() and 1 <= int(choice) <= len(ELENA_OPTIONS):
                return ELENA_OPTIONS[int(choice) - 1]

    def choose_location(self) -> Optional[str]:
        """Travel menu with the map. Returns loc_id or None."""
        s = self.engine.state
        labels, places = {}, []
        for n, loc_id in enumerate(STORY_ORDER, 1):
            if loc_id not in s.unlocked_locations:
                labels[loc_id] = "[?]"
                continue
            here = loc_id == s.current_location
            labels[loc_id] = f"[{'@' if here else n}] {LOCATIONS[loc_id].name}"
            if not here:
                places.append((n, loc_id))
        print(f"\n{rule()}\n{c('          WHERE TO, DETECTIVE?', 'bright_white')}\n{rule()}")
        print(c(art.berlin_map(labels), 'bright_black'))
        if not places:
            print(c("No other leads yet. Keep digging here.", 'bright_black'))
            pause()
            return None
        for n, loc_id in places:
            solved, total = self.engine.progress(loc_id)
            print(f"{c(f'[{n}]', 'yellow')} {LOCATIONS[loc_id].name}  {c(f'{solved}/{total}', 'bright_black')}")
        choice = ask("Go to (Enter to cancel): ")
        for n, loc_id in places:
            if choice == str(n):
                return loc_id
        return None

    def choose_difficulty(self) -> Optional[str]:
        """Returns a DIFFICULTIES key, or None to go back"""
        keys = list(DIFFICULTIES)
        print(f"\n{rule()}\n{c('          CHOOSE YOUR DIFFICULTY', 'bright_white')}\n{rule()}\n")
        for n, key in enumerate(keys, 1):
            rules = DIFFICULTIES[key]
            print(f"{c(f'[{n}]', 'yellow')} {rules.name:<11}{c(rules.blurb, 'bright_black')}")
        choice = ask(f"Choose (Enter for {DIFFICULTIES[DEFAULT_DIFFICULTY].name}, b to go back): ")
        if not choice:
            return DEFAULT_DIFFICULTY
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            return keys[int(choice) - 1]
        return None

    def show_save_code(self):
        print(f"\n{rule()}\n{c('          SAVE CODE', 'bright_white')}\n{rule()}")
        print(c("Copy it or write it down. On the title screen, [c] Enter a save code picks this", 'white'))
        print(c("case up again, here or in the browser version.\n", 'white'))
        for line in savecode.lines(self.engine.save_code(), groups=6):
            print(c(f"  {line}", 'bright_yellow'))
        pause()

    def enter_save_code(self) -> bool:
        """Read a save code, which may be pasted over several lines. True once the case is restored."""
        print(f"\n{rule()}\n{c('          ENTER A SAVE CODE', 'bright_white')}\n{rule()}")
        print(c("Type or paste your code. Spaces, dashes and capitals don't matter.", 'white'))
        print(c("Press Enter on an empty line when you're done, or to go back.\n", 'bright_black'))
        lines: List[str] = []
        while True:
            line = input(c("> ", 'yellow'))
            if not line.strip():
                break
            lines.append(line)
            try:
                savecode.decode(" ".join(lines))
                break  # a whole code already: no need for the empty line
            except SaveCodeError:
                continue
        if not lines:
            return False
        try:
            self.engine.load_code(" ".join(lines))
        except SaveCodeError as error:
            print(c(f"\n{error}", 'red'))
            pause()
            return False
        print(c("\nCase restored from your save code.", 'green'))
        pause()
        return True

    def print_achievements(self):
        entries = self.achievements.entries()
        print(f"\n{rule()}\n{c('          ACHIEVEMENTS', 'bright_white')}\n{rule()}")
        print(c(f"{sum(unlocked for _, unlocked in entries)} of {len(entries)} unlocked. "
                f"They carry over between cases.\n", 'bright_black'))
        for a, unlocked in entries:
            if unlocked:
                print(f"  {c(f'★ {a.name:<15}', 'bright_yellow')}{a.text}")
            else:
                print(c(f"  ☆ {a.name:<15}{a.hint}", 'bright_black'))
        pause()

    def settings_menu(self):
        """Switch settings on and off; they are saved at once"""
        while True:
            print(f"\n{rule()}\n{c('          SETTINGS', 'bright_white')}\n{rule()}\n")
            for n, (key, label, what) in enumerate(TOGGLES, 1):
                on = self.toggle_value(key)
                print(f"{c(f'[{n}]', 'yellow')} {label}: {c('ON', 'green') if on else c('OFF', 'bright_black')}")
                print(c(f"    {what}", 'bright_black'))
            choice = ask("Switch which (Enter to go back): ")
            if not (choice.isdigit() and 1 <= int(choice) <= len(TOGGLES)):
                return
            key = TOGGLES[int(choice) - 1][0]
            if key == "tips":
                self.tips.set_enabled(not self.tips.enabled)
            else:
                setattr(self.settings, key, not getattr(self.settings, key))
                self.settings.save(self.engine.SAVE_DIR)

    def toggle_value(self, key: str) -> bool:
        """A settings row; the tips switch is kept by tips.py, the rest in settings.json"""
        return self.tips.enabled if key == "tips" else getattr(self.settings, key)

    def menu(self) -> str:
        """Save/load menu. Returns 'back', 'loaded' or 'main_menu'."""
        while True:
            print(f"\n{rule()}\n{c('          SAVE / LOAD MENU', 'bright_white')}\n{rule()}\n")
            for i, exists, label in self.engine.get_save_slots():
                print(f"{c(f'Slot {i}:', 'yellow')} {c(label, 'green' if exists else 'bright_black')}")
            print(f"\n{c('[1] Save Game', 'yellow')}\n{c('[2] Load Game', 'yellow')}")
            print(f"{c('[3] Back to Game', 'yellow')}\n{c('[4] Main Menu', 'yellow')}")
            print(f"{c('[5] Show Save Code', 'yellow')}\n{c('[6] Achievements', 'yellow')}\n{c('[7] Settings', 'yellow')}")
            choice = ask()
            if choice == "1":
                slot = ask("Save to slot (1-3, anything else to cancel): ")
                if slot in ("1", "2", "3"):
                    self.engine.save_game(int(slot))
                    print(c(f"\nGame saved to slot {slot}!", 'green'))
                    pause()
            elif choice == "2":
                slot = ask("Load slot (1-3, anything else to cancel): ")
                if slot in ("1", "2", "3"):
                    if self.engine.load_game(int(slot)):
                        print(c(f"\nGame loaded from slot {slot}!", 'green'))
                        pause()
                        return "loaded"
                    print(c("\nNo save found in that slot!", 'red'))
                    pause()
            elif choice == "3":
                return "back"
            elif choice == "4":
                return "main_menu"
            elif choice == "5":
                self.show_save_code()
            elif choice == "6":
                self.print_achievements()
            elif choice == "7":
                self.settings_menu()

    def main_menu(self) -> str:
        print(c(art.LOGO, 'cyan'))
        print(rule())
        print(c('  NOIR LANGUAGE RIDDLES', 'bright_white'))
        print(c('  The Babel Conspiracy', 'bright_white'))
        print(rule())
        print(c(art.TITLE_SCENE, 'bright_black'))
        print(c('Berlin, 1947. A linguist has disappeared.', 'bright_black'))
        print(c('Solve etymological riddles to uncover the truth.', 'bright_black'))
        print(f"\n{c('[1] New Game', 'yellow')}\n{c('[2] Continue', 'yellow')}")
        print(f"{c('[3] Etymology Notebook', 'yellow')}\n{c('[4] Quit', 'yellow')}")
        print(c("\n[c] Enter a save code   [a] Achievements   [s] Settings", 'yellow'))
        return ask()


# =============================================================================
# MAIN GAME LOOP
# =============================================================================

def read_response(engine: GameEngine, riddle: Riddle, options: List[str], choice: str) -> Optional[str]:
    """Turn what the player typed into an answer, or None if it isn't one"""
    if riddle.kind == "choice":
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        return None
    if riddle.kind == "match":
        response = engine.match_response(riddle, options, choice)
        if response is None and choice:
            print(c(f"Type {len(riddle.pairs)} different letters, one per word, e.g. BCA.", 'red'))
            pause()
        return response
    return choice or None


def fresh_options(engine: GameEngine, riddle: Optional[Riddle]) -> List[str]:
    if riddle is None:
        return []
    if riddle.kind == "choice":
        return engine.shuffled_options(riddle)
    if riddle.kind == "match":
        return engine.match_options(riddle)
    return []


def after_wrong(engine: GameEngine, riddle: Riddle, options: List[str], response: str,
                eliminated: List[str]) -> List[str]:
    """Reshape the options after a wrong answer so guessing through doesn't work"""
    if riddle.kind == "choice":
        return engine.replace_wrong_option(riddle, options, response, eliminated)
    eliminated.append(response.replace("|", ", "))
    return engine.match_options(riddle) if riddle.kind == "match" else options


def screen_tips(engine: GameEngine, riddle: Optional[Riddle]) -> List[str]:
    """The tips that fit the case screen, most urgent first"""
    keys = ["case"]
    if riddle and riddle.kind != "choice":
        keys.append("typing")
    if engine.state.current_location == FINAL_LOCATION:
        keys.append("archive")
    if engine.state.inventory:
        keys.append("evidence")
    return keys


def interrogate(engine: GameEngine, ui: TextUI) -> Tuple[str, Optional[str]]:
    """Question the character here until the player leaves.
    Returns the mood and line to keep on the case screen (None for the usual line)."""
    talk, who = engine.interrogation(), engine.location().character
    if engine.refuses():
        print(c(f'\n{who}: "{talk.refuse}"', 'italic'))
        print(c(engine.mend_advice(), 'bright_black'))
        pause()
        return "bad", f'"{talk.refuse}"'

    question: Optional[Question] = None  # the answer on the table
    mood, line, aside, spoke = "neutral", talk.opening, "", False
    while True:
        refusing = engine.refuses()
        can_press = bool(question and not engine.is_caught(question) and engine.state.inventory and not refusing)
        clear_screen()
        ui.print_status()
        print(c(f":: QUESTIONING {who.upper()} ::", 'bright_yellow'))
        ui.print_character(mood, f'"{line}"')
        if aside:
            print(aside)
        print()
        questions = engine.questions()
        if not refusing:
            # New questions are marked •, broken lies ✓
            for n, q in enumerate(questions, 1):
                mark = "✓" if engine.is_caught(q) else " " if engine.was_asked(q) else "•"
                print(f"  {c(f'[{n}]', 'yellow')} {mark} {q.ask}")
            if engine.locked_questions():
                print(c(f"        ({engine.locked_questions()} more as you solve riddles here)", 'bright_black'))
            print()
        if can_press:
            print(f"  {c('[p]', 'yellow')} Press that answer with evidence")
        print(f"  {c('[n]', 'yellow')} Case notes")
        print(f"  {c('[Enter]', 'yellow')} Leave")
        ui.tip("interrogation")
        choice = ask("Ask: " if not refusing else "Press Enter to leave: ")

        if not choice:
            return (mood, f'"{line}"') if spoke else ("neutral", None)
        if choice == "n":
            ui.print_notes()
        elif choice == "p" and can_press:
            item = ui.choose_item("Which evidence contradicts that?")
            if item:
                result = engine.press(question.id, item)
                mood, line, spoke = ("good" if result.broken else "bad"), result.line, True
                if result.broken:
                    perks = "a free hint (h) this case"
                    if talk.blessing:
                        perks += ", and a blessing before the showdown"
                    aside = c(f"\nThe lie breaks. Added to your case notes.\n{who} trusts you now: {perks}.", 'bright_green')
                else:
                    aside = c(f"\nWrong evidence. {who} trusts you less." + ("  -1 ♥" if result.heart_lost else ""), 'red')
                    if result.clammed_up:
                        aside += c(f"\n{who} clams up. {engine.mend_advice()}", 'bright_black')
        elif choice.isdigit() and not refusing and 1 <= int(choice) <= len(questions):
            question = questions[int(choice) - 1]
            mood, line, aside, spoke = "neutral", engine.ask(question.id), "", True


def finish_case(engine: GameEngine, ui: TextUI):
    """Final deduction, the showdown, the ending, and a fresh case"""
    clear_screen()
    guess = ui.ask_elena()
    engine.travel(FINAL_LOCATION)
    blessing = engine.receive_blessing()
    if blessing:
        who, line = blessing
        print(c(f"\nYou remember {who}'s blessing:", 'bright_white'))
        typewrite(f'"{line}"', instant=ui.settings.reduce_motion)
        print(c("Your nerve steadies. +1 ♥", 'bright_red'))
        pause()
    won = showdown(engine, ui, guess)
    clear_screen()
    ui.print_end(*engine.get_ending(guess, won), 'green', triumph=won)
    engine.new_game()


def showdown(engine: GameEngine, ui: TextUI, elena_guess: Optional[str] = None) -> bool:
    """Volkov's questions. Returns True if the detective wins."""
    sd = engine.start_showdown(elena_guess)
    archive = LOCATIONS[FINAL_LOCATION]
    mood, line = "neutral", None
    while not sd.finished:
        riddle = sd.current
        options = fresh_options(engine, riddle)
        eliminated: List[str] = []
        while not sd.finished and sd.current is riddle:
            clear_screen()
            ui.print_status()
            ui.print_scene(sd)
            ui.print_character(mood, line, showdown=True)
            ui.print_riddle(riddle, options, eliminated, False, "VOLKOV ASKS")
            ui.print_commands(showdown=True)
            if riddle.kind != "choice":
                ui.tip("typing")
            choice = ask("Your answer: ")
            if choice == "n":
                ui.print_notes()
                continue
            if choice == "e":
                item = ui.choose_item("Throw which evidence at Volkov? It dodges this question.")
                if item and sd.dodge(item):
                    mood, line = "good", f'"...The {item}. Where did you find that?"'
                continue
            response = read_response(engine, riddle, options, choice)
            if response is None:
                continue
            if sd.answer(response):
                mood, line = "good", f'"{random.choice(archive.good_lines)}"'
                print(f"\n{c('✓ CORRECT!', 'green')} {c(riddle.explanation, 'white')}")
                pause()
            else:
                mood, line = "bad", f'"{random.choice(archive.bad_lines)}"'
                options = after_wrong(engine, riddle, options, response, eliminated)
    return sd.won


def play(engine: GameEngine, ui: TextUI):
    """Run one case until it ends or the player returns to the main menu"""
    while True:
        riddle = engine.current_riddle()
        options = fresh_options(engine, riddle)
        eliminated: List[str] = []
        hint_shown = False
        mood, line = "neutral", None
        loc = engine.location()

        # Ask the current riddle until it is solved or the player does something else
        while True:
            clear_screen()
            ui.print_header()
            ui.print_status()
            ui.print_scene()
            ui.print_character(mood, line)
            if riddle:
                label = "LEAD" if riddle.id == loc.lead_riddle else "Riddle"
                ui.print_riddle(riddle, options, eliminated, hint_shown, label)
                ui.print_commands()
                ui.tip(*screen_tips(engine, riddle))
                choice = ask("Your answer: ")
            else:
                print(c("\nYou've turned this place inside out. Time to follow another lead.", 'bright_black'))
                ui.print_commands()
                ui.tip(*screen_tips(engine, riddle))
                choice = ask()

            if choice == "n":
                ui.print_notes()
                continue
            if choice == "b":
                ui.print_notebook()
                continue
            if choice == "a":
                ui.print_achievements()
                continue
            if choice == "e":
                item = ui.choose_item(f"Show {loc.character} which evidence?")
                if item:
                    text = engine.present(item)
                    mood, line = ("good", f'"{text}"') if text else ("neutral", f'"The {item}? That means nothing to me."')
                continue
            if choice == "i" and engine.interrogation():
                mood, line = interrogate(engine, ui)
                continue
            if choice == "h" and riddle and not hint_shown:
                cost = engine.hint_cost(bool(eliminated))
                if cost != "free" and not ui.pay_for_hint(evidence=cost == "evidence"):
                    continue
                hint_shown = True
                continue
            if choice == "t":
                dest = ui.choose_location()
                if dest:
                    engine.travel(dest)
                break
            if choice == "m":
                if ui.menu() == "main_menu":
                    return
                break
            if choice == "v" and engine.can_confront():
                finish_case(engine, ui)
                return
            if not riddle or choice in COMMANDS:
                continue

            response = read_response(engine, riddle, options, choice)
            if response is None:
                continue
            result = engine.answer(riddle, response)
            if not result.correct:
                options = after_wrong(engine, riddle, options, response, eliminated)
                mood, line = "bad", f'"{random.choice(loc.bad_lines)}"'
                if engine.is_game_over():
                    clear_screen()
                    print(c(art.GAME_OVER, 'red'))
                    ui.print_end("GAME OVER", "Volkov's men found you first.", 'red', triumph=False)
                    engine.new_game()
                    return
                continue

            # Correct: redraw with the character's reaction, then the payoff
            clear_screen()
            ui.print_header()
            ui.print_status()
            ui.print_scene()
            ui.print_character("good", f'"{random.choice(loc.good_lines)}"')
            print(f"\n{c('✓ CORRECT!', 'green')} {c(riddle.display_answer(), 'bright_green')}")
            print(c(riddle.explanation, 'white'))
            if riddle.item:
                if result.item_gained:
                    print(c(f"\nEvidence collected: {riddle.item}", 'bright_green'))
                else:
                    print(c(f"\nYou fumbled earlier. The {riddle.item} slipped through your fingers.", 'bright_black'))
            if result.streak_bonus:
                print(c(f"Streak x{engine.state.streak}: +{result.streak_bonus} bonus", 'bright_yellow'))
            if result.heart_restored:
                print(c(f"{engine.difficulty().streak_heart} clean answers in a row steady your nerve. +1 ♥",
                        'bright_red'))
            if result.beat:
                print(c(f'\nNEW NOTE: {loc.character}: "{result.beat}"', 'bright_cyan'))
            if engine.all_riddles_solved():
                pause()
                finish_case(engine, ui)
                return
            if result.unlocked:
                new_loc = LOCATIONS[result.unlocked]
                print(c(f"\n{loc.lead_text}", 'italic'))
                print(c(f"\nNEW LEAD: {new_loc.name}", 'bright_yellow'))
                ui.tip("lead")
                if ask(f"[1] Go to {new_loc.name} now, Enter to keep digging here: ") == "1":
                    engine.travel(new_loc.id)
            else:
                pause()
            break


def main():
    """Main game entry point"""
    engine = GameEngine()
    ui = TextUI(engine)

    while True:
        clear_screen()
        choice = ui.main_menu()

        if choice == "1":
            difficulty = ui.choose_difficulty()
            if difficulty:
                engine.new_game(difficulty)
                play(engine, ui)
        elif choice == "c":
            if ui.enter_save_code():
                play(engine, ui)
        elif choice == "a":
            ui.print_achievements()
        elif choice == "s":
            ui.settings_menu()
        elif choice == "2":
            if engine.load_game(0):
                play(engine, ui)
            else:
                print(c('\nNo saved game found!', 'red'))
                pause()
        elif choice == "3":
            ui.print_notebook()
        elif choice == "4":
            print(c('\nGoodbye, detective.', 'bright_black'))
            return


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nGoodbye, detective.")
