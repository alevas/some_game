#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
A polished text-based detective game about etymology

Run with: python main_polished.py
(For the full-screen ASCII art version, run: python tui.py)
"""

import os
import random
from typing import List, Optional

import art
from engine import GameEngine, Riddle, LOCATIONS, ELENA_QUESTION, ELENA_OPTIONS


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
              f"{c(f'| SCORE: {s.score} | STREAK: {streak} | EVIDENCE: {len(s.inventory)}/{self.engine.total_items()}', 'bright_white')}")
        print(rule())

    def print_location(self, mood: str = "neutral", reaction: Optional[str] = None):
        loc = self.engine.location()
        print(c(art.SCENES[loc.id], 'bright_black'))
        print(c(f':: {loc.name.upper()} ::', 'bright_yellow'))
        print(c(loc.description, "white"))

        beats = self.engine.beats_unlocked(loc.id)
        if reaction:
            line = f'"{reaction}"'
        elif self.engine.current_riddle() is None:
            line = f'"{loc.done_text}"'
        elif beats:
            line = f'"{beats[-1]}"'
        else:
            line = f'"{loc.greeting}"'
        print(c(art.PORTRAITS[loc.character][mood], 'white'))
        print(c(f"{loc.character}:", 'bright_yellow'), c(line, 'italic'))

    def print_riddle(self, riddle: Riddle, options: List[str], eliminated: List[str]):
        is_lead = riddle.id == self.engine.location().lead_riddle
        print(f"\n{rule('yellow', '-')}")
        print(c(f"[{'LEAD' if is_lead else 'Riddle'}: {riddle.language}]", 'bright_cyan'))
        print(c(f'Clue: {riddle.clue}', 'bright_magenta'))
        print(c(riddle.text, 'italic'))
        print(rule('yellow', '-'))

        print(f"\n{c('Answer choices:', 'bright_white')}")
        for i, option in enumerate(options, 1):
            print(f"  {c(f'[{i}]', 'yellow')} {option}")
        if eliminated:
            print(c(f"\n  Ruled out: {', '.join(eliminated)}", 'bright_black'))
        self.print_commands()

    def print_commands(self):
        print()
        print(c("[n] Notes   [t] Travel   [m] Menu", 'bright_black'))
        if self.engine.can_confront():
            print(c("[v] Confront Volkov (ends the case)", 'bright_red'))

    def print_end(self, title: str, text: str, color: str):
        s = self.engine.state
        print(f"\n{rule(color)}")
        print(c(f'          {title}', f'bright_{color}'))
        print(rule(color))
        print(c(text, color))
        print(c(f"\nRiddles solved: {len(s.solved_riddles)}/{len(self.engine.riddles)}", 'white'))
        print(c(f"Evidence collected: {len(s.inventory)}/{self.engine.total_items()}", 'white'))
        print(c(f"Final score: {s.score}", 'white'))
        tagline = "All our words are connected." if self.engine.all_riddles_solved() else "The Babel Society wins. For now."
        print(f"\n{c(tagline, 'italic')}")
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
        """Travel menu. Returns loc_id or None."""
        s = self.engine.state
        places = [l for l in self.engine.unlocked_locations() if l.id != s.current_location]
        if not places:
            print(c("\nNo other leads yet. Keep digging here.", 'bright_black'))
            pause()
            return None
        print(f"\n{rule()}\n{c('          WHERE TO, DETECTIVE?', 'bright_white')}\n{rule()}\n")
        for i, loc in enumerate(places, 1):
            solved, total = self.engine.progress(loc.id)
            print(f"{c(f'[{i}]', 'yellow')} {loc.name}  {c(f'{solved}/{total}', 'bright_black')}")
        print(f"\n{c('[0] Cancel', 'yellow')}")
        choice = ask()
        if choice.isdigit() and 1 <= int(choice) <= len(places):
            return places[int(choice) - 1].id
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
        print(f"\n{c('[1] New Game', 'yellow')}\n{c('[2] Continue', 'yellow')}\n{c('[3] Quit', 'yellow')}")
        return ask()


# =============================================================================
# MAIN GAME LOOP
# =============================================================================

def finish_case(engine: GameEngine, ui: TextUI):
    """Final deduction, ending screen, and a fresh case"""
    clear_screen()
    guess = ui.ask_elena()
    clear_screen()
    ui.print_end(*engine.get_ending(guess), 'green')
    engine.new_game()


def play(engine: GameEngine, ui: TextUI):
    """Run one case until it ends or the player returns to the main menu"""
    while True:
        riddle = engine.current_riddle()
        options = engine.shuffled_options(riddle) if riddle else []
        eliminated: List[str] = []
        mood, reaction = "neutral", None
        loc = engine.location()

        # Ask the current riddle until it is solved or the player does something else
        while True:
            clear_screen()
            ui.print_header()
            ui.print_status()
            ui.print_location(mood, reaction)
            if riddle:
                ui.print_riddle(riddle, options, eliminated)
                choice = ask("Your answer: ")
            else:
                print(c("\nYou've turned this place inside out. Time to follow another lead.", 'bright_black'))
                ui.print_commands()
                choice = ask()

            if choice == "n":
                ui.print_notes()
                continue
            if choice == "t":
                dest = ui.choose_location()
                if dest:
                    engine.travel(dest)
                break
            if choice == "m":
                action = ui.menu()
                if action == "main_menu":
                    return
                break
            if choice == "v" and engine.can_confront():
                finish_case(engine, ui)
                return
            if not (riddle and choice.isdigit() and 1 <= int(choice) <= len(options)):
                continue

            picked = options[int(choice) - 1]
            result = engine.answer(riddle, picked)
            if not result.correct:
                options = engine.replace_wrong_option(riddle, options, picked, eliminated)
                mood, reaction = "bad", random.choice(loc.bad_lines) if loc.bad_lines else None
                if engine.is_game_over():
                    clear_screen()
                    print(c(art.GAME_OVER, 'red'))
                    ui.print_end("GAME OVER", "Volkov's men found you first.", 'red')
                    engine.new_game()
                    return
                print(c("\n✗ WRONG! You lose 1 Sanity point. The answers blur and rearrange.", 'red'))
                if ask("[h] Show hint, Enter to try again: ") == "h":
                    print(c(f"\nHint: {riddle.hint}", 'bright_magenta'))
                    pause()
                continue

            # Correct: redraw with the character's reaction, then the payoff
            clear_screen()
            ui.print_header()
            ui.print_status()
            ui.print_location("good", random.choice(loc.good_lines) if loc.good_lines else None)
            print(f"\n{c('✓ CORRECT!', 'green')} {c(riddle.explanation, 'white')}")
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
                print(c(f"\n{engine.location().lead_text}", 'italic'))
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
            print(c('\nGoodbye, detective.', 'bright_black'))
            return


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nGoodbye, detective.")
