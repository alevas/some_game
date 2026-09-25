#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
A polished text-based detective game about etymology

Run with: python main_polished.py

Features:
- 30+ linguistic riddles
- Noir ASCII art atmosphere
- Color formatting
- Clean navigation
"""

import json
import os
import random
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


# =============================================================================
# ANSI COLORS FOR TERMINAL
# =============================================================================

class Color:
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


# =============================================================================
# ASCII ART
# =============================================================================

ASCII_LOGO = r"""
   __   __        _   _                   _   _
   \ \ / /       | | | |                 | | | |
    \ V /___  ___ | |_| |__   ___  _ __  | |_| | __ _
     > </ _ \/ __|| __| '_ \ / _ \| '_ \ | __| |/ _` |
    / . \__/\__ \| |_| | | | (_) | | | || |_| | (_| |
   /_/\_\___|___/ \__|_| |_|\___/|_| |_| \__,_|\__,_|
"""

ASCII_DETECTIVE = r"""
      _____
     /     \
    | () () |
     \  ^  /
     | \_/ |
     |   |
     |___|
    /     \
   /       \
  |  LOAD  |
  |  CASE  |
   \_____/
"""

ASCII_COFFEE = r"""
      ( (
       ) )
   ........
   |      |]
   \      /
    `----'
"""

ASCII_BOOKS = r"""
    _____
   /     \
  | [][] |
  | [][] |
   \_____/
   |   |
   |___|
"""

ASCII_CHURCH = r"""
        /
       /
      /\____
     /  __ \
    /  /  \ \
   |  |   | |
   |__|   |__|
"""

ASCII_LIGHTBULB = r"""
     ___
    /   \
   |   |
    \___/
     / \
    /   \
"""


# =============================================================================
# DATA MODULE
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
    ascii_art: Optional[str] = None
    first_riddle: int = 1


# Game database - 30 riddles now!
RIDDLES = [
    # Original 10
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
           "All descend from Latin liber.", "Cafe", "Spanish Dictionary", 1),
    
    Riddle(4, "Russian", "etymology", "This Slavic word is передача (peredacha) meaning transmission. What English word shares Latin root 'trahere'?",
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
    
    Riddle(8, "English", "cognates", "This English word is mother in English, Mutter in German, μητέρα in Greek. What is it?",
           "mother | Mutter | μητέρα", "Mother", ["Sister", "Aunt"], "PIE root: *méh₂tēr",
           "All from PIE *méh₂tēr. Preserved across 4000+ years.", "Church", "Family Tree", 1),
    
    Riddle(9, "Spanish", "etymology", "This word is noche in Spanish. In Latin it was nox. What is it in English?",
           "noche | nox", "Night", ["Noon", "Noxious"], "It is the opposite of day.",
           "From Latin nox/noctis.", "Library", None, 1),
    
    Riddle(10, "Russian", "etymology", "This Russian word is водка (vodka). From вода (voda) meaning water. What is the connection?",
           "водка | вода", "Little water", ["Fire water", "Strong drink"], "Vodka is a diminutive.",
           "Vodka is the diminutive of вода (water).", "Cafe", "Vodka Bottle", 2),
    
    # New 20 riddles
    Riddle(11, "Latin", "etymology", "This Latin word 'lux' means light. What English word derives from it?",
           "lux", "Illuminate", ["Luxury", "Luck"], "Think of something that sheds light.",
           "From Latin lux = light. Illuminate, luminous, etc.", "Library", "Lantern", 2),
    
    Riddle(12, "French", "etymology", "In French, 'histoire' means history and story. What English word shares this root?",
           "histoire", "Story", ["Histogram", "Historical"], "From Latin historia.",
           "Both English 'story' and 'history' come from Latin historia.", "Archive", "History Book", 2),
    
    Riddle(13, "Greek", "etymology", "This Greek word φως (phos) means light. What English prefix means light?",
           "φως (phos)", "Photo", ["Phonics", "Photon"], "As in photography, photon.",
           "From Greek φώς (phos) = light.", "Library", "Photograph", 1),
    
    Riddle(14, "Sanskrit", "etymology", "The Sanskrit word 'danta' means tooth. What English word is related?",
           "danta", "Dental", ["Dentist", "Denture"], "From PIE *h₃dónts.",
           "Sanskrit दन्त (danta) and English 'tooth' are cognates.", "Archive", "Dental Mirror", 2),
    
    Riddle(15, "Old Norse", "etymology", "Old Norse 'skip' means ship. What English word comes from this?",
           "skip", "Ship", ["Skipper", "Skiff"], "Direct cognate.",
           "Old Norse influenced English heavily after Viking invasions.", "Archive", "Ship Model", 1),
    
    Riddle(16, "Arabic", "borrowings", "This Arabic word 'sukkar' means sugar. It entered English through which language?",
           "sukkar", "Persian", ["Latin", "Greek", "Spanish"], "Trade routes carried it West.",
           "Arabic → Persian → Medieval Latin → English.", "Cafe", "Sugar Cube", 2),
    
    Riddle(17, "Hebrew", "etymology", "The Hebrew word 'shalom' means peace. What does it literally mean?",
           "שלום", "Wholeness", ["Hello", "Peace"], "Root means completeness.",
           "Peace as wholeness, not just absence of conflict.", "Church", "Peace Symbol", 2),
    
    Riddle(18, "Japanese", "borrowings", "The Japanese word 'pan' (パン) for bread comes from which language?",
           "パン", "Portuguese", ["Chinese", "English", "French"], "From Portuguese pão.",
           "Portuguese traders brought bread to Japan in the 16th century.", "Cafe", "Portuguese Bread", 1),
    
    Riddle(19, "Finnish", "etymology", "Finnish 'kala' means fish. It's unrelated to most European words. Why?",
           "kala", "Uralic language", ["Indo-European", "Slavic", "Germanic"], "Finnish is not Indo-European.",
           "Finnish belongs to the Uralic language family, unrelated to most European languages.", "Archive", "Language Map", 2),
    
    Riddle(20, "Egyptian", "etymology", "The ancient Egyptian word for 'river' was 'iteru'. What modern word derives from it?",
           "iteru", "Nile", ["Water", "Flow", "River"], "The Nile was 'The River' par excellence.",
           "From Egyptian 𓇋𓏏𓁹 (iteru) = river, specifically the Nile.", "Library", "Papyrus Scroll", 3),
    
    Riddle(21, "Greek", "cognates", "Greek 'hydor' (ὕδωρ) means water. What English word contains this root?",
           "ὕδωρ", "Hydroelectric", ["Hydrogen", "Dehydrated"], "Think of water-related terms.",
           "Hydro- prefix means water in English.", "Library", None, 1),
    
    Riddle(22, "German", "etymology", "German 'Buchstabe' means letter (of alphabet). What does it literally mean?",
           "Buchstabe", "Book staff", ["Book letter", "Letter book"], "Buch = book, Stab = staff/stick.",
           "Originally referred to letters carved on sticks used as bookmarks.", "Archive", "Quill Pen", 2),
    
    Riddle(23, "Spanish", "false friends", "In Spanish, 'embarazada' does NOT mean embarrassed. What does it mean?",
           "embarazada", "Pregnant", ["Embarrassed", "Sad", "Happy"], "Classic false friend!",
           "Embarazada = pregnant. 'Avergonzada' = embarrassed.", "Church", None, 1),
    
    Riddle(24, "Russian", "etymology", "Russian 'spasibo' (thank you) comes from what religious phrase?",
           "spasibo", "God save", ["Save me", "Thank God", "Spas"], "Spasi Bog = God save (you).",
           "From Old Church Slavonic 'spasi bog' = God save (you).", "Church", "Religious Text", 2),
    
    Riddle(25, "Greek", "etymology", "Greek 'astron' (ἄστρον) means star. What English word contains this?",
           "ἄστρον", "Astronomy", ["Asteroid", "Disaster"], "Study of stars.",
           "Astronomy, astrology, astronaut, asteroid all from Greek ἄστρον.", "Archive", None, 1),
    
    Riddle(26, "Latin", "etymology", "Latin 'specere' means to look. What English words come from it?",
           "specere", "Spectacle", ["Inspect", "Respect", "All of these"], "Think of words with 'spect'.",
           "Specere → inspect, respect, suspect, specimen, spectacle, perspective, etc.", "Library", "Magnifying Glass", 2),
    
    Riddle(27, "French", "false friends", "In French, 'actuellement' does NOT mean 'currently'. What does it mean?",
           "actuellement", "Actually", ["Now", "Currently", "In fact"], "Classical false friend.",
           "Actuellement = actually/in fact. 'Actuellement' does NOT mean 'currently' (that's 'actuellement' in a different sense, but still not).", "Cafe", None, 2),
    
    Riddle(28, "Arvanitika", "etymology", "In Arvanitika, 'gjukë' means tongue. What is the Albanian word?",
           "gjukë", "Gjuha", ["Lenguaje", "Zungë", "Jezik"], "Direct cognate.",
           "Shows the Albanian roots of Arvanitika.", "Church", None, 2),
    
    Riddle(29, "PIE", "etymology", "PIE root *treyes means three. What words in English, Greek, and Latin come from this?",
           "*treyes", "Three / Три / Tres", ["Two", "Four", "Five"], "Direct cognates.",
           "English three, Greek τρία (tria), Latin tres, all from PIE *treyes.", "Library", None, 2),
    
    Riddle(30, "Hindi", "etymology", "The Hindi word 'namaste' combines 'namas' (bow) and what?",
           "namaste", "To you", ["Hello", "Goodbye", "Peace"], "Namah = bow, te = to you.",
           "From Sanskrit namas (bow/reverence) + te (to you).", "Archive", "Namaste Symbol", 2),
]

LOCATIONS = {
    "ClientOffice": Location(
        "ClientOffice", "Weber's Private Office",
        "The dim glow of a desk lamp illuminates stacks of case files. Berlin, 1947. "
        "A typewriter sits silent, waiting. On the desk, a note in Greek catches your eye. "
        "Elena Weber, a linguist, has disappeared. The only clue: a trail of etymological breadcrumbs.",
        ASCII_DETECTIVE, 1
    ),
    
    "Library": Location(
        "Library", "Staatsbibliothek",
        "Tall shelves stretch into shadow. Ancient manuscripts in Greek, German, Latin. "
        "The air smells of parchment and secrets. A librarian eyes you suspiciously.",
        ASCII_BOOKS, 3
    ),
    
    "Cafe": Location(
        "Cafe", "Café Mozart",
        "The scent of strong coffee and sugar hangs in the air. Intellectuals and spies "
        "share tables in the dim light. A waiter polishes a glass, watching.",
        ASCII_COFFEE, 2
    ),
    
    "Church": Location(
        "Church", "St. Nicholas Church",
        "Candlelight flickers against stone walls. The sacristan moves silently between shadows. "
        "Old texts in Greek and Latin line the shelves. The Babel Society has left its mark here.",
        ASCII_CHURCH, 6
    ),
    
    "Archive": Location(
        "Archive", "Secret Archive",
        "Files upon files of linguistic research. The Babel Society's true work is here. "
        "Volkov, their leader, has been one step ahead. But you're closing in.",
        None, 4
    ),
}

LOCATION_CHARACTER = {
    "ClientOffice": ("Elena Weber", "I need your help, detective. The Babel Society is real."),
    "Library": ("Herr Schmidt", "She was here last week. Asking about Proto-Indo-European again."),
    "Cafe": ("Karl", "The men in dark suits come in every Tuesday. Always order the same thing."),
    "Church": ("Father Thomas", "The church has secrets, detective. Some older than the building itself."),
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
        
        # Find riddle that points to this location
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
        locs_with_riddles = []
        for loc_id, loc in self.locations.items():
            for r in self.riddles:
                if r.next_location == loc_id and r.id not in self.state.solved_riddles:
                    locs_with_riddles.append(loc_id)
                    break
        
        if locs_with_riddles:
            return self.locations.get(random.choice(locs_with_riddles))
        
        return random.choice(list(self.locations.values()))
    
    def get_locations_with_riddles(self) -> List[tuple]:
        """Get list of (loc_id, loc_name) that have unsolved riddles"""
        result = []
        for loc_id, loc in self.locations.items():
            for r in self.riddles:
                if r.next_location == loc_id and r.id not in self.state.solved_riddles:
                    result.append((loc_id, loc.name))
                    break
        return result
    
    def get_ending(self) -> tuple:
        """Determine ending based on progress"""
        total_riddles = len(self.riddles)
        total_items = len([r for r in self.riddles if r.item])
        solved = len(self.state.solved_riddles)
        collected = len(self.state.inventory)
        
        if solved >= total_riddles and collected >= total_items:
            return ("The Truth Revealed", 
                   "With all clues, you expose the Babel Society to the world.")
        elif solved >= total_riddles:
            return ("Partial Victory", 
                   "You solve the case and recover the manuscript, but Volkov escapes.")
        elif solved >= total_riddles / 2:
            return ("A Lead, Not a Victory", 
                   "You gather evidence to close Elena's case, but the Babel Society remains.")
        else:
            return ("Case Closed", 
                   "You solved the case, but Volkov escaped with the manuscript.")
    
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
        
        with open(self.SAVE_DIR / "autosave.json", 'w') as f:
            json.dump(state_dict, f, indent=2)
    
    def load_game(self, slot: int = 0) -> bool:
        """Load game from file"""
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
        (self.SAVE_DIR / "autosave.json").unlink(missing_ok=True)


# =============================================================================
# TEXT UI WITH COLORS
# =============================================================================

class TextUI:
    """Simple text-based interface with colors and ASCII art"""
    
    def __init__(self, engine: GameEngine):
        self.engine = engine
    
    def c(self, text: str, color: str = None) -> str:
        """Colorize text"""
        if color:
            return f"{getattr(Color, color.upper(), '')}{text}{Color.RESET}"
        return text
    
    def print_header(self):
        """Print game header with logo"""
        print(f"\n{self.c(ASCII_LOGO, 'cyan')}")
        print(f"{self.c('='*60, 'yellow')}")
        print(f"{self.c('  NOIR LANGUAGE RIDDLES', 'bright_white')}")
        print(f"{self.c('  The Babel Conspiracy', 'bright_white')}")
        print(f"{self.c('='*60, 'yellow')}\n")
    
    def print_location(self):
        """Print current location with character dialogue and riddle"""
        loc = self.engine.get_current_location()
        if not loc:
            print(self.c("Error: Location not found!", "red"))
            return
        
        # Print location header with ASCII art if available
        print(f"\n{self.c('='*60, 'yellow')}")
        if loc.ascii_art:
            print(f"{self.c(loc.ascii_art, 'bright_black')}")
        print(f"{self.c(f':: {loc.name.upper()} ::', 'bright_yellow')}")
        print(f"{self.c('='*60, 'yellow')}")
        print(self.c(loc.description, "white"))
        
        # Character dialogue
        char_name, char_dialogue = self.engine.location_character.get(loc.id, (None, None))
        if char_name and char_dialogue:
            print(f'\n{self.c(f"\"{char_dialogue}\"", "italic")}')
            print(f'{self.c(f"   - {char_name}", "bright_black")}')
        
        riddle = self.engine.get_current_riddle()
        if riddle:
            return riddle
        else:
            print(f"\n{self.c('You have solved all riddles here.', 'bright_black')}")
            return None
    
    def print_riddle(self, riddle: Riddle):
        """Print a riddle with answer options"""
        print(f"\n{self.c('-'*60, 'yellow')}")
        print(f"{self.c(f'[Riddle: {riddle.language}]', 'bright_cyan')}")
        print(f"{self.c(f'Clue: {riddle.clue}', 'bright_magenta')}")
        print(f"{self.c(riddle.text, 'italic')}")
        print(f"{self.c('-'*60, 'yellow')}")
        
        answers = [riddle.answer] + riddle.wrong_answers
        random.shuffle(answers)
        
        print(f"\n{self.c('Answer choices:', 'bright_white')}")
        for i, answer in enumerate(answers, 1):
            print(f"  {self.c(f'[{i}]', 'yellow')} {answer}")
        
        print(f"\n{self.c('[m] Open menu', 'bright_black')}")
        
        return riddle.id, answers
    
    def print_result(self, is_correct: bool, riddle: Riddle, next_loc: Optional[str]) -> Optional[str]:
        """Print result of answer attempt. Returns next action."""
        print(f"\n{self.c('='*60, 'yellow')}")
        
        if is_correct:
            print(f"{self.c('✓ CORRECT!', 'green')}")
            print(f"{self.c(f'The answer is: {riddle.answer}', 'bright_green')}")
            print(f"\n{self.c(riddle.explanation, 'white')}")
            
            if riddle.item:
                print(f"\n{self.c(f'You collected: {riddle.item}', 'bright_green')}")
            
            if next_loc:
                loc = self.engine.get_location(next_loc)
                if loc:
                    if next_loc == self.engine.state.current_location:
                        print(f"\n{self.c('[1] Look for more clues here', 'yellow')}")
                        print(f"{self.c('[m] Open menu', 'bright_black')}")
                        choice = input("\nChoose: ").strip().lower()
                        if choice == "1":
                            return "location"
                        elif choice == "m":
                            return "menu"
                        else:
                            return "location"
                    else:
                        print(f"\n{self.c(f'[1] Continue to {loc.name}', 'yellow')}")
                        print(f"{self.c('[2] Stay here', 'yellow')}")
                        print(f"{self.c('[m] Open menu', 'bright_black')}")
                        choice = input("\nChoose: ").strip().lower()
                        if choice == "1":
                            self.engine.move_to_location(next_loc)
                            return "location"
                        elif choice == "2":
                            return "location"
                        elif choice == "m":
                            return "menu"
                        else:
                            return "location"
                else:
                    print(f"\n{self.c('[1] Continue investigating', 'yellow')}")
                    print(f"{self.c('[2] Stay here', 'yellow')}")
                    print(f"{self.c('[m] Open menu', 'bright_black')}")
                    choice = input("\nChoose: ").strip().lower()
                    if choice == "1":
                        loc = self.engine.get_random_location()
                        if loc:
                            self.engine.move_to_location(loc.id)
                        return "location"
                    elif choice == "2":
                        return "location"
                    elif choice == "m":
                        return "menu"
                    else:
                        return "location"
            else:
                print(f"\n{self.c('[1] Look for more clues', 'yellow')}")
                print(f"{self.c('[2] Stay here', 'yellow')}")
                print(f"{self.c('[m] Open menu', 'bright_black')}")
                choice = input("\nChoose: ").strip().lower()
                if choice == "1":
                    loc = self.engine.get_random_location()
                    if loc:
                        self.engine.move_to_location(loc.id)
                    return "location"
                elif choice == "2":
                    return "location"
                elif choice == "m":
                    return "menu"
                else:
                    return "location"
        
        else:
            print(f"{self.c('✗ WRONG!', 'red')}")
            print(f"{self.c(f'You lose 1 Sanity point!', 'red')}")
            sanity_str = f"{self.engine.state.sanity}/{self.engine.state.max_sanity}"
            print(f"{self.c(f'Sanity: {sanity_str}', 'bright_red')}")
            
            print(f"\n{self.c('[1] Try again', 'yellow')}")
            print(f"{self.c('[2] Show hint', 'yellow')}")
            print(f"{self.c('[m] Open menu', 'bright_black')}")
            
            choice = input("\nChoose: ").strip().lower()
            
            if choice == "1":
                return "retry"
            elif choice == "2":
                print(f"\n{self.c(f'Hint: {riddle.hint}', 'bright_magenta')}")
                input(f"\n{self.c('Press Enter to continue...', 'bright_black')}")
                return "retry"
            elif choice == "m":
                return "menu"
            else:
                return "retry"
        
        return None
    
    def print_ui(self):
        """Print game UI (sanity, score, inventory)"""
        sanity_icons = "".join([self.c("♥", "red") if i < self.engine.state.sanity else self.c("♡", "bright_black") 
                               for i in range(self.engine.state.max_sanity)])
        inv = self.c(", ", "bright_black").join(self.engine.state.inventory) if self.engine.state.inventory else self.c("Empty", "bright_black")
        
        print(f"\n{self.c('='*60, 'yellow')}")
        print(f"{self.c('SANITY: ', 'bright_white')}{sanity_icons} {self.c(f'| SCORE: {self.engine.state.score}', 'bright_white')} {self.c(f'| INVENTORY: {inv}', 'bright_white')}")
        print(f"{self.c('='*60, 'yellow')}\n")
    
    def print_game_over(self):
        """Print game over screen"""
        total_riddles = len(self.engine.riddles)
        total_items = len([r for r in self.engine.riddles if r.item])
        
        print(f"\n{self.c('='*60, 'red')}")
        print(f"{self.c('          GAME OVER', 'bright_red')}")
        print(f"{self.c('='*60, 'red')}")
        print(f"{self.c('Volkov\'s men found you first.', 'red')}")
        print(f"\n{self.c(f'Riddles solved: {len(self.engine.state.solved_riddles)}/{total_riddles}', 'white')}")
        print(f"{self.c(f'Items collected: {len(self.engine.state.inventory)}/{total_items}', 'white')}")
        print(f"{self.c(f'Final score: {self.engine.state.score}', 'white')}")
        print(f"\n{self.c('The Babel Society wins. For now.', 'bright_black')}")
        
        input(f"\n{self.c('Press Enter to continue...', 'bright_black')}")
    
    def print_ending(self):
        """Print ending screen"""
        title, description = self.engine.get_ending()
        total_riddles = len(self.engine.riddles)
        total_items = len([r for r in self.engine.riddles if r.item])
        
        print(f"\n{self.c('='*60, 'green')}")
        print(f"{self.c(f'          {title}', 'bright_green')}")
        print(f"{self.c('='*60, 'green')}")
        print(f"{self.c(description, 'green')}")
        print(f"\n{self.c(f'Riddles solved: {len(self.engine.state.solved_riddles)}/{total_riddles}', 'white')}")
        print(f"{self.c(f'Items collected: {len(self.engine.state.inventory)}/{total_items}', 'white')}")
        print(f"{self.c(f'Sanity remaining: {self.engine.state.sanity}', 'white')}")
        print(f"{self.c(f'Final score: {self.engine.state.score}', 'white')}")
        print(f"\n{self.c('All our words are connected.', 'italic')}")
        
        input(f"\n{self.c('Press Enter to continue...', 'bright_black')}")
    
    def print_location_menu(self, locations: List[tuple]) -> Optional[str]:
        """Print menu to select location. Returns loc_id or None."""
        print(f"\n{self.c('='*60, 'yellow')}")
        print(f"{self.c('          SELECT DESTINATION', 'bright_white')}")
        print(f"{self.c('='*60, 'yellow')}\n")
        
        for idx, (loc_id, loc_name) in enumerate(locations, 1):
            print(f"{self.c(f'[{idx}]', 'yellow')} {loc_name}")
        
        print(f"\n{self.c('[0] Cancel', 'yellow')}")
        
        choice = input(f"\n{self.c('Choose: ', 'bright_white')}").strip()
        
        if choice == "0":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(locations):
                return locations[idx][0]
        except ValueError:
            pass
        return None
    
    def print_menu(self) -> str:
        """Print save/load menu. Returns action string."""
        print(f"\n{self.c('='*60, 'yellow')}")
        print(f"{self.c('          SAVE / LOAD MENU', 'bright_white')}")
        print(f"{self.c('='*60, 'yellow')}\n")
        
        slots = self.engine.get_save_slots()
        for i, exists, label in slots:
            status = self.c(label, "green" if exists else "bright_black")
            print(f"{self.c(f'Slot {i}:', 'yellow')} {status}")
        
        print(f"\n{self.c('[1] Save Game', 'yellow')}")
        print(f"{self.c('[2] Load Game', 'yellow')}")
        print(f"{self.c('[3] Back to Game', 'yellow')}")
        print(f"{self.c('[4] Main Menu', 'yellow')}")
        
        choice = input(f"\n{self.c('Choose: ', 'bright_white')}").strip()
        
        if choice == "1":
            return self.print_save_menu()
        elif choice == "2":
            return self.print_load_menu()
        elif choice == "3":
            return "back"
        elif choice == "4":
            return "main_menu"
        else:
            return "menu"
    
    def print_save_menu(self) -> str:
        """Print save slot selection. Returns action string."""
        print(f"\n{self.c('='*60, 'yellow')}")
        print(f"{self.c('          SAVE TO SLOT', 'bright_white')}")
        print(f"{self.c('='*60, 'yellow')}\n")
        
        for i in range(1, 4):
            print(f"{self.c(f'[{i}] Slot {i}', 'yellow')}")
        
        print(f"\n{self.c('[0] Back', 'yellow')}")
        
        choice = input(f"\n{self.c('Choose slot: ', 'bright_white')}").strip()
        if choice in ["1", "2", "3"]:
            self.engine.save_game(int(choice))
            print(f"\n{self.c(f'Game saved to slot {choice}!', 'green')}")
            input(f"{self.c('Press Enter to continue...', 'bright_black')}")
            return "menu"
        else:
            return "menu"
    
    def print_load_menu(self) -> str:
        """Print load slot selection. Returns action string."""
        print(f"\n{self.c('='*60, 'yellow')}")
        print(f"{self.c('          LOAD FROM SLOT', 'bright_white')}")
        print(f"{self.c('='*60, 'yellow')}\n")
        
        slots = self.engine.get_save_slots()
        for i, exists, label in slots:
            status = self.c(label, "green" if exists else "bright_black")
            print(f"{self.c(f'[{i}] Slot {i}:', 'yellow')} {status}")
        
        print(f"\n{self.c('[0] Back', 'yellow')}")
        
        choice = input(f"\n{self.c('Choose slot: ', 'bright_white')}").strip()
        if choice in ["1", "2", "3"]:
            if self.engine.load_game(int(choice)):
                print(f"\n{self.c(f'Game loaded from slot {choice}!', 'green')}")
                input(f"{self.c('Press Enter to continue...', 'bright_black')}")
                return "loaded"
            else:
                print(f"\n{self.c('No save found in that slot!', 'red')}")
                input(f"{self.c('Press Enter to continue...', 'bright_black')}")
                return "menu"
        else:
            return "menu"
    
    def print_main_menu(self) -> str:
        """Print main menu. Returns action string."""
        print(f"\n{self.c(ASCII_LOGO, 'cyan')}")
        print(f"{self.c('='*60, 'yellow')}")
        print(f"{self.c('  NOIR LANGUAGE RIDDLES', 'bright_white')}")
        print(f"{self.c('  The Babel Conspiracy', 'bright_white')}")
        print(f"{self.c('='*60, 'yellow')}\n")
        print(f"{self.c('Berlin, 1947. A linguist has disappeared.', 'bright_black')}")
        print(f"{self.c('Solve etymological riddles to uncover the truth.', 'bright_black')}")
        print(f"\n{self.c('[1] New Game', 'yellow')}")
        print(f"{self.c('[2] Continue', 'yellow')}")
        print(f"{self.c('[3] Quit', 'yellow')}")
        
        choice = input(f"\n{self.c('Choose: ', 'bright_white')}").strip()
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
                print(f"\n{ui.c('No saved game found!', 'red')}")
                input(f"{ui.c('Press Enter to continue...', 'bright_black')}")
        elif choice == "3":
            print(f"\n{ui.c('Goodbye, detective.', 'bright_black')}")
            return
    
    # Main game loop
    while True:
        clear_screen()
        ui.print_header()
        ui.print_ui()
        riddle = ui.print_location()
        
        # Check for game over
        if engine.is_game_over():
            clear_screen()
            ui.print_header()
            ui.print_ui()
            ui.print_game_over()
            engine.reset_game()
            engine.move_to_location("ClientOffice")
            continue
        
        # Check if all riddles solved
        if engine.all_riddles_solved():
            clear_screen()
            ui.print_header()
            ui.print_ui()
            ui.print_ending()
            engine.reset_game()
            engine.move_to_location("ClientOffice")
            continue
        
        # If there's a riddle, show it and get answer
        if riddle:
            riddle_id, answers = ui.print_riddle(riddle)
            choice = input(f"\n{ui.c('Your answer (number or m for menu): ', 'bright_white')}").strip()
            
            if choice.lower() == "m":
                action = ui.print_menu()
                if action == "back":
                    continue
                elif action == "loaded":
                    continue
                elif action == "main_menu":
                    return main()
                else:
                    continue
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(answers):
                    selected = answers[idx]
                    is_correct, riddle_obj, next_loc = engine.check_answer(riddle_id, selected)
                    clear_screen()
                    ui.print_header()
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
                else:
                    print(f"\n{ui.c('Invalid choice!', 'red')}")
                    input(f"{ui.c('Press Enter...', 'bright_black')}")
            except ValueError:
                print(f"\n{ui.c('Invalid input!', 'red')}")
                input(f"{ui.c('Press Enter...', 'bright_black')}")
        else:
            # No riddle - offer to explore
            print(f"\n{ui.c('[1] Look for more clues', 'yellow')}")
            print(f"{ui.c('[2] Open menu', 'yellow')}")
            choice = input(f"\n{ui.c('Choose: ', 'bright_white')}").strip()
            
            if choice == "1":
                print(f"\n{ui.c('You look around, but only find trails of presense that once was.', 'bright_black')}")
                print(f"{ui.c('Better move on.', 'bright_black')}")
                input(f"\n{ui.c('Press Enter to continue...', 'bright_black')}")
                
                locs_with_riddles = engine.get_locations_with_riddles()
                if len(locs_with_riddles) == 1:
                    # Only one location has riddles - go there
                    engine.move_to_location(locs_with_riddles[0][0])
                elif len(locs_with_riddles) > 1:
                    # Multiple locations - let player choose
                    action = ui.print_location_menu(locs_with_riddles)
                    if action:
                        engine.move_to_location(action)
                else:
                    # No locations have riddles - random
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
