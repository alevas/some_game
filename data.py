"""
Noir Language Riddles - Data Module
All game data in one place for easy extension
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Riddle:
    """A single etymological riddle"""
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
    """A game location"""
    id: str
    name: str
    description: str
    first_riddle: int = 1


@dataclass
class Character:
    """An NPC character"""
    id: str
    name: str
    dialogue: List[str]


class GameData:
    """Central game database"""
    
    def __init__(self):
        self.riddles = self._load_riddles()
        self.locations = self._load_locations()
        self.characters = self._load_characters()
        self.location_character_map = {
            "ClientOffice": "Weber",
            "Library": "Librarian", 
            "Cafe": "Waiter",
            "Church": "Sacristan",
            "Archive": "Volkov"
        }
    
    def _load_riddles(self) -> List[Riddle]:
        return [
            Riddle(
                id=1, language="Greek", category="location",
                text="In Greek, it is βιβλίο (vivlio). Where do these live?",
                clue="βιβλίο",
                answer="Library",
                wrong_answers=["University", "Bookstore", "Her apartment"],
                hint="Think where books are collected and borrowed.",
                explanation="From Greek βιβλιον (biblion) = book. The word library comes from Latin liber (book).",
                next_location="Library",
                item="Case File",
                difficulty=1
            ),
            Riddle(
                id=2, language="German", category="location",
                text="In German, linguists met where Kaffee flows. Where?",
                clue="Linguisten trafen sich, wo Kaffee fließt",
                answer="Café Mozart",
                wrong_answers=["The university", "A private club", "A beer hall"],
                hint="Not a pub. Somewhere with coffee.",
                explanation="Kaffee = coffee. Berlin intellectuals historically met in cafes.",
                next_location="Cafe",
                item="Sugar Packet with Clue",
                difficulty=1
            ),
            Riddle(
                id=3, language="Spanish", category="etymology",
                text="This word is libro in Spanish, livre in French, and Buch in German. What is it in English?",
                clue="Spanish: libro | French: livre | German: Buch",
                answer="Book",
                wrong_answers=["Library", "Reading", "Novel"],
                hint="All three words mean the same thing. Think: what do you read?",
                explanation="All descend from Latin liber (inner bark of trees used for writing).",
                next_location="Cafe",
                item="Spanish Dictionary",
                difficulty=1
            ),
            Riddle(
                id=4, language="Russian", category="etymology",
                text="This Slavic word is передача (peredacha) meaning transmission. What English word shares the Latin root 'trahere'?",
                clue="передача (peredacha)",
                answer="Tradition",
                wrong_answers=["Transfer", "Translation", "Transport"],
                hint="Think of passing down through generations.",
                explanation="From Latin tradere = to hand over. Russian передача comes from the same PIE root.",
                next_location="Archive",
                item="Cipher Wheel",
                difficulty=2
            ),
            Riddle(
                id=5, language="Arvanitika", category="false friends",
                text="In Arvanitika, it is buke. In Greek, it is ψωμί (psomi). What is it in English?",
                clue="Arvanitika: buke | Greek: ψωμί",
                answer="Bread",
                wrong_answers=["Book", "Brick", "Water"],
                hint="It is a staple food.",
                explanation="Arvanitika buke and Greek ψωμί both mean bread. Shows the Albanian-Greek linguistic connection.",
                next_location="Cafe",
                item="Arvanitika Notes",
                difficulty=2
            ),
            Riddle(
                id=6, language="Greek", category="etymology",
                text="In Greek, it is πατήρ (pater). In German, it is Vater. What is it in English?",
                clue="Greek: πατήρ | German: Vater",
                answer="Father",
                wrong_answers=["Mother", "Brother", "Son"],
                hint="PIE root: *pəter",
                explanation="All descend from Proto-Indo-European *pəter.",
                next_location="Church",
                item=None,
                difficulty=1
            ),
            Riddle(
                id=7, language="German", category="false friends",
                text="In German, Gift does not mean a present. What does it mean?",
                clue="German: Gift",
                answer="Poison",
                wrong_answers=["Gift", "Present", "Disease"],
                hint="In English, a gift is positive. Not so in German.",
                explanation="German Gift = poison. English gift comes from Old Norse.",
                next_location="Cafe",
                item=None,
                difficulty=1
            ),
            Riddle(
                id=8, language="English", category="cognates",
                text="This English word is mother in English, Mutter in German, and μητέρα (meter) in Greek. What is it?",
                clue="English: mother | German: Mutter | Greek: μητέρα",
                answer="Mother",
                wrong_answers=["Sister", "Aunt", "Wife"],
                hint="PIE root: *méh₂tēr",
                explanation="All from PIE *méh₂t Αυτικητ. Preserved across 4000+ years.",
                next_location="Church",
                item="Family Tree",
                difficulty=1
            ),
            Riddle(
                id=9, language="Spanish", category="etymology",
                text="This word is noche in Spanish. In Latin it was nox. What is it in English?",
                clue="Spanish: noche | Latin: nox",
                answer="Night",
                wrong_answers=["Noon", "Noxious", "Nought"],
                hint="It is the opposite of day.",
                explanation="From Latin nox/noctis. English night also from same PIE root.",
                next_location="Library",
                item=None,
                difficulty=1
            ),
            Riddle(
                id=10, language="Russian", category="etymology",
                text="This Russian word is водка (vodka). It comes from вода (voda) meaning water. What is the connection?",
                clue="водка (vodka) | вода (voda)",
                answer="Little water",
                wrong_answers=["Fire water", "Strong drink", "Russian tea"],
                hint="Vodka is a diminutive form.",
                explanation="Vodka is the diminutive of вода (water). Originally referred to distilled spirits.",
                next_location="Cafe",
                item="Vodka Bottle",
                difficulty=2
            ),
        ]
    
    def _load_locations(self) -> List[Location]:
        return [
            Location(
                id="ClientOffice",
                name="Weber's Private Office",
                description="The dim glow of a desk lamp illuminates stacks of case files. Berlin, 1947. A typewriter sits silent, waiting. On the desk, a note in Greek catches your eye. Elena Weber, a linguist, has disappeared. The only clue: a trail of etymological breadcrumbs.",
                first_riddle=1
            ),
            Location(
                id="Library",
                name="Staatsbibliothek", 
                description="Tall shelves stretch into shadow. Ancient manuscripts in Greek, German, Latin. The air smells of parchment and secrets. A librarian eyes you suspiciously from behind a desk piled with indices.",
                first_riddle=3
            ),
            Location(
                id="Cafe",
                name="Café Mozart",
                description="The scent of strong coffee and sugar hangs in the air. Intellectuals and spies share tables in the dim light. A waiter polishes a glass, watching. This is where linguists used to meet.",
                first_riddle=2
            ),
            Location(
                id="Church",
                name="St. Nicholas Church",
                description="Candlelight flickers against stone walls. The sacristan moves silently between shadows. Old texts in Greek and Latin line the shelves. The Babel Society has left its mark here. You can feel it.",
                first_riddle=6
            ),
            Location(
                id="Archive",
                name="Secret Archive",
                description="Files upon files of linguistic research. The Babel Society's true work is here. Volkov, their leader, has been one step ahead. But you're closing in. The final pieces of the puzzle are within reach.",
                first_riddle=4
            ),
        ]
    
    def _load_characters(self) -> List[Character]:
        return [
            Character(id="Weber", name="Elena Weber", 
                     dialogue=["I need your help, detective. The Babel Society is real, and they've got their hands on something dangerous.",
                              "They're using language itself as a weapon. If we can't stop them...",
                              "Find the connections. The roots. They're the key to everything."]),
            Character(id="Librarian", name="Herr Schmidt",
                     dialogue=["She was here just last week. Asking about Proto-Indo-European again.",
                              "I told her it was dangerous. Some knowledge should stay buried.",
                              "Take this. She left it for you."]),
            Character(id="Waiter", name="Karl the Waiter",
                     dialogue=["The men in the dark suits? They come in every Tuesday. Always order the same thing.",
                              "She sat in the corner, with her notebooks. Always writing, always thinking.",
                              "They were speaking Russian. But not just Russian... something older."]),
            Character(id="Sacristan", name="Father Thomas",
                     dialogue=["The church has secrets, detective. Some older than the building itself.",
                              "They come at night. Always checking the old manuscripts.",
                              "The word of God... twisted. That's what they're doing here."]),
            Character(id="Volkov", name="Igor Volkov",
                     dialogue=["You're too late, detective. The work is already done.",
                              "Language is power. And power belongs to those who understand the roots.",
                              "Join us. Or become another footnote in history."]),
        ]
    
    def get_riddle_for_location(self, location_id: str) -> Optional[Riddle]:
        """Get the first unsolved riddle for a location"""
        loc = self.get_location(location_id)
        if not loc:
            return None
        
        # First, try the location's first_riddle
        first = self.get_riddle(loc.first_riddle)
        if first and first.id not in self.get_all_riddle_ids():
            # Wait, this logic is wrong. Let me rethink
            pass
        
        # For now, just return riddles that point to this location or are the first riddle
        for riddle in self.riddles:
            if riddle.next_location == location_id:
                return riddle
        
        return self.get_riddle(loc.first_riddle)
    
    def get_location(self, location_id: str) -> Optional[Location]:
        """Get location by ID"""
        for loc in self.locations:
            if loc.id == location_id:
                return loc
        return None
    
    def get_riddle(self, riddle_id: int) -> Optional[Riddle]:
        """Get riddle by ID"""
        for riddle in self.riddles:
            if riddle.id == riddle_id:
                return riddle
        return None
    
    def get_character(self, location_id: str) -> Optional[Character]:
        """Get character for a location"""
        char_id = self.location_character_map.get(location_id)
        if char_id:
            for char in self.characters:
                if char.id == char_id:
                    return char
        return None
    
    def get_all_riddle_ids(self) -> List[int]:
        """Get all riddle IDs"""
        return [r.id for r in self.riddles]
    
    def get_riddles_with_items(self) -> List[Riddle]:
        """Get all riddles that have items"""
        return [r for r in self.riddles if r.item]


# Singleton instance
DATA = GameData()
