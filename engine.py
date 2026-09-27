"""
Noir Language Riddles: The Babel Conspiracy
Game data and engine, shared by the console UI (main_polished.py) and the
full-screen ASCII UI (tui.py). Nothing in here prints or reads input.

The case is a chain of locations. Each location holds its own riddles plus one
"lead" riddle. The lead shows up once enough of the location's riddles are
solved, and solving it unlocks the next location. You can move on early and
come back later, but evidence you skip counts against you at the end.

Evidence is also currency: show it to characters to learn more, trade it for a
hint, or throw it at Volkov in the final showdown to dodge a question.
"""

import json
import random
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Tuple


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
    decoys: List[str] = field(default_factory=list)  # swapped in after a wrong pick
    # "choice": pick one of the options
    # "type":   type the word (answer plus any `accepted` spellings)
    # "match":  pair each left-hand word with its right-hand partner; answer is the partners joined by "|"
    kind: str = "choice"
    accepted: List[str] = field(default_factory=list)
    pairs: List[Tuple[str, str]] = field(default_factory=list)
    item_help: Optional[Tuple[str, str]] = None  # (evidence, extra help shown while you hold it)

    def display_answer(self) -> str:
        if self.kind == "match":
            return ", ".join(f"{left} = {right}" for left, right in self.pairs)
        return self.answer


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
    beats: List[Tuple[int, str]] = field(default_factory=list)  # (riddles solved here, what you learn)
    good_lines: List[str] = field(default_factory=list)  # reactions to a clean answer
    bad_lines: List[str] = field(default_factory=list)   # reactions to a slip
    present: Dict[str, str] = field(default_factory=dict)  # evidence shown -> what the character reveals


RIDDLES = [
    Riddle(1, "Greek", "location", "In Greek, it is βιβλίο (vivlio). Where would you go to borrow one?",
           "βιβλίο", "Library", ["University", "Bookstore"],
           "Think where books are collected and borrowed.",
           "Greek βιβλίο = book; a library is a βιβλιοθήκη ('book case'). English 'library' took the Latin route: liber (book) → librarium.", "Case File", 1,
           decoys=['Post office', 'Museum']),

    Riddle(2, "German", "location", "In German, linguists met where Kaffee flows. Where?",
           "Linguisten trafen sich, wo Kaffee fließt", "Café Mozart",
           ["The university", "A beer hall"], "Not a pub. Somewhere with coffee.",
           "Kaffee = coffee. Berlin intellectuals met in cafes.", "Sugar Packet", 1,
           decoys=['A bakery', 'The train station']),

    Riddle(3, "Spanish", "etymology", "This word is libro in Spanish, livre in French, Buch in German. What is it in English?",
           "libro | livre | Buch", "Book", ["Library", "Novel"],
           "All three words mean the same thing.",
           "Libro and livre come from Latin liber (originally 'inner bark'). Buch is Germanic, a sibling of English 'book'.", "Spanish Dictionary", 1,
           decoys=['Letter', 'Page']),

    Riddle(4, "Russian", "cognates", "Russian новый (novyi), Latin novus, Greek νέος (neos). What is it in English?",
           "новый | novus | νέος", "New", ["Noon", "Nine"],
           "The opposite of old.",
           "All from PIE *néwos. 'Nine' looks close but comes from a different root, *h₁néwn̥.", "Cipher Wheel", 2,
           decoys=['Now', 'Near']),

    Riddle(5, "Arvanitika", "false friends", "In Arvanitika, it is buke. In Greek, it is ψωμί. What is it in English?",
           "buke | ψωμί", "Bread", ["Book", "Brick"], "It is a staple food.",
           "Arvanitika buke and Greek ψωμί both mean bread. It only looks like 'book'.", "Arvanitika Notes", 2,
           decoys=['Cheese', 'Water']),

    Riddle(6, "Greek", "etymology", "In Greek, it is πατήρ (pater). In German, it is Vater. What is it in English?",
           "πατήρ | Vater", "Father", ["Mother", "Brother"], "PIE root: *ph₂tḗr",
           "All descend from Proto-Indo-European *ph₂tḗr. Germanic turned p into f/v.", None, 1,
           decoys=['Uncle', 'Pastor']),

    Riddle(7, "German", "false friends", "In German, Gift does not mean a present. What does it mean?",
           "Gift", "Poison", ["Gift", "Present"], "In English, gift is positive.",
           "German Gift once meant 'something given', a dose, and narrowed to 'poison'. English kept the original sense.", None, 1,
           decoys=['Money', 'Luck']),

    Riddle(8, "German", "cognates", "It is Mutter in German, μητέρα (mitera) in Greek, mater in Latin. What is it in English?",
           "Mutter | μητέρα | mater", "Mother", ["Sister", "Aunt"], "PIE root: *méh₂tēr",
           "All from PIE *méh₂tēr. Preserved across 4000+ years.", "Family Tree", 1,
           decoys=['Daughter', 'Wife']),

    Riddle(9, "Spanish", "etymology", "This word is noche in Spanish. In Latin it was nox. What is it in English?",
           "noche | nox", "Night", ["Noon", "Noxious"], "It is the opposite of day.",
           "Latin nox, noctis and English night are cognates from PIE *nókʷts. 'Noxious' comes from noxa (harm).", None, 1,
           decoys=['Nook', 'Nose']),

    Riddle(10, "Russian", "etymology", "This Russian word is водка (vodka). From вода (voda) meaning water. What is the connection?",
           "водка | вода", "Little water", ["Fire water", "Strong drink"], "Vodka is a diminutive.",
           "Vodka is the diminutive of вода (water).", "Vodka Bottle", 2,
           decoys=['Grain spirit', 'Holy water']),

    # New 20 riddles
    Riddle(11, "Latin", "etymology", "This Latin word 'lux' (genitive lucis) means light. What English word derives from it?",
           "lux", "Lucid", ["Luxury", "Luck"], "Think of a clear, bright mind.",
           "Lux, lucis → lucid, elucidate, translucent. 'Luxury' is a trap: it comes from luxus (excess).", "Lantern", 2,
           decoys=['Lust', 'Lush']),

    Riddle(12, "French", "etymology", "In French, 'histoire' means both history and story. What everyday English word shares its root?",
           "histoire", "Story", ["Histogram", "Hysteria"], "From Latin historia.",
           "Story is a clipped form of Old French estoire, from Latin historia. Histogram (histos, 'mast') and hysteria (hystera, 'womb') only look similar.", "History Book", 2,
           decoys=['Mystery', 'Stair']),

    Riddle(13, "Greek", "etymology", "This Greek word φως (phos) means light. What English prefix means light?",
           "φως (phos)", "Photo-", ["Phono-", "Philo-"], "As in photography.",
           "From Greek φῶς, φωτός (phos, photos) = light. Phono- is sound, philo- is love.", "Photograph", 1,
           decoys=['Phyto-', 'Phylo-']),

    Riddle(14, "Sanskrit", "etymology", "The Sanskrit word 'danta' means tooth. What English word is related?",
           "danta", "Dental", ["Dandy", "Dance"], "Think of your dentist.",
           "Sanskrit दन्त (danta) and Latin dens, dentis (→ dental) share PIE *h₃dónts, which also became English 'tooth'.", "Dental Mirror", 2,
           decoys=['Denim', 'Dainty']),

    Riddle(15, "Old Norse", "borrowings", "Old Norse 'skyrta' meant shirt. English kept its native 'shirt', but borrowed the Norse word too. As what?",
           "skyrta", "Skirt", ["Short", "Scarf"], "Vikings kept the hard 'sk' sound.",
           "Shirt (Old English scyrte) and skirt (Old Norse skyrta) are the same word. The Vikings left English doublets like this.", "Viking Brooch", 1,
           decoys=['Shawl', 'Scarlet']),

    Riddle(16, "Arabic", "borrowings", "This Arabic word 'sukkar' means sugar. Through which language did it reach English?",
           "sukkar", "Old French", ["Persian", "Greek"], "It came to England via the Mediterranean and the Normans' language.",
           "Sanskrit śarkarā → Persian shakar → Arabic sukkar → Medieval Latin succarum / Old French sucre → English sugar.", "Sugar Cube", 2,
           decoys=['Dutch', 'Old Norse']),

    Riddle(17, "Hebrew", "etymology", "The Hebrew word 'shalom' means peace. What does its root literally mean?",
           "שלום", "Wholeness", ["Hello", "Victory"], "Root means completeness.",
           "Peace as wholeness, not just absence of conflict.", "Peace Symbol", 2,
           decoys=['Silence', 'Surrender']),

    Riddle(18, "Japanese", "borrowings", "The Japanese word 'pan' (パン) for bread comes from which language?",
           "パン", "Portuguese", ["Chinese", "English", "French"], "From Portuguese pão.",
           "Portuguese traders brought bread to Japan in the 16th century.", "Portuguese Bread", 1,
           decoys=['Dutch', 'Korean']),

    Riddle(19, "Finnish", "etymology", "Finnish 'kala' means fish. It's unrelated to most European words. Why?",
           "kala", "Uralic language", ["Indo-European", "Slavic", "Germanic"], "Finnish is not Indo-European.",
           "Finnish belongs to the Uralic family. Its cousin is Hungarian hal (fish), not English or German.", "Language Map", 2,
           decoys=['Celtic', 'Baltic']),

    Riddle(20, "Egyptian", "etymology", "Ancient Egyptians called the Nile 'iteru', simply 'the river'. From which language does the name 'Nile' come?",
           "iteru", "Greek", ["Egyptian", "Arabic"], "Herodotus wrote about it.",
           "'Nile' comes from Greek Νεῖλος (Neilos), of uncertain origin. The Egyptians just said iteru.", "Papyrus Scroll", 3,
           decoys=['Coptic', 'Hebrew']),

    Riddle(21, "Greek", "cognates", "Greek ὕδωρ (hydor) means water. Which of these words does NOT contain this root?",
           "ὕδωρ", "Hybrid", ["Hydrogen", "Dehydrated"], "Two of these are wet.",
           "Hydrogen ('water-maker') and dehydrated contain hydor. Hybrid comes from Latin hybrida, 'mongrel'.", None, 1,
           decoys=['Hydrant', 'Hydraulic']),

    Riddle(22, "German", "etymology", "German 'Buchstabe' means letter (of alphabet). What does it literally mean?",
           "Buchstabe", "Beech stick", ["Book letter", "Letter book"], "Buche = beech, Stab = staff/stick.",
           "Early Germanic runes were carved on beech staves. Buch and English 'book' are probably named after the beech too.", "Quill Pen", 2,
           decoys=['Oak tablet', 'Stamp mark']),

    Riddle(23, "Spanish", "false friends", "In Spanish, 'embarazada' does NOT mean embarrassed. What does it mean?",
           "embarazada", "Pregnant", ["Embarrassed", "Sad", "Happy"], "Classic false friend!",
           "Embarazada = pregnant. 'Avergonzada' = embarrassed.", None, 1,
           decoys=['Married', 'Engaged']),

    Riddle(24, "Russian", "etymology", "Russian 'spasibo' (thank you) comes from what religious phrase?",
           "spasibo", "God save", ["Save me", "Thank God", "Spas"], "Spasi Bog = God save (you).",
           "From Old Church Slavonic 'spasi bog' = God save (you).", "Religious Text", 2,
           decoys=['Bless you', 'Holy Russia']),

    Riddle(25, "Greek", "etymology", "Greek 'astron' (ἄστρον) means star. Which word hides this root?",
           "ἄστρον", "Disaster", ["Easter", "Master"], "Blame bad luck on the stars.",
           "Disaster = Italian disastro, 'ill-starred'. Easter is from a Germanic dawn goddess; master from Latin magister.", None, 1,
           decoys=['Plaster', 'Monster']),

    Riddle(26, "Latin", "etymology", "Latin 'specere' means to look. Which of inspect, respect and spectacle come from it?",
           "specere", "All of these", ["Only inspect", "Only spectacle", "None of these"], "Think of words with 'spect'.",
           "Specere → inspect, respect, suspect, specimen, spectacle, perspective, etc.", "Magnifying Glass", 2,
           decoys=['Only respect', 'Only inspect and respect']),

    Riddle(27, "French", "false friends", "In French, 'actuellement' does NOT mean 'actually'. What does it mean?",
           "actuellement", "Currently", ["Actually", "Accurately", "Finally"], "Think time, not truth.",
           "Actuellement = currently, at the moment. For 'actually', French says 'en fait'.", None, 2,
           decoys=['Eventually', 'Seriously']),

    Riddle(28, "Arvanitika", "cognates", "Albanian 'motër' means sister, and Arvanitika inherited it. Which English word shares its PIE root?",
           "motër", "Mother", ["Sister", "Brother"], "The meaning shifted inside the family.",
           "Albanian motër comes from PIE *méh₂tēr, 'mother'. Along the way it came to mean 'sister'.", None, 2,
           decoys=['Motor', 'Other']),

    Riddle(29, "PIE", "etymology", "PIE root *tréyes means three. Which English / Greek / Latin set comes from it?",
           "*tréyes", "Three / τρία / tres", ["Two / δύο / duo", "Tree / δένδρο / arbor"], "Direct cognates.",
           "English three, Greek τρία (tria), Latin tres, all from PIE *tréyes.", None, 2,
           decoys=['Thirst / δίψα / sitis', 'Throne / θρόνος / thronus']),

    Riddle(30, "Hindi", "etymology", "The Hindi word 'namaste' combines 'namas' (bow) and what?",
           "namaste", "To you", ["Hello", "Goodbye", "Peace"], "Namah = bow, te = to you.",
           "From Sanskrit namas (bow/reverence) + te (to you).", "Namaste Symbol", 2,
           decoys=['Thank you', 'Welcome']),

    # Sound shifts: type the English cognate by applying Grimm's law
    Riddle(31, "Latin", "sound shift",
           "Latin 'pes, pedis' names a body part. Apply Grimm's law (p → f, d → t) to find its English cousin.",
           "pes, pedis   (p → f, d → t)", "foot", [], "You stand on two of them.",
           "Latin pes, pedis and English foot are cognates: Germanic shifted p to f and d to t (Grimm's law). "
           "Pedal and pedestrian are later loans from the Latin.", None, 2, kind="type", accepted=["feet"]),

    Riddle(32, "Latin", "sound shift",
           "Latin 'tu' means 'you' (one person). Grimm's law turned t into th. What is the old English word, still heard in prayers?",
           "tu   (t → th)", "thou", [], "'___ shalt not...'",
           "Latin tu and English thou are cognates; t → th is Grimm's law. German kept du.",
           None, 2, kind="type", accepted=["thee"]),

    Riddle(33, "Latin", "sound shift",
           "Latin 'centum' (said 'kentum') means a number. Grimm's law shifted k to h and t to d. What is it in English?",
           "centum   (k → h, t → d)", "hundred", [], "Ten times ten.",
           "Latin centum and English hundred share PIE *ḱm̥tóm: k → h and t → d are Grimm's law. "
           "The -red was added later, from an old word for 'count'.", "Parish Ledger", 3, kind="type"),

    Riddle(34, "Latin", "sound shift",
           "Latin 'genu' is a body part. Grimm's law turned g into k. What is it in English? (The k is silent now.)",
           "genu   (g → k)", "knee", [], "It bends when you kneel.",
           "Latin genu and English knee are cognates: g → k is Grimm's law. "
           "The k in 'knee' was pronounced until the 1600s.", None, 2, kind="type", accepted=["knees"]),

    # Odd one out
    Riddle(35, "Arabic", "odd one out", "Which of these is NOT a loanword from Arabic?",
           "Arabic loanwords in English", "Tea", ["Algebra", "Alcohol", "Coffee"],
           "One of these came from China, by sea.",
           "Algebra (al-jabr), alcohol (al-kuḥl), coffee (qahwa), zero (ṣifr) and sofa (ṣuffa) are Arabic. "
           "Tea comes from Chinese (Min dialect 'te'), brought by Dutch traders.", None, 2,
           decoys=["Zero", "Sofa"]),

    Riddle(38, "French", "odd one out",
           "After 1066, Norman French gave English its words for meat. Which of these is NOT from French?",
           "Norman French, 1066", "Sheep", ["Beef", "Pork", "Mutton"],
           "Saxon farmers raised the animals; Norman lords ate the meat.",
           "Beef (boeuf), pork (porc), mutton (mouton), veal and venison came with the Normans. "
           "Sheep, cow and swine stayed Old English: the animal in the field, the French word on the plate.",
           "Norman Menu", 2, decoys=["Veal", "Venison"]),

    # Match the pairs
    Riddle(36, "German", "false friends", "Match each German false friend to what it really means.",
           "Rat · bekommen · Chef", "advice|to receive|boss", [],
           "A German 'Chef' runs the office, not the kitchen.",
           "Rat = advice (not a rodent), bekommen = to receive (not 'become'), Chef = boss (not a cook).",
           "Waiter's Notepad", 2, kind="match",
           pairs=[("Rat", "advice"), ("bekommen", "to receive"), ("Chef", "boss")]),

    Riddle(37, "Greek", "cognates", "Match each Greek word to the English word built from it.",
           "θεός · πῦρ · χρόνος", "theology|pyromaniac|chronicle", [], "πῦρ is fire.",
           "θεός (theos) = god → theology; πῦρ (pyr) = fire → pyromaniac; χρόνος (chronos) = time → chronicle.",
           None, 2, kind="match",
           pairs=[("θεός (theos)", "theology"), ("πῦρ (pyr)", "pyromaniac"), ("χρόνος (chronos)", "chronicle")]),

    # Elena's cipher: easier if you kept the Cipher Wheel
    Riddle(39, "Cipher", "cipher", "Hidden in Volkov's files, a scrap of paper in Elena's hand. Decode it.",
           "F U B S W", "crypt", [], "Each letter was moved the same number of places along the alphabet.",
           "A Caesar cipher: every letter shifted three places forward. Elena was telling you where she is.",
           None, 3, kind="type", item_help=("Cipher Wheel", "Your Cipher Wheel is set to 3: move each letter back three places.")),
]

# The final showdown: Volkov picks three of these. They don't count toward the 39.
VOLKOV_RIDDLES = [
    Riddle(101, "Latin", "sound shift", "'Latin dens, dentis,' Volkov says. 'Grimm's law: d → t. The English word, detective?'",
           "dens, dentis   (d → t)", "tooth", [], "",
           "Dens, dentis and tooth share PIE *h₃dónts; d → t is Grimm's law, and English lost the n (compare German Zahn).",
           kind="type", accepted=["teeth"]),
    Riddle(102, "English", "family", "'Which living language is English's closest relative?'",
           "West Germanic", "Frisian", ["German", "Danish", "Icelandic"], "",
           "Frisian, spoken on the North Sea coast. 'Bread, butter and green cheese is good English and good Fries.'",
           decoys=["Welsh", "Latin"]),
    Riddle(103, "Sanskrit", "cognates", "'Match my Sanskrit to your English.'",
           "pitṛ · bhrātṛ · dva", "father|brother|two", [], "",
           "Sanskrit pitṛ, bhrātṛ and dva, English father, brother and two: all Proto-Indo-European.",
           kind="match", pairs=[("पितृ (pitṛ)", "father"), ("भ्रातृ (bhrātṛ)", "brother"), ("द्व (dva)", "two")]),
    Riddle(104, "Akkadian", "etymology", "Volkov smiles. 'Babel. In Akkadian, Bāb-ili meant what?'",
           "Bāb-ili", "Gate of God", ["Confusion", "Tower of Heaven", "City of Tongues"], "",
           "Akkadian bāb-ili = gate of god. The Bible ties Babel to Hebrew bālal, 'to confuse': a pun, not the origin.",
           decoys=["House of Kings", "River Gate"]),
]
ALL_RIDDLES = {r.id: r for r in RIDDLES + VOLKOV_RIDDLES}
SHOWDOWN_ROUNDS = 3
SHOWDOWN_INTRO = ("Volkov steps out from between the cabinets. "
                  "\"Words are my weapons, detective. Let us see yours.\"")

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
        beats=[(1, "She walked along the Spree every night. Said the water helped her think.")],
        good_lines=["You really can read it!", "Elena said you were good."],
        bad_lines=["Are you sure you know Greek?", "Please, take your time. For her sake."],
        present={'Photograph': "That's Elena outside St. Nicholas, before the war. She loved that church. Said its crypt was older than Berlin itself."},
    ),
    "Library": Location(
        "Library", "Staatsbibliothek",
        "Tall shelves stretch into shadow. Manuscripts in Greek, German, Latin. "
        "The air smells of parchment and secrets. A librarian eyes you suspiciously.",
        "Herr Schmidt",
        "She was here last week. Asking about Proto-Indo-European again. Always the old roots.",
        riddle_ids=[3, 9, 31, 11, 13, 20, 35, 21, 26, 29], lead_riddle=2, leads_to="Cafe", lead_after=3,
        lead_text="Tucked in Elena's last book: a napkin from Café Mozart, with a table number and a time.",
        done_text="You've read more than most of my students, detective.",
        beats=[
            (2, "She kept requesting the 1690 plans of St. Nicholas. Not the nave. The parts below ground."),
            (5, "The men who came after her asked for the same plans. I told them they were lost. They were not."),
            (8, "Elena told me once: the oldest words are always buried deepest."),
        ],
        good_lines=["Hm. Not bad, for a policeman.", "Correct. Elena would approve."],
        bad_lines=["Tsk. Look it up, detective.", "My first-year students know that one."],
        present={'Case File': "Her last call slip: the St. Nicholas plans. Stamped 'returned'. They were never returned."},
    ),
    "Cafe": Location(
        "Cafe", "Café Mozart",
        "Strong coffee and sugar hang in the air. Intellectuals and spies "
        "share tables in the dim light. A waiter polishes a glass, watching.",
        "Karl",
        "The men in dark suits come in every Tuesday. Always order the same thing.",
        riddle_ids=[5, 7, 32, 10, 16, 36, 18, 27], lead_riddle=24, leads_to="Church", lead_after=3,
        lead_text="Karl leans in: the men in suits always leave for St. Nicholas when the bells ring. They cross themselves on the way out.",
        done_text="No more gossip, detective. Just coffee.",
        beats=[
            (2, "The suits take bread and soup to go. Every day. Nobody takes soup to go."),
            (4, "They carry it across the square, toward the church, still steaming."),
            (6, "Our cellar? Only beer and rats down there. Go look, if you like. I did."),
        ],
        good_lines=["Sharp. Like the coffee.", "Careful being that clever in here."],
        bad_lines=["Maybe stick to the coffee, detective.", "The suits are laughing at you."],
        present={'Sugar Packet': "From table six, the suits' table. They always take extra sugar. 'For the lady,' they say."},
    ),
    "Church": Location(
        "Church", "St. Nicholas Church",
        "Candlelight flickers against stone walls. The sacristan moves silently between shadows. "
        "Old texts in Greek and Latin line the shelves. The Babel Society has left its mark here.",
        "Father Thomas",
        "The church has secrets, detective. Some older than the building itself.",
        riddle_ids=[6, 8, 33, 17, 37, 23, 28], lead_riddle=12, leads_to="Archive", lead_after=2,
        lead_text="Father Thomas unlocks the parish register. Every Babel Society meeting is noted, and every entry points to a basement archive near the Spree.",
        done_text="Go with God. And be careful down there.",
        beats=[
            (2, "The crypt has been sealed since the bombing in '44. No one goes down there."),
            (4, "Though the sacristan swears he hears a woman singing beneath the altar at night. Greek hymns."),
            (6, "Forgive me. I lied. They made me give them the crypt key."),
        ],
        good_lines=["The Lord gave you a good ear.", "Yes... that is right."],
        bad_lines=["Pride comes before the fall, my son.", "Slowly. The old words do not hurry."],
        present={'Arvanitika Notes': "Arvanitika... the sacristan's grandmother spoke it. He says the songs beneath the altar sound like this."},
    ),
    "Archive": Location(
        "Archive", "Secret Archive",
        "Files upon files of linguistic research. The Babel Society's true work is here. "
        "Volkov, their leader, has been one step ahead. But you're closing in.",
        "Igor Volkov",
        "You're too late. The work is already done.",
        riddle_ids=[4, 14, 34, 15, 19, 39, 22, 38, 25, 30],
        done_text="Every word traced to its root. Impressive. Now what, detective?",
        beats=[
            (2, "You think I would keep her here, among my papers? I am not sentimental."),
            (4, "The river? How romantic. No. Water ruins paper, and she is writing for me."),
            (6, "She is closer to God than you are, detective. And deeper."),
        ],
        good_lines=["...Lucky guess.", "So. You have done your reading."],
        bad_lines=["Ha! Elena would be ashamed of you.", "Every mistake brings my men closer, detective."],
        present={'Religious Text': 'A hymnal? Put it away. I hear enough hymns from below as it is.'},
    ),
}

STORY_ORDER = ["ClientOffice", "Library", "Cafe", "Church", "Archive"]

# The final question: where is Elena? The answer is pieced together from the beats.
ELENA_QUESTION = "Before you face Volkov: where is Elena being held?"
ELENA_OPTIONS = [
    "A safe house by the Spree",
    "The back rooms of the Archive",
    "The crypt under St. Nicholas",
    "The cellar of Café Mozart",
]
ELENA_ANSWER = "The crypt under St. Nicholas"
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
    streak: int = 0  # riddles solved first try in a row
    visited_locations: List[str] = field(default_factory=lambda: [START_LOCATION])
    unlocked_locations: List[str] = field(default_factory=lambda: [START_LOCATION])
    presented: List[str] = field(default_factory=list)  # "location:item" pairs that revealed something


@dataclass
class AnswerResult:
    correct: bool
    riddle: Riddle
    item_gained: bool = False
    unlocked: Optional[str] = None  # location id opened by solving a lead
    beat: Optional[str] = None      # story beat revealed by this answer
    streak_bonus: int = 0
    heart_restored: bool = False


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
        self.notebook = self._load_notebook()

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

    def replace_wrong_option(self, riddle: Riddle, options: List[str], picked: str,
                             eliminated: List[str]) -> List[str]:
        """Swap a wrong pick for an unused decoy and reshuffle, so guessing through doesn't work"""
        eliminated.append(picked)
        new = [o for o in options if o != picked]
        spare = [d for d in riddle.decoys if d not in new and d not in eliminated]
        if spare:
            new.append(spare[0])
        random.shuffle(new)
        return new

    def match_options(self, riddle: Riddle) -> List[str]:
        """The right-hand column of a match riddle, shuffled"""
        rights = [right for _, right in riddle.pairs]
        random.shuffle(rights)
        return rights

    def match_response(self, riddle: Riddle, shown: List[str], letters: str) -> Optional[str]:
        """Turn typed letters (e.g. 'BCA') into an answer string, or None if they don't make sense"""
        letters = re.sub(r"[^A-Za-z]", "", letters).upper()
        indexes = [ord(ch) - ord("A") for ch in letters]
        if len(indexes) != len(riddle.pairs) or sorted(indexes) != list(range(len(shown))):
            return None
        return "|".join(shown[i] for i in indexes)

    @staticmethod
    def is_correct(riddle: Riddle, response: str) -> bool:
        if riddle.kind == "type":
            def norm(word: str) -> str:
                return re.sub(r"[^a-z]", "", word.lower())
            return norm(response) in {norm(a) for a in [riddle.answer] + riddle.accepted}
        return response.strip().lower() == riddle.answer.lower()

    def item_help(self, riddle: Riddle) -> Optional[str]:
        """Extra help for a riddle when you hold the right evidence"""
        if riddle.item_help and riddle.item_help[0] in self.state.inventory:
            return riddle.item_help[1]
        return None

    def beats_unlocked(self, loc_id: str) -> List[str]:
        solved, _ = self.progress(loc_id)
        return [text for needed, text in self.locations[loc_id].beats if solved >= needed]

    def case_notes(self) -> List[Tuple[str, str]]:
        """(location name, note) for everything learned so far, in story order"""
        notes = []
        for loc in self.unlocked_locations():
            if loc.lead_riddle in self.state.solved_riddles:
                notes.append((loc.name, loc.lead_text))
            notes.extend((loc.name, f'{loc.character}: "{beat}"') for beat in self.beats_unlocked(loc.id))
            for item, text in loc.present.items():
                if f"{loc.id}:{item}" in self.state.presented:
                    notes.append((loc.name, f'{loc.character}, shown the {item}: "{text}"'))
        return notes

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

    def get_ending(self, elena_guess: Optional[str], volkov_beaten: bool) -> tuple:
        """Determine ending from progress, the showdown, and where the detective looked for Elena"""
        total_riddles = len(self.riddles)
        solved = len(self.state.solved_riddles)
        found = elena_guess == ELENA_ANSWER

        if volkov_beaten and found and solved >= total_riddles:
            title, text = ("The Truth Revealed",
                           "Volkov leaves in handcuffs, and every root of the Babel Society is exposed to the world.")
        elif volkov_beaten:
            title, text = ("Partial Victory",
                           "You outwit Volkov and the police take him away, but his society's members scatter into the night.")
        elif solved >= total_riddles / 2:
            title, text = ("A Lead, Not a Victory",
                           "Volkov slips out the back of the archive. You have enough to close the case, but the Babel Society remains.")
        else:
            title, text = ("Case Closed",
                           "You moved on Volkov with too little. He escapes with the manuscript.")

        if found:
            text += " Beneath St. Nicholas, behind a bricked-up arch, you find Elena alive."
        else:
            text += " You search the wrong place. Elena Weber is never seen again."
        return title, text

    # --- Actions -------------------------------------------------------------

    def new_game(self):
        self.state = GameState()
        (self.SAVE_DIR / "autosave.json").unlink(missing_ok=True)

    def answer(self, riddle: Riddle, choice: str) -> AnswerResult:
        """Check an answer and update state"""
        if not self.is_correct(riddle, choice):
            self.state.sanity -= 1
            self.state.streak = 0
            if riddle.id not in self.state.fumbled_riddles:
                self.state.fumbled_riddles.append(riddle.id)
            self.autosave()
            return AnswerResult(False, riddle)

        result = AnswerResult(True, riddle)
        self.learn(riddle)
        loc = self.location()
        beats_before = len(self.beats_unlocked(loc.id))
        if riddle.id not in self.state.solved_riddles:
            self.state.solved_riddles.append(riddle.id)
            self.state.score += riddle.difficulty * 10

        # First-try streak: bonus score, and every third clean solve steadies your nerve
        if riddle.id not in self.state.fumbled_riddles:
            self.state.streak += 1
            result.streak_bonus = min(5 * (self.state.streak - 1), 20)
            self.state.score += result.streak_bonus
            if self.state.streak % 3 == 0 and self.state.sanity < self.state.max_sanity:
                self.state.sanity += 1
                result.heart_restored = True

        beats = self.beats_unlocked(loc.id)
        if len(beats) > beats_before:
            result.beat = beats[-1]

        # Evidence only survives a clean solve
        if riddle.item and riddle.id not in self.state.fumbled_riddles and riddle.item not in self.state.inventory:
            self.state.inventory.append(riddle.item)
            result.item_gained = True

        if riddle.id == loc.lead_riddle and loc.leads_to not in self.state.unlocked_locations:
            self.state.unlocked_locations.append(loc.leads_to)
            result.unlocked = loc.leads_to

        self.autosave()
        return result

    def present(self, item: str) -> Optional[str]:
        """Show evidence to the character here. Returns what they reveal, or None."""
        loc = self.location()
        text = loc.present.get(item)
        key = f"{loc.id}:{item}"
        if text and key not in self.state.presented:
            self.state.presented.append(key)
            self.autosave()
        return text

    def spend_item(self, item: str) -> bool:
        """Give up a piece of evidence (for a hint, or to dodge Volkov)"""
        if item not in self.state.inventory:
            return False
        self.state.inventory.remove(item)
        self.autosave()
        return True

    def start_showdown(self) -> "Showdown":
        return Showdown(self)

    def travel(self, loc_id: str) -> bool:
        if loc_id not in self.state.unlocked_locations:
            return False
        self.state.current_location = loc_id
        if loc_id not in self.state.visited_locations:
            self.state.visited_locations.append(loc_id)
        self.autosave()
        return True

    # --- Etymology notebook (kept across cases) --------------------------------

    def _load_notebook(self) -> List[int]:
        try:
            with open(self.SAVE_DIR / "notebook.json") as f:
                return [i for i in json.load(f) if i in ALL_RIDDLES]
        except (OSError, ValueError, TypeError):
            return []

    def learn(self, riddle: Riddle):
        if riddle.id not in self.notebook:
            self.notebook.append(riddle.id)
            with open(self.SAVE_DIR / "notebook.json", "w") as f:
                json.dump(self.notebook, f)

    def notebook_entries(self) -> List[Riddle]:
        """Everything learned so far, grouped by language"""
        return sorted((ALL_RIDDLES[i] for i in self.notebook), key=lambda r: (r.language, r.id))

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


class Showdown:
    """The final duel: Volkov asks SHOWDOWN_ROUNDS riddles. A wrong answer costs a heart;
    throwing a piece of evidence at him dodges the question. Lose your nerve and he escapes."""

    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.riddles = random.sample(VOLKOV_RIDDLES, SHOWDOWN_ROUNDS)
        self.index = 0

    @property
    def current(self) -> Optional[Riddle]:
        return None if self.finished else self.riddles[self.index]

    @property
    def lost(self) -> bool:
        return self.engine.state.sanity <= 0

    @property
    def finished(self) -> bool:
        return self.lost or self.index >= len(self.riddles)

    @property
    def won(self) -> bool:
        return self.index >= len(self.riddles) and not self.lost

    def answer(self, response: str) -> bool:
        riddle = self.current
        if self.engine.is_correct(riddle, response):
            self.engine.learn(riddle)
            self.engine.state.score += 30
            self.index += 1
            return True
        self.engine.state.sanity -= 1
        return False

    def dodge(self, item: str) -> bool:
        if not self.engine.spend_item(item):
            return False
        self.index += 1
        return True
