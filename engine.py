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

The riddles and the story live in data/riddles.toml and data/story.toml, so they
can be edited without touching the code. They are checked when the game starts.
"""

import difflib
import hashlib
import json
import math
import random
import re
import sys
import textwrap
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Tuple

try:
    import tomllib
except ImportError:  # Python older than 3.11
    try:
        import tomli as tomllib
    except ImportError:
        raise SystemExit("Noir Language Riddles needs Python 3.11 or newer "
                         "(or, on an older Python: pip install tomli).") from None

import art


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
    # "order":  put the shuffled `sequence` back in order; answer is the sequence joined by "|"
    kind: str = "choice"
    accepted: List[str] = field(default_factory=list)
    pairs: List[Tuple[str, str]] = field(default_factory=list)
    item_help: Optional[Tuple[str, str]] = None  # (evidence, extra help shown while you hold it)
    sequence: List[str] = field(default_factory=list)  # an order riddle's steps, first to last
    diagram: str = ""  # ASCII art shown above a choice riddle's options, e.g. a family tree with a ??? gap

    def display_answer(self) -> str:
        if self.kind == "match":
            return ", ".join(f"{left} = {right}" for left, right in self.pairs)
        if self.kind == "order":
            return " → ".join(self.sequence)
        return self.answer


@dataclass
class Location:
    id: str
    name: str
    description: str
    character: str
    greeting: str           # what the character says while you investigate
    riddle_ids: List[int]   # the pool: every riddle placed here but the lead, in the order they are asked
    lead_riddle: Optional[int] = None
    leads_to: Optional[str] = None
    lead_after: int = 0     # riddles to solve here before the lead appears
    lead_text: str = ""     # story beat when the lead is solved
    done_text: str = ""     # what the character says once the place is exhausted
    beats: List[Tuple[int, str]] = field(default_factory=list)  # (riddles solved here, what you learn)
    good_lines: List[str] = field(default_factory=list)  # reactions to a clean answer
    bad_lines: List[str] = field(default_factory=list)   # reactions to a slip
    present: Dict[str, str] = field(default_factory=dict)  # evidence shown -> what the character reveals
    riddles_per_case: int = 0        # how many of the pool a case asks (picked at random)
    riddles_per_daily_case: int = 0  # the same for the shorter daily case


# =============================================================================
# LOADING THE DATA FILES
# =============================================================================

# Next to this file, or inside the bundle when frozen with PyInstaller (--add-data "data:data")
DATA_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "data"


class DataError(ValueError):
    """A mistake in one of the data files, described so that a person can fix it"""


def read_toml(name: str) -> dict:
    """Parse data/<name>. Syntax errors come back with the line and column."""
    path = DATA_DIR / name
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except OSError as e:
        raise DataError(f"data/{name}: cannot open {path} ({e.strerror})") from None
    except tomllib.TOMLDecodeError as e:
        raise DataError(f"data/{name}: {e}") from None


def join_lines(text: str) -> str:
    """Text written over several lines inside triple quotes becomes one line again"""
    if "\n" not in text:
        return text
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


_REQUIRED = object()


class Fields:
    """Reads the fields of one entry in a data file, failing with a message that names the entry"""

    def __init__(self, table, where: str):
        if not isinstance(table, dict):
            raise DataError(f"{where}: should be a table of fields")
        self.table, self.where, self.seen = table, where, set()

    def fail(self, message: str):
        raise DataError(f"{self.where}: {message}")

    def get(self, key: str, default=_REQUIRED):
        self.seen.add(key)
        if key in self.table:
            return self.table[key]
        if default is _REQUIRED:
            typo = difflib.get_close_matches(key, [k for k in self.table if k not in self.seen], n=1, cutoff=0.8)
            self.fail(f"missing field '{key}'" + (f" (is '{typo[0]}' a typo?)" if typo else ""))
        return default

    def text(self, key: str, default=_REQUIRED, keep_lines: bool = False) -> Optional[str]:
        if key not in self.table and default is not _REQUIRED:
            return self.get(key, default)
        value = self.get(key)
        if not isinstance(value, str):
            self.fail(f"'{key}' should be text in quotes, not {value!r}")
        if not value.strip():
            self.fail(f"'{key}' is empty")
        return value if keep_lines else join_lines(value)

    def number(self, key: str, default=_REQUIRED, low: int = 0, high: Optional[int] = None) -> int:
        value = self.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool):
            self.fail(f"'{key}' should be a whole number, not {value!r}")
        if value < low or (high is not None and value > high):
            limits = f"between {low} and {high}" if high is not None else f"at least {low}"
            self.fail(f"'{key}' should be {limits}, not {value}")
        return value

    def texts(self, key: str, default=_REQUIRED) -> List[str]:
        if key not in self.table and default is not _REQUIRED:
            return self.get(key, default)
        value = self.get(key)
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            self.fail(f"'{key}' should be a list of texts in quotes, like [\"one\", \"two\"]")
        return [join_lines(v) for v in value]

    def tables(self, key: str) -> List[dict]:
        """An array of tables, written [[entry.key]] in the file"""
        value = self.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            self.fail(f"'{key}' should be written as [[...{key}]] sections")
        return value

    def finish(self):
        """Anything left over is a misspelt or misplaced field"""
        unknown = [key for key in self.table if key not in self.seen]
        if unknown:
            self.fail(f"unknown field '{unknown[0]}' (a typo?)")


def entries(doc: dict, key: str, filename: str) -> List[dict]:
    value = doc.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise DataError(f"{filename}: '{key}' entries should be written as [[{key}]] sections")
    return value


def check_known_sections(doc: dict, known: Tuple[str, ...], expected: str, filename: str):
    for key in doc:
        if key not in known:
            raise DataError(f"{filename}: unknown section or field '{key}' (expected {expected})")


# Fields that only some kinds of riddle have
KIND_FIELDS = {
    "choice": {"answer", "wrong_answers", "decoys", "diagram"},
    "type": {"answer", "accepted"},
    "match": {"pairs"},
    "order": {"sequence"},
}

DIAGRAM_WIDTH = 56  # fits the riddle panel of the full-screen version at its smallest (100 columns)


def clean_diagram(text: str, f: "Fields") -> str:
    """Keep a diagram's layout, minus blank lines around it, trailing spaces and common indentation"""
    if "\t" in text:
        f.fail("the diagram contains a tab; use spaces so the lines stay aligned")
    lines = [line.rstrip() for line in textwrap.dedent(text).split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        f.fail("'diagram' is empty")
    if max(len(line) for line in lines) > DIAGRAM_WIDTH:
        f.fail(f"the diagram is wider than {DIAGRAM_WIDTH} characters, so it would not fit on screen")
    return "\n".join(lines)


def build_riddle(table: dict, number: int, filename: str, story: bool) -> Tuple[Riddle, Optional[str]]:
    """One [[riddle]] or [[volkov_riddle]] table. Returns the riddle and its location id."""
    label = "riddle" if story else "volkov_riddle"
    rid = table.get("id") if isinstance(table, dict) else None
    where = (f"{filename}, {label} {rid}" if isinstance(rid, int)
             else f"{filename}, {label} number {number} in the file")
    f = Fields(table, where)
    rid = f.number("id", low=1)
    location = f.text("location") if story else None

    kind = f.text("kind", "choice")
    if kind not in KIND_FIELDS:
        f.fail(f"kind should be one of {', '.join(KIND_FIELDS)}, not '{kind}'")
    for key in set().union(*KIND_FIELDS.values()) - KIND_FIELDS[kind]:
        if key in table:
            f.fail(f"'{key}' does not belong in a {kind} riddle")

    r = Riddle(
        id=rid, language=f.text("language"), category=f.text("category"),
        text=f.text("text"), clue=f.text("clue"), answer="", wrong_answers=[],
        hint=f.text("hint") if story else f.text("hint", ""),
        explanation=f.text("explanation"), item=f.text("item", None),
        difficulty=f.number("difficulty", 1, low=1, high=3), kind=kind,
    )

    if kind == "choice":
        r.answer = f.text("answer")
        r.wrong_answers = f.texts("wrong_answers")
        r.decoys = f.texts("decoys")
        if not 1 <= len(r.wrong_answers) <= 3:
            f.fail("needs 1 to 3 wrong_answers (the answer and the wrong answers are shown together, "
                   "and there are only 4 number keys)")
        if len(r.decoys) != 2:
            f.fail(f"needs exactly 2 decoys (they replace wrong picks), not {len(r.decoys)}")
        seen = {r.answer.casefold()}
        for option in r.wrong_answers + r.decoys:
            if option.casefold() == r.answer.casefold():
                f.fail(f"the answer '{r.answer}' is also listed among its wrong_answers or decoys")
            if option.casefold() in seen:
                f.fail(f"'{option}' is listed twice among its wrong_answers and decoys")
            seen.add(option.casefold())
        if "diagram" in table:
            r.diagram = clean_diagram(f.text("diagram", keep_lines=True), f)
    elif kind == "type":
        r.answer = f.text("answer")
        r.accepted = f.texts("accepted", [])
        for spelling in [r.answer] + r.accepted:
            if not re.sub(r"[^a-z]", "", spelling.lower()):
                f.fail(f"the typed answer '{spelling}' has no letters a-z in it, so nobody could type it")
    elif kind == "match":
        pairs = f.get("pairs")
        if (not isinstance(pairs, list) or not all(isinstance(p, list) and len(p) == 2
                                                   and all(isinstance(s, str) and s.strip() for s in p)
                                                   for p in pairs)):
            f.fail('\'pairs\' should be a list of ["left", "right"] pairs')
        if not 2 <= len(pairs) <= 6:
            f.fail(f"needs 2 to 6 pairs, not {len(pairs)}")
        r.pairs = [(join_lines(left), join_lines(right)) for left, right in pairs]
        for side, words in (("left", [p[0] for p in r.pairs]), ("right", [p[1] for p in r.pairs])):
            if len({w.casefold() for w in words}) != len(words):
                f.fail(f"two pairs have the same {side}-hand word, so the letters would be ambiguous")
        r.answer = "|".join(right for _, right in r.pairs)
    elif kind == "order":
        r.sequence = f.texts("sequence")
        if not 3 <= len(r.sequence) <= 6:
            f.fail(f"needs 3 to 6 steps in its sequence, not {len(r.sequence)}")
        if len({step.casefold() for step in r.sequence}) != len(r.sequence):
            f.fail("two steps of the sequence are the same, so the order would be ambiguous")
        r.answer = "|".join(r.sequence)

    item_help = f.get("item_help", None)
    if item_help is not None:
        h = Fields(item_help, f"{where}, item_help")
        r.item_help = (h.text("evidence"), h.text("text"))
        h.finish()
    f.finish()
    return r, location


def scaled(needed: int, picked: int, per_case: int) -> int:
    """A count written for a full case (a beat's 'after', lead_after), shrunk in proportion
    when a case picks fewer riddles at the place, so every beat can still be heard"""
    if per_case <= 0 or picked >= per_case:
        return needed
    return math.ceil(needed * picked / per_case)


def build_location(table: dict, number: int, filename: str, placed: Dict[int, str]) -> Location:
    """One [[location]] table. `placed` maps each story riddle id to its location, in file order."""
    lid = table.get("id") if isinstance(table, dict) else None
    where = f"{filename}, location \"{lid}\"" if isinstance(lid, str) else f"{filename}, location number {number}"
    f = Fields(table, where)
    loc = Location(
        id=f.text("id"), name=f.text("name"), description=f.text("description"),
        character=f.text("character"), greeting=f.text("greeting"), riddle_ids=[],
        lead_riddle=f.number("lead_riddle", low=1) if "lead_riddle" in table else None,
        leads_to=f.text("leads_to", None), lead_after=f.number("lead_after", 0),
        lead_text=f.text("lead_text", ""), done_text=f.text("done_text"),
        good_lines=f.texts("good_lines"), bad_lines=f.texts("bad_lines"),
    )
    if not loc.good_lines or not loc.bad_lines:
        f.fail("needs at least one line in good_lines and in bad_lines")
    if loc.lead_riddle is None and ("leads_to" in table or "lead_text" in table or "lead_after" in table):
        f.fail("has leads_to / lead_text / lead_after but no lead_riddle")
    if loc.lead_riddle is not None and (not loc.leads_to or not loc.lead_text):
        f.fail("has a lead_riddle, so it also needs leads_to and lead_text")

    for n, beat in enumerate(f.tables("beat"), 1):
        b = Fields(beat, f"{where}, beat {n}")
        loc.beats.append((b.number("after", low=1), b.text("text")))
        b.finish()
    if [after for after, _ in loc.beats] != sorted({after for after, _ in loc.beats}):
        f.fail("beats should be in order of 'after', each with a different number")

    # The pool, and how much of it one case asks
    loc.riddle_ids = [rid for rid, at in placed.items() if at == loc.id and rid != loc.lead_riddle]
    pool = len(loc.riddle_ids)
    loc.riddles_per_case = f.number("riddles_per_case", pool)
    loc.riddles_per_daily_case = f.number("riddles_per_daily_case", loc.riddles_per_case)
    if loc.riddles_per_case > pool:
        f.fail(f"riddles_per_case is {loc.riddles_per_case}, but only {pool} riddles "
               f"(not counting the lead) are placed here in riddles.toml")
    if loc.riddles_per_daily_case > loc.riddles_per_case:
        f.fail("riddles_per_daily_case should not be more than riddles_per_case")
    if pool and not loc.riddles_per_daily_case:
        f.fail("riddles_per_case and riddles_per_daily_case should be at least 1")
    if loc.lead_after > loc.riddles_per_case:
        f.fail(f"lead_after is {loc.lead_after}, but a case only asks {loc.riddles_per_case} other riddles here")
    most = loc.riddles_per_case + (1 if loc.lead_riddle else 0)
    for after, _ in loc.beats:
        if after > most:
            f.fail(f"a beat comes after {after} riddles, but a case only asks {most} here")
    daily = [scaled(after, loc.riddles_per_daily_case, loc.riddles_per_case) for after, _ in loc.beats]
    if len(set(daily)) != len(daily):
        f.fail(f"with riddles_per_daily_case = {loc.riddles_per_daily_case}, two beats would come at once in "
               f"the daily case; raise it, or space the beats further apart")

    for n, shown in enumerate(f.tables("present"), 1):
        p = Fields(shown, f"{where}, present {n}")
        item = p.text("evidence")
        if item in loc.present:
            p.fail(f"the {item} is shown here twice")
        loc.present[item] = p.text("text")
        p.finish()

    # The art has to exist for the UIs to draw this place
    if loc.id not in art.SCENES:
        f.fail(f"art.py has no scene for '{loc.id}' (add one to SCENES)")
    if loc.id not in art.MAP_SPOTS:
        f.fail(f"art.py has no spot on the Berlin map for '{loc.id}' (add one to MAP_SPOTS)")
    if set(art.PORTRAITS.get(loc.character, {})) != {"neutral", "good", "bad"}:
        f.fail(f"art.py has no portrait for '{loc.character}' (PORTRAITS needs neutral, good and bad)")
    try:
        art.berlin_map({loc.id: f"[9] {loc.name}"})
    except IndexError:
        f.fail(f"the name '{loc.name}' is too long to fit on the travel map")
    f.finish()
    return loc


@dataclass
class GameData:
    riddles: List[Riddle]
    volkov_riddles: List[Riddle]
    locations: Dict[str, Location]  # in story order
    elena_question: str
    elena_options: List[str]
    elena_answer: str
    showdown_rounds: int
    showdown_intro: str


def load_game_data(riddles_doc: Optional[dict] = None, story_doc: Optional[dict] = None) -> GameData:
    """Read and check data/riddles.toml and data/story.toml (or already parsed copies of them)"""
    RF, SF = "data/riddles.toml", "data/story.toml"
    riddles_doc = read_toml("riddles.toml") if riddles_doc is None else riddles_doc
    story_doc = read_toml("story.toml") if story_doc is None else story_doc
    check_known_sections(riddles_doc, ("riddle", "volkov_riddle"), "[[riddle]] and [[volkov_riddle]]", RF)
    check_known_sections(story_doc, ("location", "elena", "showdown"), "[[location]], [elena] and [showdown]", SF)

    # --- Riddles ---
    story, placed = [], {}
    for n, table in enumerate(entries(riddles_doc, "riddle", RF), 1):
        r, where = build_riddle(table, n, RF, story=True)
        story.append(r)
        placed[r.id] = where
    volkov = [build_riddle(t, n, RF, story=False)[0]
              for n, t in enumerate(entries(riddles_doc, "volkov_riddle", RF), 1)]
    if not story or not volkov:
        raise DataError(f"{RF}: needs at least one [[riddle]] and one [[volkov_riddle]]")
    ids: Dict[int, Riddle] = {}
    items: Dict[str, int] = {}
    for r in story + volkov:
        if r.id in ids:
            raise DataError(f"{RF}: two riddles have id {r.id}; every riddle needs its own number")
        ids[r.id] = r
        if r.item:
            if r.item in items:
                raise DataError(f"{RF}, riddle {r.id}: the evidence '{r.item}' is already given by riddle {items[r.item]}")
            items[r.item] = r.id
    for r in story + volkov:
        if r.item_help and r.item_help[0] not in items:
            raise DataError(f"{RF}, riddle {r.id}: item_help needs the '{r.item_help[0]}', "
                            f"but no riddle gives that evidence")

    # --- Locations ---
    locations: Dict[str, Location] = {}
    for n, table in enumerate(entries(story_doc, "location", SF), 1):
        loc = build_location(table, n, SF, placed)
        if loc.id in locations:
            raise DataError(f"{SF}: two locations have the id \"{loc.id}\"")
        locations[loc.id] = loc
    if len(locations) < 2:
        raise DataError(f"{SF}: needs at least two [[location]] sections")

    for r in story:
        if placed[r.id] not in locations:
            raise DataError(f"{RF}, riddle {r.id}: unknown location \"{placed[r.id]}\" "
                            f"(the locations are {', '.join(locations)})")
    leads = {}
    for loc in locations.values():
        where = f"{SF}, location \"{loc.id}\""
        if loc.lead_riddle is not None:
            if loc.lead_riddle not in placed:
                raise DataError(f"{where}: lead_riddle {loc.lead_riddle} is not a [[riddle]] in {RF}")
            if placed[loc.lead_riddle] != loc.id:
                raise DataError(f"{where}: its lead_riddle {loc.lead_riddle} is placed at "
                                f"\"{placed[loc.lead_riddle]}\" in {RF}; it should say location = \"{loc.id}\"")
            if loc.leads_to not in locations or loc.leads_to == loc.id:
                raise DataError(f"{where}: leads_to \"{loc.leads_to}\" is not another location")
            leads[loc.id] = loc.leads_to
        for item in loc.present:
            if item not in items:
                raise DataError(f"{where}: shows the '{item}', but no riddle gives that evidence")

    # Every place must be reachable by following leads from the first one
    order = list(locations)
    reached, here = [order[0]], order[0]
    while here in leads and leads[here] not in reached:
        here = leads[here]
        reached.append(here)
    for loc_id in order:
        if loc_id not in reached:
            raise DataError(f"{SF}: no chain of leads from \"{order[0]}\" reaches \"{loc_id}\"")

    # --- The finale ---
    elena = Fields(story_doc.get("elena", {}), f"{SF}, [elena]")
    question, options, answer = elena.text("question"), elena.texts("options"), elena.text("answer")
    elena.finish()
    if answer not in options:
        elena.fail(f"the answer \"{answer}\" is not one of the options")
    if options[0] == answer:
        elena.fail("the answer should not be the first option, which the menu highlights")
    if len(set(options)) != len(options) or not 2 <= len(options) <= 9:
        elena.fail("needs 2 to 9 different options")
    showdown = Fields(story_doc.get("showdown", {}), f"{SF}, [showdown]")
    rounds = showdown.number("rounds", low=1, high=len(volkov))
    intro = showdown.text("intro")
    showdown.finish()

    return GameData(story, volkov, locations, question, options, answer, rounds, intro)


try:
    _DATA = load_game_data()
except DataError as error:
    raise SystemExit(f"Noir Language Riddles could not start, because of a mistake in the game data:\n  {error}") from None

RIDDLES = _DATA.riddles
# The final showdown: Volkov picks SHOWDOWN_ROUNDS of these. They don't count toward the case.
VOLKOV_RIDDLES = _DATA.volkov_riddles
ALL_RIDDLES = {r.id: r for r in RIDDLES + VOLKOV_RIDDLES}
SHOWDOWN_ROUNDS = _DATA.showdown_rounds
SHOWDOWN_INTRO = _DATA.showdown_intro

LOCATIONS: Dict[str, Location] = _DATA.locations
STORY_ORDER = list(LOCATIONS)  # the order of [[location]] in story.toml

# The final question: where is Elena? The answer is pieced together from the beats.
ELENA_QUESTION = _DATA.elena_question
ELENA_OPTIONS = _DATA.elena_options
ELENA_ANSWER = _DATA.elena_answer
START_LOCATION = STORY_ORDER[0]    # the case starts at the first location...
FINAL_LOCATION = STORY_ORDER[-1]   # ...and ends with Volkov at the last


def seeded_sample(items: list, count: int, seed: str) -> list:
    """`count` of the items, always the same ones for the same seed, on any computer or Python version"""
    return sorted(items, key=lambda item: hashlib.sha256(f"{seed}/{item}".encode()).hexdigest())[:count]


def pick_riddles(seed: Optional[str] = None, daily: bool = False) -> Dict[str, List[int]]:
    """The riddles one case asks at each place (leads not included): a handful of the pool,
    at random or fixed by a seed, asked in pool order"""
    selection = {}
    for loc in LOCATIONS.values():
        count = loc.riddles_per_daily_case if daily else loc.riddles_per_case
        if seed is None:
            chosen = random.sample(loc.riddle_ids, count)
        else:
            chosen = seeded_sample(loc.riddle_ids, count, f"{seed}/{loc.id}")
        selection[loc.id] = [rid for rid in loc.riddle_ids if rid in chosen]
    return selection


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
    selection: Dict[str, List[int]] = field(default_factory=pick_riddles)  # this case's riddles at each place


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

    def __init__(self, save_dir: Optional[Path] = None):
        self.state = GameState()
        self.riddles = {r.id: r for r in RIDDLES}
        self.locations = LOCATIONS
        if save_dir is not None:
            self.SAVE_DIR = Path(save_dir)  # e.g. a private folder per web session
        self.SAVE_DIR.mkdir(parents=True, exist_ok=True)
        self.notebook = self._load_notebook()

    # --- Queries -------------------------------------------------------------

    def location(self, loc_id: Optional[str] = None) -> Location:
        return self.locations[loc_id or self.state.current_location]

    def riddles_at(self, loc_id: str) -> List[int]:
        """This case's riddles at a place: its pick from the pool, then the lead"""
        loc = self.locations[loc_id]
        return self.state.selection.get(loc_id, []) + ([loc.lead_riddle] if loc.lead_riddle else [])

    def case_riddles(self) -> List[int]:
        """Every riddle this case asks, in story order"""
        return [rid for loc_id in STORY_ORDER for rid in self.riddles_at(loc_id)]

    def solved_count(self) -> int:
        return sum(1 for rid in self.case_riddles() if rid in self.state.solved_riddles)

    def needed(self, loc_id: str, count: int) -> int:
        """A beat's or a lead's count, shrunk when this case asks fewer riddles here than a full case"""
        return scaled(count, len(self.state.selection.get(loc_id, [])), self.locations[loc_id].riddles_per_case)

    def progress(self, loc_id: str) -> tuple:
        """(solved, total) for a location"""
        ids = self.riddles_at(loc_id)
        return sum(1 for i in ids if i in self.state.solved_riddles), len(ids)

    def lead_available(self, loc_id: str) -> bool:
        loc = self.locations[loc_id]
        if not loc.lead_riddle:
            return False
        solved_here = sum(1 for i in self.state.selection.get(loc_id, []) if i in self.state.solved_riddles)
        return solved_here >= self.needed(loc_id, loc.lead_after)

    def current_riddle(self) -> Optional[Riddle]:
        """The lead comes first once it is available, then the rest in order"""
        loc = self.location()
        solved = self.state.solved_riddles
        if self.lead_available(loc.id) and loc.lead_riddle not in solved:
            return self.riddles[loc.lead_riddle]
        for rid in self.state.selection.get(loc.id, []):
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
        """The right-hand column of a match riddle, or the steps of an order riddle, shuffled"""
        if riddle.kind == "order":
            steps = list(riddle.sequence)
            while steps == riddle.sequence:  # never hand over the answer already in order
                random.shuffle(steps)
            return steps
        rights = [right for _, right in riddle.pairs]
        random.shuffle(rights)
        return rights

    def match_response(self, riddle: Riddle, shown: List[str], letters: str) -> Optional[str]:
        """Turn typed letters (e.g. 'BCA') into an answer string, or None if they don't make sense"""
        letters = re.sub(r"[^A-Za-z]", "", letters).upper()
        indexes = [ord(ch) - ord("A") for ch in letters]
        if len(indexes) != len(shown) or sorted(indexes) != list(range(len(shown))):
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
        return [text for after, text in self.locations[loc_id].beats if solved >= self.needed(loc_id, after)]

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
        """Evidence this case can give"""
        return sum(1 for rid in self.case_riddles() if self.riddles[rid].item)

    def can_confront(self) -> bool:
        """Volkov can be confronted once the detective reaches his archive"""
        return self.state.current_location == FINAL_LOCATION

    def is_game_over(self) -> bool:
        return self.state.sanity <= 0

    def all_riddles_solved(self) -> bool:
        """Every riddle of this case (not the whole pool) is solved"""
        return self.solved_count() >= len(self.case_riddles())

    def get_ending(self, elena_guess: Optional[str], volkov_beaten: bool) -> tuple:
        """Determine ending from progress, the showdown, and where the detective looked for Elena"""
        total_riddles = len(self.case_riddles())
        solved = self.solved_count()
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
            state.selection = self.repair_selection(data.get("selection"), state.solved_riddles)
            # Saves from before locations were unlockable: open everything already visited
            if "unlocked_locations" not in data:
                state.unlocked_locations = list(dict.fromkeys([START_LOCATION] + state.visited_locations + [state.current_location]))
            if state.current_location not in self.locations:
                state.current_location = START_LOCATION
            self.state = state
            return True
        except (OSError, ValueError, TypeError):
            return False

    @staticmethod
    def repair_selection(saved, solved: List[int]) -> Dict[str, List[int]]:
        """A saved case's riddles, checked against the pools as they are now. A place missing from
        the save (a save from before pools, or a new place) keeps the riddles already solved there
        and gets a fresh random pick for the rest."""
        saved = saved if isinstance(saved, dict) else {}
        selection = {}
        for loc in LOCATIONS.values():
            kept = saved.get(loc.id)
            if isinstance(kept, list):
                selection[loc.id] = [rid for rid in loc.riddle_ids if rid in kept]  # riddles since removed drop out
                continue
            done = [rid for rid in loc.riddle_ids if rid in solved]
            rest = [rid for rid in loc.riddle_ids if rid not in done]
            extra = random.sample(rest, max(0, min(len(rest), loc.riddles_per_case - len(done))))
            selection[loc.id] = [rid for rid in loc.riddle_ids if rid in done or rid in extra]
        return selection

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
