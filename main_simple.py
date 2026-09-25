#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
A simple text-based detective game about etymology

Run with: python main_simple.py

This version uses only standard Python - no external dependencies.
It will work on any system with Python 3.7+
"""

import json
import os
import random
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


# =============================================================================
# DATA MODULE (inline for simplicity)
# =============================================================================

@dataclass
class Riddle:
    id: int
    language: str
    category: str
    text: str
    clue: str
    answer: str
    wrong_answers: List[str]
    hint: str
    explanation: str
    next_location: Optional[str] = None
    item: Optional[str] = None
    difficulty: int = 1


@dataclass 
class Location:
    id: str
    name: str
    description: str
    first_riddle: int = 1


# Game database
RIDDLES = [
    Riddle(1, "Greek", "location", "In Greek, it is βιβλίο (vivlio). Where do these live?",
           "βιβλίο", "Library", ["University", "Bookstore"],
           "Think where books are collected and borrowed.",
           "From Greek βιβλιον (biblion) = book.", "Library", "Case File", 1),
    
    Riddle(2, "German", "location", "In German, linguists met where Kaffee flows. Where?",
           "Linguisten trafen sich, wo Kaffee fließt", "Café Mozart", 
           ["The university", "A beer hall"], "Not a pub. Somewhere with coffee.",
           "Kaffee = coffee. Berlin intellectuals met in cafes.", "Cafe", "Sugar Packet", 1),
    
    Riddle(3, "Spanish", "etymology", "This word is libro in Spanish, livre in French, Buch in German. What is it in English?",
           "libro | livre | Buch", "Book", ["Library", "Novel"],
           "All three words mean the same thing.",
           "All descend from Latin liber.", "Cafe", "Dictionary", 1),
    
    Riddle(4, "Russian", "etymology", "This Slavic word is передача meaning transmission. What English word shares Latin root 'trahere'?",
           "передача", "Tradition", ["Transfer", "Translation"],
           "Think of passing down through generations.",
           "From Latin tradere = to hand over.", "Archive", "Cipher Wheel", 2),
    
    Riddle(5, "Arvanitika", "false friends", "In Arvanitika, it is buke. In Greek, it is ψωμί. What is it in English?",
           "buke | ψωμί", "Bread", ["Book", "Brick"], "It is a staple food.",
           "Arvanitika buke and Greek ψωμί both mean bread.", "Cafe", "Arvanitika Notes", 2),
    
    Riddle(6, "Greek", "etymology", "In Greek, it is πατήρ (pater). In German, it is Vater. What is it in English?",
           "πατήρ | Vater", "Father", ["Mother", "Brother"], "PIE root: *pəter",
           "All descend from Proto-Indo-European *pəter.", "Church", None, 1),
    
    Riddle(7, "German", "false friends", "In German, Gift does not mean a present. What does it mean?",
           "Gift", "Poison", ["Gift", "Present"], "In English, gift is positive.",
           "German Gift = poison. English gift comes from Old Norse.", "Cafe", None, 1),
    
    Riddle(8, "English", "cognates", "This word is mother in English, Mutter in German, μητέρα in Greek. What is it?",
           "mother | Mutter | μητέρα", "Mother", ["Sister", "Aunt"], "PIE root: *méh₂tēr",
           "All from PIE *méh₂tēr. Preserved across 4000+ years.", "Church", "Family Tree", 1),
    
    Riddle(9, "Spanish", "etymology", "This word is noche in Spanish. In Latin it was nox. What is it in English?",
           "noche | nox", "Night", ["Noon", "Noxious"], "It is the opposite of day.",
           "From Latin nox/noctis.", "Library", None, 1),
    
    Riddle(10, "Russian", "etymology", "This Russian word is водка (vodka). From вода (voda) meaning water. What is the connection?",
           "водка | вода", "Little water", ["Fire water", "Strong drink"], "Vodka is a diminutive.",
           "Vodka is the diminutive of вода (water).", "Cafe", "Vodka Bottle", 2),
]

LOCATIONS = {
    "ClientOffice": Location("ClientOffice", "Weber's Private Office",
        "The dim glow of a desk lamp illuminates stacks of case files. Berlin, 1947. "
        "A typewriter sits silent, waiting. On the desk, a note in Greek catches your eye. "
        "Elena Weber, a linguist, has disappeared. The only clue: a trail of etymological breadcrumbs.", 1),
    
    "Library": Location("Library", "Staatsbibliothek",
        "Tall shelves stretch into shadow. Ancient manuscripts in Greek, German, Latin. "
        "The air smells of parchment and secrets. A librarian eyes you suspiciously.", 3),
    
    "Cafe": Location("Cafe", "Café Mozart",
        "The scent of strong coffee and sugar hangs in the air. Intellectuals and spies "
        "share tables in the dim light. A waiter polishes a glass, watching.", 2),
    
    "Church": Location("Church", "St. Nicholas Church",
        "Candlelight flickers against stone walls. The sacristan moves silently between shadows. "
        "Old texts in Greek and Latin line the shelves. The Babel Society has left its mark here.", 6),
    
    "Archive": Location("Archive", "Secret Archive",
        "Files upon files of linguistic research. The Babel Society's true work is here. "
        "Volkov, their leader, has been one step ahead. But you're closing in.", 4),
}

LOCATION_CHARACTER = {
    "ClientOffice": ("Elena Weber", "I need your help, detective. The Babel Society is real."),
    "Library": ("Herr Schmidt", "She was here last week. Asking about Proto-Indo-European again."),
    "Cafe": ("Karl", "The men in dark suits come in every Tuesday."),
    "Church": ("Father Thomas", "The church has secrets older than the building."),
    "Archive": ("Igor Volkov", "You're too late. The work is already done."),
}


# =============================================================================
# GAME STATE
# =============================================================================

@dataclass
class GameState:
    current_location: str = "ClientOffice"
    solved_riddles: List[int] = field(default_factory=list)
    inventory: List[str] = field(default_factory=list)
    sanity: int = 3
    max_sanity: int = 3
    score: int = 0
    visited_locations: List[str] = field(default_factory=list)


# =============================================================================
# GAME ENGINE
# =============================================================================

class GameEngine:
    """Core game logic"""
    
    SAVE_DIR = Path.home() / ".babel_conspiracy_saves"
    
    def __init__(self):
        self.state = GameState()
        self.riddles = RIDDLES
        self.locations = LOCATIONS
        self.location_character = LOCATION_CHARACTER
        self._ensure_save_dir()
    
    def _ensure_save_dir(self):
        self.SAVE_DIR.mkdir(parents=True, exist_ok=True)
    
    def get_location(self, loc_id: str) -> Optional[Location]:
        return self.locations.get(loc_id)
    
    def get_riddle(self, riddle_id: int) -> Optional[Riddle]:
        for r in self.riddles:
            if r.id == riddle_id:
                return r
        return None
    
    def get_current_location(self) -> Optional[Location]:
        return self.get_location(self.state.current_location)
    
    def get_current_riddle(self) -> Optional[Riddle]:
        """Get first unsolved riddle for current location"""
        loc = self.get_current_location()
        if not loc:
            return None
        
        # Find riddle that points to this location or is the first riddle
        for r in self.riddles:
            if r.next_location == loc.id and r.id not in self.state.solved_riddles:
                return r
        
        # Fallback to first_riddle
        first = self.get_riddle(loc.first_riddle)
        if first and first.id not in self.state.solved_riddles:
            return first
        
        return None
    
    def check_answer(self, riddle_id: int, answer: str) -> tuple:
        """Check answer and update state. Returns (is_correct, riddle, next_location)"""
        riddle = self.get_riddle(riddle_id)
        if not riddle:
            return False, None, None
        
        is_correct = answer.lower() == riddle.answer.lower()
        
        if is_correct:
            if riddle.id not in self.state.solved_riddles:
                self.state.solved_riddles.append(riddle.id)
            self.state.score += riddle.difficulty * 10
            
            if riddle.item and riddle.item not in self.state.inventory:
                self.state.inventory.append(riddle.item)
        else:
            self.state.sanity -= 1
        
        return is_correct, riddle, riddle.next_location
    
    def move_to_location(self, loc_id: str) -> bool:
        """Move to a new location"""
        loc = self.get_location(loc_id)
        if loc:
            self.state.current_location = loc_id
            if loc_id not in self.state.visited_locations:
                self.state.visited_locations.append(loc_id)
            return True
        return False
    
    def get_random_unsolved_riddle(self) -> Optional[Riddle]:
        unsolved = [r for r in self.riddles if r.id not in self.state.solved_riddles]
        return random.choice(unsolved) if unsolved else None
    
    def get_random_location(self) -> Optional[Location]:
        """Get a random location with unsolved riddles"""
        # Find locations that have unsolved riddles
        locs_with_riddles = []
        for loc_id, loc in self.locations.items():
            for r in self.riddles:
                if r.next_location == loc_id and r.id not in self.state.solved_riddles:
                    locs_with_riddles.append(loc_id)
                    break
        
        if locs_with_riddles:
            return self.locations.get(random.choice(locs_with_riddles))
        
        # Fallback: any location
        return random.choice(list(self.locations.values()))
    
    def get_ending(self) -> tuple:
        """Determine ending based on progress"""
        total_riddles = len(self.riddles)
        total_items = len([r for r in self.riddles if r.item])
        solved = len(self.state.solved_riddles)
        collected = len(self.state.inventory)
        
        if solved >= total_riddles and collected >= total_items:
            return "The Truth Revealed", "With all clues, you expose the Babel Society to the world."
        elif solved >= total_riddles:
            return "Partial Victory", "You solve the case but Volkov escapes."
        elif solved >= total_riddles / 2:
            return "A Lead, Not a Victory", "You gather evidence but the Society remains."
        else:
            return "Case Closed", "You solved the case but Volkov escaped."
    
    def is_game_over(self) -> bool:
        return self.state.sanity <= 0
    
    def all_riddles_solved(self) -> bool:
        return len(self.state.solved_riddles) >= len(self.riddles)
    
    def save_game(self, slot: int = 0):
        """Save game to file"""
        state_dict = {
            "current_location": self.state.current_location,
            "solved_riddles": self.state.solved_riddles,
            "inventory": self.state.inventory,
            "sanity": self.state.sanity,
            "max_sanity": self.state.max_sanity,
            "score": self.state.score,
            "visited_locations": self.state.visited_locations,
        }
        
        save_path = self.SAVE_DIR / f"slot_{slot}.json"
        with open(save_path, 'w') as f:
            json.dump(state_dict, f, indent=2)
        
        # Also autosave
        with open(self.SAVE_DIR / "autosave.json", 'w') as f:
            json.dump(state_dict, f, indent=2)
    
    def load_game(self, slot: int = 0) -> bool:
        """Load game from file. slot=0 is autosave"""
        if slot == 0:
            save_path = self.SAVE_DIR / "autosave.json"
        else:
            save_path = self.SAVE_DIR / f"slot_{slot}.json"
        
        if not save_path.exists():
            return False
        
        try:
            with open(save_path, 'r') as f:
                state_dict = json.load(f)
            
            self.state = GameState(
                current_location=state_dict.get("current_location", "ClientOffice"),
                solved_riddles=state_dict.get("solved_riddles", []),
                inventory=state_dict.get("inventory", []),
                sanity=state_dict.get("sanity", 3),
                max_sanity=state_dict.get("max_sanity", 3),
                score=state_dict.get("score", 0),
                visited_locations=state_dict.get("visited_locations", [])
            )
            return True
        except Exception as e:
            print(f"Error loading save: {e}")
            return False
    
    def get_save_slots(self) -> List[tuple]:
        """Get info for all save slots"""
        slots = []
        for i in range(1, 4):
            save_path = self.SAVE_DIR / f"slot_{i}.json"
            if save_path.exists():
                try:
                    with open(save_path, 'r') as f:
                        data = json.load(f)
                    slots.append((i, True, f"Score: {data['score']}, Sanity: {data['sanity']}"))
                except:
                    slots.append((i, False, "Corrupted"))
            else:
                slots.append((i, False, "Empty"))
        return slots
    
    def reset_game(self):
        """Reset to initial state"""
        self.state = GameState()
        # Remove autosave
        (self.SAVE_DIR / "autosave.json").unlink(missing_ok=True)


# =============================================================================
# TEXT UI
# =============================================================================

class TextUI:
    """Simple text-based interface"""
    
    def __init__(self, engine: GameEngine):
        self.engine = engine
    
    def print_location(self):
        """Print current location with character dialogue and riddle"""
        loc = self.engine.get_current_location()
        if not loc:
            print("Error: Location not found!")
            return
        
        char_name, char_dialogue = self.engine.location_character.get(loc.id, (None, None))
        
        print(f"\n{'='*60}")
        print(f":: {loc.name.upper()} ::")
        print(f"{'='*60}")
        print(loc.description)
        
        if char_name and char_dialogue:
            print(f'\n"{char_dialogue}"')
            print(f"   - {char_name}")
        
        riddle = self.engine.get_current_riddle()
        if riddle:
            self.print_riddle(riddle)
            return True
        else:
            print("\nYou've solved all riddles here.")
            return False
    
    def print_riddle(self, riddle: Riddle):
        """Print a riddle with answer options"""
        print(f"\n{'-'*60}")
        print(f"[Riddle: {riddle.language}]")
        print(f"Clue: {riddle.clue}")
        print(f"{riddle.text}")
        print(f"{'-'*60}")
        
        answers = [riddle.answer] + riddle.wrong_answers
        random.shuffle(answers)
        
        print("\nAnswer choices:")
        for i, answer in enumerate(answers, 1):
            print(f"  [{i}] {answer}")
        
        return riddle.id, answers
    
    def print_result(self, is_correct: bool, riddle: Riddle, next_loc: Optional[str]) -> Optional[str]:
        """Print result of answer attempt. Returns next action or None."""
        print(f"\n{'='*60}")
        
        if is_correct:
            print("✓ CORRECT!")
            print(f"The answer is: {riddle.answer}")
            print(f"\n{riddle.explanation}")
            
            if riddle.item:
                print(f"\nYou collected: {riddle.item}")
            
            if next_loc:
                loc = self.engine.get_location(next_loc)
                if loc:
                    if next_loc == self.engine.state.current_location:
                        print("\n[1] Look for more clues here")
                    else:
                        print(f"\n[1] Continue to {loc.name}")
                else:
                    print("\n[1] Continue investigating")
            else:
                print("\n[1] Look for more clues")
            
            print("[2] Stay here")
            print("[m] Open menu")
            
            choice = input("\nChoose: ").strip().lower()
            
            if choice == "1":
                if next_loc:
                    self.engine.move_to_location(next_loc)
                else:
                    # Go to random location with unsolved riddles
                    loc = self.engine.get_random_location()
                    if loc:
                        self.engine.move_to_location(loc.id)
                return "location"
            elif choice == "2":
                # Stay here - do nothing, will re-show same location
                return "location"
            elif choice == "m":
                return "menu"
            else:
                return "location"  # Invalid choice, stay
        
        else:
            print("✗ WRONG!")
            print(f"You lose 1 Sanity point! (Sanity: {self.engine.state.sanity}/{self.engine.state.max_sanity})")
            print(f"\n[1] Try again")
            print(f"[2] Show hint")
            print(f"[m] Open menu")
            
            choice = input("\nChoose: ").strip().lower()
            
            if choice == "1":
                return "retry"
            elif choice == "2":
                print(f"\nHint: {riddle.hint}")
                input("\nPress Enter to continue...")
                return "retry"
            elif choice == "m":
                return "menu"
            else:
                return "retry"
        
        return None
    
    def print_ui(self):
        """Print game UI (sanity, score, inventory)"""
        sanity_icons = "".join(["♥" if i < self.engine.state.sanity else "♡" 
                               for i in range(self.engine.state.max_sanity)])
        inv = ", ".join(self.engine.state.inventory) if self.engine.state.inventory else "Empty"
        
        print(f"\n{'='*60}")
        print(f"SANITY: {sanity_icons} | SCORE: {self.engine.state.score} | INVENTORY: {inv}")
        print(f"{'='*60}\n")
    
    def print_game_over(self):
        """Print game over screen"""
        total_riddles = len(self.engine.riddles)
        total_items = len([r for r in self.engine.riddles if r.item])
        
        print(f"\n{'='*60}")
        print("          GAME OVER")
        print(f"{'='*60}")
        print("Volkov's men found you first.")
        print(f"\nRiddles solved: {len(self.engine.state.solved_riddles)}/{total_riddles}")
        print(f"Items collected: {len(self.engine.state.inventory)}/{total_items}")
        print(f"Final score: {self.engine.state.score}")
        print("\nThe Babel Society wins. For now.")
        
        input("\nPress Enter to continue...")
    
    def print_ending(self):
        """Print ending screen"""
        title, description = self.engine.get_ending()
        total_riddles = len(self.engine.riddles)
        total_items = len([r for r in self.engine.riddles if r.item])
        
        print(f"\n{'='*60}")
        print(f"          {title}")
        print(f"{'='*60}")
        print(description)
        print(f"\nRiddles solved: {len(self.engine.state.solved_riddles)}/{total_riddles}")
        print(f"Items collected: {len(self.engine.state.inventory)}/{total_items}")
        print(f"Sanity remaining: {self.engine.state.sanity}")
        print(f"Final score: {self.engine.state.score}")
        print("\nAll our words are connected.")
        
        input("\nPress Enter to continue...")
    
    def print_menu(self) -> str:
        """Print main menu. Returns action string."""
        print(f"\n{'='*60}")
        print("          SAVE / LOAD MENU")
        print(f"{'='*60}\n")
        
        slots = self.engine.get_save_slots()
        for i, exists, label in slots:
            print(f"Slot {i}: {label}")
        
        print("\n[1] Save Game")
        print("[2] Load Game")
        print("[3] Back to Game")
        print("[4] Main Menu")
        
        choice = input("\nChoose: ").strip()
        
        if choice == "1":
            return self.print_save_menu()
        elif choice == "2":
            return self.print_load_menu()
        elif choice == "3":
            return "back"
        elif choice == "4":
            return "main_menu"
        else:
            return "menu"  # Stay in menu
    
    def print_save_menu(self) -> str:
        """Print save slot selection. Returns action string."""
        print(f"\n{'='*60}")
        print("          SAVE TO SLOT")
        print(f"{'='*60}\n")
        
        for i in range(1, 4):
            print(f"[{i}] Slot {i}")
        
        print("\n[0] Back")
        
        choice = input("\nChoose slot: ").strip()
        if choice in ["1", "2", "3"]:
            self.engine.save_game(int(choice))
            print(f"\nGame saved to slot {choice}!")
            input("Press Enter to continue...")
            return "menu"
        else:
            return "menu"
    
    def print_load_menu(self) -> str:
        """Print load slot selection. Returns action string."""
        print(f"\n{'='*60}")
        print("          LOAD FROM SLOT")
        print(f"{'='*60}\n")
        
        slots = self.engine.get_save_slots()
        for i, exists, label in slots:
            print(f"[{i}] Slot {i}: {label}")
        
        print("\n[0] Back")
        
        choice = input("\nChoose slot: ").strip()
        if choice in ["1", "2", "3"]:
            if self.engine.load_game(int(choice)):
                print(f"\nGame loaded from slot {choice}!")
                input("Press Enter to continue...")
                return "loaded"
            else:
                print("\nNo save found in that slot!")
                input("Press Enter to continue...")
                return "menu"
        else:
            return "menu"
    
    def print_main_menu(self) -> str:
        """Print main menu. Returns action string."""
        print(f"\n{'='*60}")
        print("   NOIR LANGUAGE RIDDLES")
        print("   The Babel Conspiracy")
        print(f"{'='*60}\n")
        print("Berlin, 1947. A linguist has disappeared.")
        print("Solve etymological riddles to uncover the truth.")
        print("\n[1] New Game")
        print("[2] Continue")
        print("[3] Quit")
        
        choice = input("\nChoose: ").strip()
        return choice


# =============================================================================
# MAIN GAME LOOP
# =============================================================================

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def main():
    """Main game entry point"""
    engine = GameEngine()
    ui = TextUI(engine)
    
    # Main menu
    while True:
        clear_screen()
        choice = ui.print_main_menu()
        
        if choice == "1":
            engine.reset_game()
            engine.move_to_location("ClientOffice")
            break
        elif choice == "2":
            if engine.load_game(0):
                break
            else:
                print("\nNo saved game found!")
                input("Press Enter to continue...")
        elif choice == "3":
            print("\nGoodbye, detective.")
            return
    
    # Main game loop
    while True:
        clear_screen()
        ui.print_ui()
        has_riddle = ui.print_location()
        
        # Check for game over
        if engine.is_game_over():
            clear_screen()
            ui.print_ui()
            ui.print_game_over()
            engine.reset_game()
            engine.move_to_location("ClientOffice")
            continue
        
        # Check if all riddles solved
        if engine.all_riddles_solved():
            clear_screen()
            ui.print_ui()
            ui.print_ending()
            engine.reset_game()
            engine.move_to_location("ClientOffice")
            continue
        
        # If there's a riddle, show it and get answer
        if has_riddle:
            riddle = engine.get_current_riddle()
            if riddle:
                riddle_id, answers = ui.print_riddle(riddle)
                choice = input("\nYour answer (number or 'm' for menu): ").strip()
                
                if choice.lower() == "m":
                    action = ui.print_menu()
                    if action == "back":
                        continue
                    elif action == "loaded":
                        continue
                    elif action == "main_menu":
                        # Go back to main menu
                        return main()
                    else:
                        continue
                
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(answers):
                        selected = answers[idx]
                        is_correct, riddle_obj, next_loc = engine.check_answer(riddle_id, selected)
                        clear_screen()
                        ui.print_ui()
                        action = ui.print_result(is_correct, riddle_obj, next_loc)
                        
                        if action == "menu":
                            menu_action = ui.print_menu()
                            if menu_action == "back":
                                continue
                            elif menu_action == "loaded":
                                continue
                            elif menu_action == "main_menu":
                                return main()
                        # For "location" and "retry", continue the loop
                    else:
                        print("Invalid choice!")
                        input("Press Enter...")
                except ValueError:
                    print("Invalid input!")
                    input("Press Enter...")
        else:
            # No riddle - offer to explore
            print("\n[1] Look for more clues")
            print("[2] Open menu")
            choice = input("\nChoose: ").strip()
            
            if choice == "1":
                loc = engine.get_random_location()
                if loc:
                    engine.move_to_location(loc.id)
            elif choice == "2":
                action = ui.print_menu()
                if action == "loaded":
                    continue
                elif action == "main_menu":
                    return main()


if __name__ == "__main__":
    # Set up save directory
    save_dir = Path.home() / ".babel_conspiracy_saves"
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Run game
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye, detective.")
