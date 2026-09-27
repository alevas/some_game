"""
Noir Language Riddles: The Babel Conspiracy
Game data and engine, shared by the console UI (main_polished.py) and the
full-screen ASCII UI (tui.py). Nothing in here prints or reads input.

The case is a chain of locations. Each location holds its own riddles plus one
"lead" riddle. The lead shows up once enough of the location's riddles are
solved, and solving it unlocks the next location. You can move on early and
come back later, but evidence you skip counts against you at the end.
"""

import json
import random
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict


# =============================================================================
# DATA
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
    item: Optional[str] = None
    difficulty: int = 1


@dataclass
class Location:
    id: str
    name: str
    description: str
    character: str
    greeting: str           # what the character says while you investigate
    riddle_ids: List[int]   # asked in this order
    lead_riddle: Optional[int] = None
    leads_to: Optional[str] = None
    lead_after: int = 0     # riddles to solve here before the lead appears
    lead_text: str = ""     # story beat when the lead is solved
    done_text: str = ""     # what the character says once the place is exhausted


RIDDLES = [
    Riddle(1, "Greek", "location", "In Greek, it is βιβλίο (vivlio). Where would you go to borrow one?",
           "βιβλίο", "Library", ["University", "Bookstore"],
           "Think where books are collected and borrowed.",
           "Greek βιβλίο = book; a library is a βιβλιοθήκη ('book case'). English 'library' took the Latin route: liber (book) → librarium.", "Case File", 1),

    Riddle(2, "German", "location", "In German, linguists met where Kaffee flows. Where?",
           "Linguisten trafen sich, wo Kaffee fließt", "Café Mozart",
           ["The university", "A beer hall"], "Not a pub. Somewhere with coffee.",
           "Kaffee = coffee. Berlin intellectuals met in cafes.", "Sugar Packet", 1),

    Riddle(3, "Spanish", "etymology", "This word is libro in Spanish, livre in French, Buch in German. What is it in English?",
           "libro | livre | Buch", "Book", ["Library", "Novel"],
           "All three words mean the same thing.",
           "Libro and livre come from Latin liber (originally 'inner bark'). Buch is Germanic, a sibling of English 'book'.", "Spanish Dictionary", 1),

    Riddle(4, "Russian", "cognates", "Russian новый (novyi), Latin novus, Greek νέος (neos). What is it in English?",
           "новый | novus | νέος", "New", ["Noon", "Nine"],
           "The opposite of old.",
           "All from PIE *néwos. 'Nine' looks close but comes from a different root, *h₁néwn̥.", "Cipher Wheel", 2),

    Riddle(5, "Arvanitika", "false friends", "In Arvanitika, it is buke. In Greek, it is ψωμί. What is it in English?",
           "buke | ψωμί", "Bread", ["Book", "Brick"], "It is a staple food.",
           "Arvanitika buke and Greek ψωμί both mean bread. It only looks like 'book'.", "Arvanitika Notes", 2),

    Riddle(6, "Greek", "etymology", "In Greek, it is πατήρ (pater). In German, it is Vater. What is it in English?",
           "πατήρ | Vater", "Father", ["Mother", "Brother"], "PIE root: *ph₂tḗr",
           "All descend from Proto-Indo-European *ph₂tḗr. Germanic turned p into f/v.", None, 1),

    Riddle(7, "German", "false friends", "In German, Gift does not mean a present. What does it mean?",
           "Gift", "Poison", ["Gift", "Present"], "In English, gift is positive.",
           "German Gift once meant 'something given', a dose, and narrowed to 'poison'. English kept the original sense.", None, 1),

    Riddle(8, "German", "cognates", "It is Mutter in German, μητέρα (mitera) in Greek, mater in Latin. What is it in English?",
           "Mutter | μητέρα | mater", "Mother", ["Sister", "Aunt"], "PIE root: *méh₂tēr",
           "All from PIE *méh₂tēr. Preserved across 4000+ years.", "Family Tree", 1),

    Riddle(9, "Spanish", "etymology", "This word is noche in Spanish. In Latin it was nox. What is it in English?",
           "noche | nox", "Night", ["Noon", "Noxious"], "It is the opposite of day.",
           "Latin nox, noctis and English night are cognates from PIE *nókʷts. 'Noxious' comes from noxa (harm).", None, 1),

    Riddle(10, "Russian", "etymology", "This Russian word is водка (vodka). From вода (voda) meaning water. What is the connection?",
           "водка | вода", "Little water", ["Fire water", "Strong drink"], "Vodka is a diminutive.",
           "Vodka is the diminutive of вода (water).", "Vodka Bottle", 2),

    # New 20 riddles
    Riddle(11, "Latin", "etymology", "This Latin word 'lux' (genitive lucis) means light. What English word derives from it?",
           "lux", "Lucid", ["Luxury", "Luck"], "Think of a clear, bright mind.",
           "Lux, lucis → lucid, elucidate, translucent. 'Luxury' is a trap: it comes from luxus (excess).", "Lantern", 2),

    Riddle(12, "French", "etymology", "In French, 'histoire' means both history and story. What everyday English word shares its root?",
           "histoire", "Story", ["Histogram", "Hysteria"], "From Latin historia.",
           "Story is a clipped form of Old French estoire, from Latin historia. Histogram (histos, 'mast') and hysteria (hystera, 'womb') only look similar.", "History Book", 2),

    Riddle(13, "Greek", "etymology", "This Greek word φως (phos) means light. What English prefix means light?",
           "φως (phos)", "Photo-", ["Phono-", "Philo-"], "As in photography.",
           "From Greek φῶς, φωτός (phos, photos) = light. Phono- is sound, philo- is love.", "Photograph", 1),

    Riddle(14, "Sanskrit", "etymology", "The Sanskrit word 'danta' means tooth. What English word is related?",
           "danta", "Dental", ["Dandy", "Dance"], "Think of your dentist.",
           "Sanskrit दन्त (danta) and Latin dens, dentis (→ dental) share PIE *h₃dónts, which also became English 'tooth'.", "Dental Mirror", 2),

    Riddle(15, "Old Norse", "borrowings", "Old Norse 'skyrta' meant shirt. English kept its native 'shirt', but borrowed the Norse word too. As what?",
           "skyrta", "Skirt", ["Short", "Scarf"], "Vikings kept the hard 'sk' sound.",
           "Shirt (Old English scyrte) and skirt (Old Norse skyrta) are the same word. The Vikings left English doublets like this.", "Viking Brooch", 1),

    Riddle(16, "Arabic", "borrowings", "This Arabic word 'sukkar' means sugar. Through which language did it reach English?",
           "sukkar", "Old French", ["Persian", "Greek"], "It came to England via the Mediterranean and the Normans' language.",
           "Sanskrit śarkarā → Persian shakar → Arabic sukkar → Medieval Latin succarum / Old French sucre → English sugar.", "Sugar Cube", 2),

    Riddle(17, "Hebrew", "etymology", "The Hebrew word 'shalom' means peace. What does its root literally mean?",
           "שלום", "Wholeness", ["Hello", "Victory"], "Root means completeness.",
           "Peace as wholeness, not just absence of conflict.", "Peace Symbol", 2),

    Riddle(18, "Japanese", "borrowings", "The Japanese word 'pan' (パン) for bread comes from which language?",
           "パン", "Portuguese", ["Chinese", "English", "French"], "From Portuguese pão.",
           "Portuguese traders brought bread to Japan in the 16th century.", "Portuguese Bread", 1),

    Riddle(19, "Finnish", "etymology", "Finnish 'kala' means fish. It's unrelated to most European words. Why?",
           "kala", "Uralic language", ["Indo-European", "Slavic", "Germanic"], "Finnish is not Indo-European.",
           "Finnish belongs to the Uralic family. Its cousin is Hungarian hal (fish), not English or German.", "Language Map", 2),

    Riddle(20, "Egyptian", "etymology", "Ancient Egyptians called the Nile 'iteru', simply 'the river'. From which language does the name 'Nile' come?",
           "iteru", "Greek", ["Egyptian", "Arabic"], "Herodotus wrote about it.",
           "'Nile' comes from Greek Νεῖλος (Neilos), of uncertain origin. The Egyptians just said iteru.", "Papyrus Scroll", 3),

    Riddle(21, "Greek", "cognates", "Greek ὕδωρ (hydor) means water. Which of these words does NOT contain this root?",
           "ὕδωρ", "Hybrid", ["Hydrogen", "Dehydrated"], "Two of these are wet.",
           "Hydrogen ('water-maker') and dehydrated contain hydor. Hybrid comes from Latin hybrida, 'mongrel'.", None, 1),

    Riddle(22, "German", "etymology", "German 'Buchstabe' means letter (of alphabet). What does it literally mean?",
           "Buchstabe", "Beech stick", ["Book letter", "Letter book"], "Buche = beech, Stab = staff/stick.",
           "Early Germanic runes were carved on beech staves. Buch and English 'book' are probably named after the beech too.", "Quill Pen", 2),

    Riddle(23, "Spanish", "false friends", "In Spanish, 'embarazada' does NOT mean embarrassed. What does it mean?",
           "embarazada", "Pregnant", ["Embarrassed", "Sad", "Happy"], "Classic false friend!",
           "Embarazada = pregnant. 'Avergonzada' = embarrassed.", None, 1),

    Riddle(24, "Russian", "etymology", "Russian 'spasibo' (thank you) comes from what religious phrase?",
           "spasibo", "God save", ["Save me", "Thank God", "Spas"], "Spasi Bog = God save (you).",
           "From Old Church Slavonic 'spasi bog' = God save (you).", "Religious Text", 2),

    Riddle(25, "Greek", "etymology", "Greek 'astron' (ἄστρον) means star. Which word hides this root?",
           "ἄστρον", "Disaster", ["Easter", "Master"], "Blame bad luck on the stars.",
           "Disaster = Italian disastro, 'ill-starred'. Easter is from a Germanic dawn goddess; master from Latin magister.", None, 1),

    Riddle(26, "Latin", "etymology", "Latin 'specere' means to look. Which of inspect, respect and spectacle come from it?",
           "specere", "All of these", ["Only inspect", "Only spectacle", "None of these"], "Think of words with 'spect'.",
           "Specere → inspect, respect, suspect, specimen, spectacle, perspective, etc.", "Magnifying Glass", 2),

    Riddle(27, "French", "false friends", "In French, 'actuellement' does NOT mean 'actually'. What does it mean?",
           "actuellement", "Currently", ["Actually", "Accurately", "Finally"], "Think time, not truth.",
           "Actuellement = currently, at the moment. For 'actually', French says 'en fait'.", None, 2),

    Riddle(28, "Arvanitika", "cognates", "Albanian 'motër' means sister, and Arvanitika inherited it. Which English word shares its PIE root?",
           "motër", "Mother", ["Sister", "Brother"], "The meaning shifted inside the family.",
           "Albanian motër comes from PIE *méh₂tēr, 'mother'. Along the way it came to mean 'sister'.", None, 2),

    Riddle(29, "PIE", "etymology", "PIE root *tréyes means three. Which English / Greek / Latin set comes from it?",
           "*tréyes", "Three / τρία / tres", ["Two / δύο / duo", "Tree / δένδρο / arbor"], "Direct cognates.",
           "English three, Greek τρία (tria), Latin tres, all from PIE *tréyes.", None, 2),

    Riddle(30, "Hindi", "etymology", "The Hindi word 'namaste' combines 'namas' (bow) and what?",
           "namaste", "To you", ["Hello", "Goodbye", "Peace"], "Namah = bow, te = to you.",
           "From Sanskrit namas (bow/reverence) + te (to you).", "Namaste Symbol", 2),
]

LOCATIONS: Dict[str, Location] = {
    "ClientOffice": Location(
        "ClientOffice", "Weber's Office",
        "Berlin, 1947. Rain on the window, a desk lamp, a silent typewriter. "
        "Elena Weber, a linguist, has disappeared. Her brother found a note in Greek on her desk.",
        "Klaus Weber",
        "She said if anything happened to her, I should give this to a detective. It's all in Greek.",
        riddle_ids=[], lead_riddle=1, leads_to="Library", lead_after=0,
        lead_text="The note is a call slip from the Staatsbibliothek. Elena's handwriting, dated the day she vanished.",
        done_text="Please. Find her.",
    ),
    "Library": Location(
        "Library", "Staatsbibliothek",
        "Tall shelves stretch into shadow. Manuscripts in Greek, German, Latin. "
        "The air smells of parchment and secrets. A librarian eyes you suspiciously.",
        "Herr Schmidt",
        "She was here last week. Asking about Proto-Indo-European again. Always the old roots.",
        riddle_ids=[3, 9, 11, 13, 20, 21, 26, 29], lead_riddle=2, leads_to="Cafe", lead_after=3,
        lead_text="Tucked in Elena's last book: a napkin from Café Mozart, with a table number and a time.",
        done_text="You've read more than most of my students, detective.",
    ),
    "Cafe": Location(
        "Cafe", "Café Mozart",
        "Strong coffee and sugar hang in the air. Intellectuals and spies "
        "share tables in the dim light. A waiter polishes a glass, watching.",
        "Karl",
        "The men in dark suits come in every Tuesday. Always order the same thing.",
        riddle_ids=[5, 7, 10, 16, 18, 27], lead_riddle=24, leads_to="Church", lead_after=3,
        lead_text="Karl leans in: the men in suits always leave for St. Nicholas when the bells ring. They cross themselves on the way out.",
        done_text="No more gossip, detective. Just coffee.",
    ),
    "Church": Location(
        "Church", "St. Nicholas Church",
        "Candlelight flickers against stone walls. The sacristan moves silently between shadows. "
        "Old texts in Greek and Latin line the shelves. The Babel Society has left its mark here.",
        "Father Thomas",
        "The church has secrets, detective. Some older than the building itself.",
        riddle_ids=[6, 8, 17, 23, 28], lead_riddle=12, leads_to="Archive", lead_after=2,
        lead_text="Father Thomas unlocks the parish register. Every Babel Society meeting is noted, and every entry points to a basement archive near the Spree.",
        done_text="Go with God. And be careful down there.",
    ),
    "Archive": Location(
        "Archive", "Secret Archive",
        "Files upon files of linguistic research. The Babel Society's true work is here. "
        "Volkov, their leader, has been one step ahead. But you're closing in.",
        "Igor Volkov",
        "You're too late. The work is already done.",
        riddle_ids=[4, 14, 15, 19, 22, 25, 30],
        done_text="Every word traced to its root. Impressive. Now what, detective?",
    ),
}

STORY_ORDER = ["ClientOffice", "Library", "Cafe", "Church", "Archive"]
START_LOCATION = "ClientOffice"
FINAL_LOCATION = "Archive"


# =============================================================================
# GAME STATE
# =============================================================================

@dataclass
class GameState:
    current_location: str = START_LOCATION
    solved_riddles: List[int] = field(default_factory=list)
    fumbled_riddles: List[int] = field(default_factory=list)  # answered wrong at least once
    inventory: List[str] = field(default_factory=list)
    sanity: int = 3
    max_sanity: int = 3
    score: int = 0
    visited_locations: List[str] = field(default_factory=lambda: [START_LOCATION])
    unlocked_locations: List[str] = field(default_factory=lambda: [START_LOCATION])


@dataclass
class AnswerResult:
    correct: bool
    riddle: Riddle
    item_gained: bool = False
    unlocked: Optional[str] = None  # location id opened by solving a lead


# =============================================================================
# GAME ENGINE
# =============================================================================

class GameEngine:
    """Core game logic"""

    SAVE_DIR = Path.home() / ".babel_conspiracy_saves"

    def __init__(self):
        self.state = GameState()
        self.riddles = {r.id: r for r in RIDDLES}
        self.locations = LOCATIONS
        self.SAVE_DIR.mkdir(parents=True, exist_ok=True)

    # --- Queries -------------------------------------------------------------

    def location(self, loc_id: Optional[str] = None) -> Location:
        return self.locations[loc_id or self.state.current_location]

    def riddles_at(self, loc_id: str) -> List[int]:
        loc = self.locations[loc_id]
        return loc.riddle_ids + ([loc.lead_riddle] if loc.lead_riddle else [])

    def progress(self, loc_id: str) -> tuple:
        """(solved, total) for a location"""
        ids = self.riddles_at(loc_id)
        return sum(1 for i in ids if i in self.state.solved_riddles), len(ids)

    def lead_available(self, loc_id: str) -> bool:
        loc = self.locations[loc_id]
        if not loc.lead_riddle:
            return False
        solved_here = sum(1 for i in loc.riddle_ids if i in self.state.solved_riddles)
        return solved_here >= loc.lead_after

    def current_riddle(self) -> Optional[Riddle]:
        """The lead comes first once it is available, then the rest in order"""
        loc = self.location()
        solved = self.state.solved_riddles
        if self.lead_available(loc.id) and loc.lead_riddle not in solved:
            return self.riddles[loc.lead_riddle]
        for rid in loc.riddle_ids:
            if rid not in solved:
                return self.riddles[rid]
        return None

    def shuffled_options(self, riddle: Riddle) -> List[str]:
        options = [riddle.answer] + riddle.wrong_answers
        random.shuffle(options)
        return options

    def unlocked_locations(self) -> List[Location]:
        return [self.locations[i] for i in STORY_ORDER if i in self.state.unlocked_locations]

    def total_items(self) -> int:
        return sum(1 for r in self.riddles.values() if r.item)

    def can_confront(self) -> bool:
        """Volkov can be confronted once the detective reaches his archive"""
        return self.state.current_location == FINAL_LOCATION

    def is_game_over(self) -> bool:
        return self.state.sanity <= 0

    def all_riddles_solved(self) -> bool:
        return len(self.state.solved_riddles) >= len(self.riddles)

    def get_ending(self) -> tuple:
        """Determine ending based on progress"""
        total_riddles = len(self.riddles)
        solved = len(self.state.solved_riddles)
        collected = len(self.state.inventory)

        if solved >= total_riddles and collected >= self.total_items():
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
                   "You moved on Volkov with too little. Elena's file is closed, but he escapes with the manuscript.")

    # --- Actions -------------------------------------------------------------

    def new_game(self):
        self.state = GameState()
        (self.SAVE_DIR / "autosave.json").unlink(missing_ok=True)

    def answer(self, riddle: Riddle, choice: str) -> AnswerResult:
        """Check an answer and update state"""
        if choice.lower() != riddle.answer.lower():
            self.state.sanity -= 1
            if riddle.id not in self.state.fumbled_riddles:
                self.state.fumbled_riddles.append(riddle.id)
            self.autosave()
            return AnswerResult(False, riddle)

        result = AnswerResult(True, riddle)
        if riddle.id not in self.state.solved_riddles:
            self.state.solved_riddles.append(riddle.id)
            self.state.score += riddle.difficulty * 10

        # Evidence only survives a clean solve
        if riddle.item and riddle.id not in self.state.fumbled_riddles and riddle.item not in self.state.inventory:
            self.state.inventory.append(riddle.item)
            result.item_gained = True

        loc = self.location()
        if riddle.id == loc.lead_riddle and loc.leads_to not in self.state.unlocked_locations:
            self.state.unlocked_locations.append(loc.leads_to)
            result.unlocked = loc.leads_to

        self.autosave()
        return result

    def travel(self, loc_id: str) -> bool:
        if loc_id not in self.state.unlocked_locations:
            return False
        self.state.current_location = loc_id
        if loc_id not in self.state.visited_locations:
            self.state.visited_locations.append(loc_id)
        self.autosave()
        return True

    # --- Saving --------------------------------------------------------------

    def _write(self, path: Path):
        with open(path, 'w') as f:
            json.dump(asdict(self.state), f, indent=2)

    def autosave(self):
        self._write(self.SAVE_DIR / "autosave.json")

    def save_game(self, slot: int):
        self._write(self.SAVE_DIR / f"slot_{slot}.json")
        self.autosave()

    def load_game(self, slot: int = 0) -> bool:
        """Load a slot; slot 0 is the autosave"""
        name = "autosave.json" if slot == 0 else f"slot_{slot}.json"
        save_path = self.SAVE_DIR / name
        if not save_path.exists():
            return False

        try:
            with open(save_path, 'r') as f:
                data = json.load(f)

            state = GameState(**{k: v for k, v in data.items() if k in GameState.__dataclass_fields__})
            # Saves from before locations were unlockable: open everything already visited
            if "unlocked_locations" not in data:
                state.unlocked_locations = list(dict.fromkeys([START_LOCATION] + state.visited_locations + [state.current_location]))
            if state.current_location not in self.locations:
                state.current_location = START_LOCATION
            self.state = state
            return True
        except (OSError, ValueError, TypeError):
            return False

    def get_save_slots(self) -> List[tuple]:
        """(slot, exists, label) for slots 1-3"""
        slots = []
        for i in range(1, 4):
            save_path = self.SAVE_DIR / f"slot_{i}.json"
            if save_path.exists():
                try:
                    with open(save_path, 'r') as f:
                        data = json.load(f)
                    where = LOCATIONS.get(data.get("current_location"), LOCATIONS[START_LOCATION]).name
                    slots.append((i, True, f"{where} | Score: {data['score']}, Sanity: {data['sanity']}"))
                except (OSError, ValueError, KeyError):
                    slots.append((i, False, "Corrupted"))
            else:
                slots.append((i, False, "Empty"))
        return slots
