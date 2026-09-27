#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
A polished text-based detective game about etymology

Run with: python main_polished.py
(For the full-screen ASCII art version, run: python tui.py)
"""

import os
from typing import List, Optional

import art
from engine import GameEngine, Riddle, STORY_ORDER, LOCATIONS


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
        print(f"\n{c('SANITY: ', 'bright_white')}{hearts} "
              f"{c(f'| SCORE: {s.score} | EVIDENCE: {len(s.inventory)}/{self.engine.total_items()}', 'bright_white')}")
        print(rule())

    def print_location(self):
        loc = self.engine.location()
        print(c(art.SCENES[loc.id], 'bright_black'))
        print(c(f':: {loc.name.upper()} ::', 'bright_yellow'))
        print(c(loc.description, "white"))

        if self.engine.current_riddle() is None:
            line = f'"{loc.done_text}"'
        else:
            line = f'"{loc.greeting}"'
        print(c(art.PORTRAITS[loc.character], 'white'))
        print(c(f"{loc.character}:", 'bright_yellow'), c(line, 'italic'))

    def print_riddle(self, riddle: Riddle, options: List[str], wrong: List[int]):
        is_lead = riddle.id == self.engine.location().lead_riddle
        print(f"\n{rule('yellow', '-')}")
        print(c(f"[{'LEAD' if is_lead else 'Riddle'}: {riddle.language}]", 'bright_cyan'))
        print(c(f'Clue: {riddle.clue}', 'bright_magenta'))
        print(c(riddle.text, 'italic'))
        print(rule('yellow', '-'))

        print(f"\n{c('Answer choices:', 'bright_white')}")
        for i, option in enumerate(options, 1):
            if i - 1 in wrong:
                print(c(f"  [{i}] {option}  (wrong)", 'bright_black'))
            else:
                print(f"  {c(f'[{i}]', 'yellow')} {option}")
        self.print_commands()

    def print_commands(self):
        print()
        print(c("[t] Travel   [m] Menu", 'bright_black'))
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

def play(engine: GameEngine, ui: TextUI):
    """Run one case until it ends or the player returns to the main menu"""
    while True:
        riddle = engine.current_riddle()
        options = engine.shuffled_options(riddle) if riddle else []
        wrong: List[int] = []

        # Ask the current riddle until it is solved or the player does something else
        while True:
            clear_screen()
            ui.print_header()
            ui.print_status()
            ui.print_location()
            if riddle:
                ui.print_riddle(riddle, options, wrong)
                choice = ask("Your answer: ")
            else:
                print(c("\nYou've turned this place inside out. Time to follow another lead.", 'bright_black'))
                ui.print_commands()
                choice = ask()

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
                clear_screen()
                ui.print_end(*engine.get_ending(), 'green')
                engine.new_game()
                return
            if not (riddle and choice.isdigit() and 1 <= int(choice) <= len(options)) or int(choice) - 1 in wrong:
                continue

            idx = int(choice) - 1
            result = engine.answer(riddle, options[idx])
            if not result.correct:
                wrong.append(idx)
                if engine.is_game_over():
                    clear_screen()
                    print(c(art.GAME_OVER, 'red'))
                    ui.print_end("GAME OVER", "Volkov's men found you first.", 'red')
                    engine.new_game()
                    return
                print(c("\n✗ WRONG! You lose 1 Sanity point.", 'red'))
                if ask("[h] Show hint, Enter to try again: ") == "h":
                    print(c(f"\nHint: {riddle.hint}", 'bright_magenta'))
                    pause()
                continue

            # Correct
            print(f"\n{c('✓ CORRECT!', 'green')} {c(riddle.explanation, 'white')}")
            if riddle.item:
                if result.item_gained:
                    print(c(f"\nEvidence collected: {riddle.item}", 'bright_green'))
                else:
                    print(c(f"\nYou fumbled earlier. The {riddle.item} slipped through your fingers.", 'bright_black'))
            if engine.all_riddles_solved():
                pause()
                clear_screen()
                ui.print_end(*engine.get_ending(), 'green')
                engine.new_game()
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
