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
import time
from typing import List, Optional

import art
from engine import (GameEngine, Riddle, Showdown, LOCATIONS, STORY_ORDER, ALL_RIDDLES,
                    ELENA_QUESTION, ELENA_OPTIONS, FINAL_LOCATION, SHOWDOWN_INTRO)


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


COMMANDS = {"n", "b", "t", "m", "v", "e", "h"}
DAILY_LABELS = {"new": "Daily Case", "in progress": "Daily Case (continue)", "done": "Daily Case (done: replay)"}


def c(text: str, color: Optional[str] = None) -> str:
    """Colorize text"""
    if color:
        return f"{getattr(Color, color.upper(), '')}{text}{Color.RESET}"
    return text


def rule(color: str = "yellow", char: str = "=") -> str:
    return c(char * 60, color)


def letters_example(count: int) -> str:
    """Example input for a letters answer: BCA for three, BCDA for four"""
    letters = "".join(chr(ord("A") + i) for i in range(count))
    return letters[1:] + letters[:1]


def ask(prompt: str = "Choose: ") -> str:
    return input(f"\n{c(prompt, 'bright_white')}").strip().lower()


def pause():
    input(f"\n{c('Press Enter to continue...', 'bright_black')}")


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def typewrite(text: str, color: str = 'italic'):
    """Print a line a few characters at a time (instantly when not in a terminal)"""
    if not sys.stdout.isatty():
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

    def print_header(self):
        print(c(art.LOGO, 'cyan'))
        print(rule())
        print(c('  NOIR LANGUAGE RIDDLES', 'bright_white'))
        print(c('  The Babel Conspiracy', 'bright_white'))
        print(rule())

    def print_status(self):
        s = self.engine.state
        hearts = "".join(c("♥", "red") if i < s.sanity else c("♡", "bright_black") for i in range(s.max_sanity))
        streak = "◆" * (s.streak % 3) + "◇" * (3 - s.streak % 3)
        print(f"\n{c('SANITY: ', 'bright_white')}{hearts} "
              f"{c(f'| SCORE: {s.score} | STREAK: {streak} | EVIDENCE: {len(s.inventory)}', 'bright_white')}")
        if s.daily:
            print(c(f"DAILY CASE {s.daily}{'  (replay)' if s.replay else ''}", 'bright_magenta'))
        print(rule())

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
        print(c(f"{loc.character}:", 'bright_yellow'))
        typewrite(line)

    def print_riddle(self, riddle: Riddle, options: List[str], eliminated: List[str],
                     hint_shown: bool, label: str):
        print(f"\n{rule('yellow', '-')}")
        print(c(f"[{label}: {riddle.language} · {riddle.category}]", 'bright_cyan'))
        print(c(f'Clue: {riddle.clue}', 'bright_magenta'))
        print(c(riddle.text, 'italic'))
        if riddle.diagram:
            print()
            print(c(riddle.diagram, 'white').replace("???", c("???", 'bright_yellow') + Color.WHITE))
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
            numbers = ", ".join(str(i + 1) for i in range(len(riddle.pairs)))
            print(c(f"\nType the letters for {numbers} in order (e.g. {letters_example(len(riddle.pairs))}).",
                    'bright_black'))
        elif riddle.kind == "order":
            print()
            for i, step in enumerate(options):
                print(f"  {c(chr(ord('A') + i) + '.', 'yellow')} {step}")
            print(c(f"\nType the letters from first to last (e.g. {letters_example(len(options))}).", 'bright_black'))
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
        if self.engine.can_confront():
            print(c("[v] Confront Volkov (ends the case)", 'bright_red'))

    def print_end(self, title: str, text: str, color: str, triumph: bool, share: Optional[str] = None):
        s = self.engine.state
        print(f"\n{rule(color)}")
        print(c(f'          {title}', f'bright_{color}'))
        print(rule(color))
        print(c(text, color))
        print(c(f"\nRiddles solved: {self.engine.solved_count()}/{len(self.engine.case_riddles())}", 'white'))
        print(c(f"Evidence kept: {len(s.inventory)}/{self.engine.total_items()}", 'white'))
        print(c(f"Final score: {s.score}", 'white'))
        tagline = "All our words are connected." if triumph else "The Babel Society wins. For now."
        print(f"\n{c(tagline, 'italic')}")
        if share:
            print(c("\nToday's result, to share (select and copy it):\n", 'bright_yellow'))
            print(share)
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

    def menu(self) -> str:
        """Save/load menu. Returns 'back', 'loaded' or 'main_menu'."""
        while True:
            print(f"\n{rule()}\n{c('          SAVE / LOAD MENU', 'bright_white')}\n{rule()}\n")
            for i, exists, label in self.engine.get_save_slots():
                print(f"{c(f'Slot {i}:', 'yellow')} {c(label, 'green' if exists else 'bright_black')}")
            print(f"\n{c('[1] Save Game', 'yellow')}\n{c('[2] Load Game', 'yellow')}")
            print(f"{c('[3] Back to Game', 'yellow')}\n{c('[4] Main Menu', 'yellow')}")
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
        print(c(f"[d] {DAILY_LABELS[self.engine.daily_status()]}", 'yellow'))
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
    if riddle.kind in ("match", "order"):
        response = engine.match_response(riddle, options, choice)
        if response is None and choice:
            print(c(f"Type {len(options)} different letters, each once, e.g. {letters_example(len(options))}.", 'red'))
            pause()
        return response
    return choice or None


def fresh_options(engine: GameEngine, riddle: Optional[Riddle]) -> List[str]:
    if riddle is None:
        return []
    if riddle.kind == "choice":
        return engine.shuffled_options(riddle)
    if riddle.kind in ("match", "order"):
        return engine.match_options(riddle)
    return []


def after_wrong(engine: GameEngine, riddle: Riddle, options: List[str], response: str,
                eliminated: List[str]) -> List[str]:
    """Reshape the options after a wrong answer so guessing through doesn't work"""
    if riddle.kind == "choice":
        return engine.replace_wrong_option(riddle, options, response, eliminated)
    eliminated.append(response.replace("|", " → " if riddle.kind == "order" else ", "))
    return engine.match_options(riddle) if riddle.kind in ("match", "order") else options


def finish_case(engine: GameEngine, ui: TextUI):
    """Final deduction, the showdown, the ending, and a fresh case"""
    clear_screen()
    guess = ui.ask_elena()
    engine.travel(FINAL_LOCATION)
    won = showdown(engine, ui)
    clear_screen()
    title, text = engine.get_ending(guess, won)
    ui.print_end(title, text, 'green', triumph=won, share=engine.finish_daily(title, guess))
    engine.end_case()


def showdown(engine: GameEngine, ui: TextUI) -> bool:
    """Volkov's questions. Returns True if the detective wins."""
    sd = engine.start_showdown()
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
                choice = ask("Your answer: ")
            else:
                print(c("\nYou've turned this place inside out. Time to follow another lead.", 'bright_black'))
                ui.print_commands()
                choice = ask()

            if choice == "n":
                ui.print_notes()
                continue
            if choice == "b":
                ui.print_notebook()
                continue
            if choice == "e":
                item = ui.choose_item(f"Show {loc.character} which evidence?")
                if item:
                    text = engine.present(item)
                    mood, line = ("good", f'"{text}"') if text else ("neutral", f'"The {item}? That means nothing to me."')
                continue
            if choice == "h" and riddle and not hint_shown:
                if not eliminated:
                    item = ui.choose_item("Trade which evidence for a hint? You lose it.")
                    if not (item and engine.spend_item(item)):
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
                    ui.print_end("GAME OVER", "Volkov's men found you first.", 'red', triumph=False,
                                 share=engine.finish_daily("GAME OVER"))
                    engine.end_case()
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
                print(c("Three clean answers in a row steady your nerve. +1 ♥", 'bright_red'))
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
            engine.new_game()
            play(engine, ui)
        elif choice == "2":
            if engine.load_game(0):
                play(engine, ui)
            else:
                print(c('\nNo saved game found!', 'red'))
                pause()
        elif choice == "3":
            ui.print_notebook()
        elif choice == "d":
            if engine.start_daily():
                print(c("\nBack to today's case.", 'bright_black'))
            elif engine.state.replay:
                print(c("\nYou have closed today's case already. A replay won't change your result.", 'bright_black'))
            else:
                print(c(f"\nThe daily case for {engine.state.daily}: everyone gets these riddles today. "
                        "It is shorter, and it doesn't touch your other case.", 'bright_black'))
            pause()
            play(engine, ui)
        elif choice == "4":
            print(c('\nGoodbye, detective.', 'bright_black'))
            return


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nGoodbye, detective.")
