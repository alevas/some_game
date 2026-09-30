#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
Full-screen ASCII art version (needs Textual: pip install -r requirements.txt)

Run with: python tui.py
"""

import os
import random
import signal
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

import art
from engine import (GameEngine, AnswerResult, Riddle, Showdown, STORY_ORDER, LOCATIONS, ALL_RIDDLES,
                    ELENA_QUESTION, ELENA_OPTIONS, FINAL_LOCATION, SHOWDOWN_INTRO)
from engine import GameState, Question
from tips import TIPS, Tips


AMBER = "#e0b050"
PAPER = "#d8d0c0"
SMOKE = "grey50"
BLOOD = "#c0392b"
MOSS = "#7fae6b"
VIOLET = "#c49bd8"
RAIN = "#5b6b7a"

TRUST_COLORS = {"distrustful": BLOOD, "guarded": SMOKE, "trusting": MOSS}


def heading(text: str) -> Text:
    return Text(text.upper(), style=f"bold {AMBER}")


def sanity_text(s: GameState) -> Text:
    t = Text()
    for i in range(s.max_sanity):
        t.append("♥" if i < s.sanity else "♡", style=BLOOD if i < s.sanity else SMOKE)
    return t


# =============================================================================
# ATMOSPHERE
# =============================================================================

class RainScene(Static):
    """ASCII art with rain falling through its empty space"""

    DROPS = "|'"

    def __init__(self, scene: str, density: float = 0.12, **kwargs):
        super().__init__(**kwargs)
        # The static art has painted-on rain; the animation replaces it
        self.base = [list(line) for line in scene.replace("'", " ").replace(",", " ").split("\n")]
        self.width = max(len(line) for line in self.base)
        self.density = density
        self.drops: List[List[int]] = []  # [row, col]

    def on_mount(self):
        self.render_frame()
        # Render's free instance has a tenth of a CPU; the animation alone would use it all
        if not os.environ.get("RENDER"):
            self.set_interval(0.09, self.tick)

    def tick(self):
        for drop in self.drops:
            drop[0] += 1
        self.drops = [d for d in self.drops if d[0] < len(self.base)]
        for col in range(self.width):
            if random.random() < self.density / 4:
                self.drops.append([0, col])
        self.render_frame()

    def render_frame(self):
        grid = [row + [" "] * (self.width - len(row)) for row in self.base]
        rain = set()
        for row, col in self.drops:
            if grid[row][col] == " ":
                grid[row][col] = random.choice(self.DROPS)
                rain.add((row, col))
        text = Text()
        for r, row in enumerate(grid):
            for c, ch in enumerate(row):
                text.append(ch, style=RAIN if (r, c) in rain else SMOKE)
            text.append("\n")
        self.update(text)


class Typewriter(Static):
    """Reveals new text a few characters at a time; repeated text appears instantly"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.full = Text()
        self.shown = 0
        self.timer = None

    def say(self, text: Text):
        if text.plain == self.full.plain:
            self.full = text
            self.update(text if self.shown >= len(text) else text[:self.shown])
            return
        self.full, self.shown = text, 0
        if self.timer:
            self.timer.stop()
        self.timer = self.set_interval(0.015, self.tick)

    def tick(self):
        self.shown += 3
        self.update(self.full[:self.shown])
        if self.shown >= len(self.full):
            self.timer.stop()
            self.timer = None


class AnswerInput(Input):
    """Text answer box. Escape steps out of it so single-key commands work again."""

    BINDINGS = [Binding("escape", "leave", "Commands", show=False)]

    def action_leave(self):
        self.screen.set_focus(None)
        self.screen.refresh_bindings()


# =============================================================================
# MODALS
# =============================================================================

class ChoiceModal(ModalScreen[Optional[str]]):
    """A small boxed menu. Dismisses with the chosen option id, or None."""

    BINDINGS = [Binding("escape", "cancel", "Back")]

    def __init__(self, title: str, choices: List[Tuple[str, str, bool]], above: Optional[Text] = None):
        super().__init__()
        self.title_text = title
        self.choices = choices  # (id, label, enabled)
        self.above = above      # optional art shown over the options

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog wide" if self.above else "dialog"):
            yield Static(heading(self.title_text), classes="dialog-title")
            if self.above:
                yield Static(self.above)
            yield OptionList(*[Option(label, id=cid, disabled=not enabled)
                               for cid, label, enabled in self.choices])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.dismiss(event.option.id)

    def action_cancel(self):
        self.dismiss(None)


class TextModal(ModalScreen[None]):
    """A scrollable page of text: case notes, the etymology notebook"""

    BINDINGS = [Binding("escape,enter", "close", "Close")]

    def __init__(self, title: str, body: Text):
        super().__init__()
        self.title_text, self.body = title, body

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog page"):
            yield Static(heading(self.title_text))
            with VerticalScroll():
                yield Static(self.body)
            yield Static(Text("Enter or Esc to close", style=SMOKE))

    def action_close(self):
        self.dismiss(None)


class EndScreen(ModalScreen[None]):
    """Ending or game over card"""

    BINDINGS = [Binding("enter", "done", "Back to title")]

    def __init__(self, engine: GameEngine, title: str, text: str, triumph: bool, dead: bool = False):
        super().__init__()
        self.engine, self.end_title, self.text = engine, title, text
        self.triumph, self.dead = triumph, dead

    def compose(self) -> ComposeResult:
        s = self.engine.state
        color = BLOOD if self.dead else AMBER
        body = Text()
        body.append(art.GAME_OVER if self.dead else art.LOGO, style=color)
        body.append(f"\n{self.end_title}\n\n", style=f"bold {color}")
        body.append(f"{self.text}\n\n", style=PAPER)
        body.append(f"Riddles solved   {len(s.solved_riddles)}/{len(self.engine.riddles)}\n", style=SMOKE)
        body.append(f"Evidence kept    {len(s.inventory)}/{self.engine.total_items()}\n", style=SMOKE)
        body.append(f"Final score      {s.score}\n\n", style=SMOKE)
        body.append("All our words are connected." if self.triumph else "The Babel Society wins. For now.",
                    style=f"italic {PAPER}")
        body.append("\n\nPress Enter", style=SMOKE)
        with Vertical(classes="dialog end"):
            yield Static(body)

    def action_done(self):
        self.dismiss(None)


class TipModal(ModalScreen[None]):
    """A first-time tip in the corner. Enter or Esc puts it away; x turns tips off."""

    BINDINGS = [Binding("enter,escape", "close", "Got it"), Binding("x", "off", "No more tips")]

    def __init__(self, key: str):
        super().__init__()
        self.key = key

    def compose(self) -> ComposeResult:
        tip = TIPS[self.key]
        with Vertical(classes="dialog tip"):
            yield Static(Text(f"TIP · {tip['title'].upper()}", style=f"bold {VIOLET}"), classes="dialog-title")
            yield Static(Text(tip["tui"], style=PAPER))
            yield Static(Text("\nEnter: got it    x: no more tips", style=SMOKE))

    def action_close(self):
        self.dismiss(None)

    def action_off(self):
        self.app.tips.set_enabled(False)
        self.app.notify("Tips are off. Turn them back on from the menu (m).")
        self.dismiss(None)


class InterrogationModal(ModalScreen[Optional[Tuple[str, str]]]):
    """Questioning the character here. Pick a question, then press the answer with evidence
    to break a lie. Dismisses with their last (mood, line), or None if nothing was said."""

    BINDINGS = [
        Binding("p", "press", "Press with evidence"),
        Binding("n", "notes", "Notes"),
        Binding("escape", "leave", "Leave"),
    ]

    def __init__(self, engine: GameEngine):
        super().__init__()
        self.engine = engine
        self.talk = engine.interrogation()
        self.question: Optional[Question] = None  # the answer on the table
        self.mood = "neutral"
        self.line = self.talk.opening
        self.aside: Optional[Text] = None         # what just happened, under the line
        self.spoke = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog grill"):
            yield Static(id="grill-status", classes="dialog-title")
            with Horizontal(id="grill-talk"):
                yield Static(id="grill-portrait")
                yield Typewriter(id="grill-line")
            yield OptionList(id="grill-options")
            yield Static(Text("Enter: ask    p: press that answer with evidence    n: notes    Esc: leave",
                              style=SMOKE), classes="grill-keys")

    def on_mount(self):
        self.render_view()

    def can_press(self) -> bool:
        e = self.engine
        return (self.question is not None and not e.is_caught(self.question)
                and bool(e.state.inventory) and not e.refuses())

    def render_view(self):
        e, who = self.engine, self.talk.character
        label = e.trust_label(who)
        status = heading(f"Questioning {who}")
        status.append("    trust ", style=SMOKE)
        status.append(label, style=TRUST_COLORS[label])
        status.append("    sanity ", style=SMOKE)
        status.append_text(sanity_text(e.state))
        self.query_one("#grill-status", Static).update(status)
        self.query_one("#grill-portrait", Static).update(Text(art.PORTRAITS[who][self.mood], style=PAPER))
        line = Text()
        line.append(f'\n"{self.line}"', style=f"italic {PAPER}")
        if self.aside:
            line.append("\n\n")
            line.append_text(self.aside)
        self.query_one("#grill-line", Typewriter).say(line)

        # New questions are marked •, broken lies ✓
        refusing = e.refuses()
        options = [Option(f"{'✓' if e.is_caught(q) else ' ' if e.was_asked(q) else '•'} {q.ask}",
                          id=f"q:{q.id}", disabled=refusing) for q in e.questions()]
        if e.locked_questions():
            options.append(Option(f"  ({e.locked_questions()} more as you solve riddles here)", disabled=True))
        options += [None,
                    Option("Press that answer with evidence  (p)", id="press", disabled=not self.can_press()),
                    Option("Leave  (Esc)", id="leave")]
        box = self.query_one("#grill-options", OptionList)
        keep = box.highlighted_option.id if box.highlighted_option else None
        box.set_options(options)
        ids = [o.id for o in box.options]
        if refusing:
            keep = "leave"
        elif keep is None or keep not in ids:
            keep = next(i for i in ids if i)  # the first question
        box.highlighted = ids.index(keep)
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple) -> Optional[bool]:
        if action == "press":
            return self.can_press()
        return True

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        choice = event.option.id
        if choice == "leave":
            self.action_leave()
        elif choice == "press":
            self.action_press()
        elif choice and choice.startswith("q:"):
            self.question = next(q for q in self.engine.questions() if q.id == choice[2:])
            self.mood, self.line, self.aside = "neutral", self.engine.ask(self.question.id), None
            self.spoke = True
            self.render_view()

    def action_press(self):
        if self.can_press():
            self.app.push_screen(ChoiceModal("Which evidence contradicts that?",
                                             [(item, item, True) for item in self.engine.state.inventory]),
                                 self._pressed)

    def _pressed(self, item: Optional[str]):
        if not item:
            return
        e, who = self.engine, self.talk.character
        result = e.press(self.question.id, item)
        self.mood, self.line, self.spoke = ("good" if result.broken else "bad"), result.line, True
        if result.broken:
            perks = "a free hint (h) this case"
            if self.talk.blessing:
                perks += ", and a blessing before the showdown"
            self.aside = Text(f"The lie breaks. Added to your case notes.\n{who} trusts you now: {perks}.",
                              style=MOSS)
        else:
            self.aside = Text(f"Wrong evidence. {who} trusts you less." + ("  -1 ♥" if result.heart_lost else ""),
                              style=BLOOD)
            if result.clammed_up:
                self.aside.append(f"\n{who} clams up. {e.mend_advice()}", style=SMOKE)
        self.render_view()

    def action_notes(self):
        self.app.push_screen(notes_page(self.engine))

    def action_leave(self):
        self.dismiss((self.mood, self.line) if self.spoke else None)


def notes_page(engine: GameEngine) -> TextModal:
    body = Text()
    current = None
    for place, note in engine.case_notes():
        if place != current:
            body.append(f"\n{place.upper()}\n", style=f"bold {AMBER}")
            current = place
        body.append(f" · {note}\n", style=PAPER)
    if current is None:
        body.append("\nNothing yet. Solve riddles and people will start talking.\n", style=SMOKE)
    return TextModal("Case notes", body)


def notebook_page(engine: GameEngine) -> TextModal:
    """Every explanation you've unlocked, in any case you've played"""
    entries = engine.notebook_entries()
    body = Text()
    body.append(f"\n{len(entries)} of {len(ALL_RIDDLES)} entries. Solve riddles to fill it in; it carries over between cases.\n",
                style=SMOKE)
    current = None
    for r in entries:
        if r.language != current:
            body.append(f"\n{r.language.upper()}\n", style=f"bold {AMBER}")
            current = r.language
        body.append(f" {r.clue}", style=f"bold {VIOLET}")
        body.append(f"  →  {r.display_answer()}\n", style=f"bold {PAPER}")
        body.append(f"   {r.explanation}\n", style=PAPER)
    return TextModal("Etymology notebook", body)


def load_modal(engine: GameEngine) -> ChoiceModal:
    return ChoiceModal("Load from slot",
                       [(str(i), f"Slot {i}: {label}", exists) for i, exists, label in engine.get_save_slots()])


# =============================================================================
# TITLE
# =============================================================================

class TitleScreen(Screen):
    def compose(self) -> ComposeResult:
        title = Text()
        title.append(art.LOGO, style=f"bold {AMBER}")
        title.append("\n   LANGUAGE RIDDLES: THE BABEL CONSPIRACY", style=f"bold {PAPER}")
        tagline = Text()
        tagline.append("   Berlin, 1947. A linguist has disappeared.\n", style=SMOKE)
        tagline.append("   Solve etymological riddles to uncover the truth.", style=SMOKE)
        with Vertical(id="title-box"):
            yield Static(title)
            yield RainScene(art.TITLE_SCENE)
            yield Static(tagline)
            yield OptionList(
                Option("New case", id="new"),
                Option("Continue", id="continue"),
                Option("Load a saved case", id="load"),
                Option("Etymology notebook", id="notebook"),
                Option("Quit", id="quit"),
                id="title-menu",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        engine = self.app.engine
        choice = event.option.id
        if choice == "new":
            engine.new_game()
            self.app.switch_screen(GameScreen())
        elif choice == "continue":
            if engine.load_game(0):
                self.app.switch_screen(GameScreen())
            else:
                self.notify("No case in progress.", severity="warning")
        elif choice == "load":
            self.app.push_screen(load_modal(engine), self._loaded)
        elif choice == "notebook":
            self.app.push_screen(notebook_page(engine))
        elif choice == "quit":
            self.app.exit()

    def _loaded(self, slot: Optional[str]):
        if slot and self.app.engine.load_game(int(slot)):
            self.app.switch_screen(GameScreen())


# =============================================================================
# GAME
# =============================================================================

class GameScreen(Screen):
    BINDINGS = [
        Binding("1", "answer(0)", "Answer", show=False),
        Binding("2", "answer(1)", "Answer", show=False),
        Binding("3", "answer(2)", "Answer", show=False),
        Binding("4", "answer(3)", "Answer", show=False),
        Binding("enter", "next", "Continue"),
        Binding("g", "go", "Follow lead"),
        Binding("h", "hint", "Hint"),
        Binding("e", "evidence", "Evidence"),
        Binding("i", "interrogate", "Ask"),
        Binding("n", "notes", "Notes"),
        Binding("b", "notebook", "Notebook"),
        Binding("t", "travel", "Travel"),
        Binding("v", "confront", "Confront Volkov"),
        Binding("m,escape", "menu", "Menu"),
    ]

    def __init__(self):
        super().__init__()
        self.mode = "question"                  # "question" or "result"
        self.riddle: Optional[Riddle] = None
        self.options: List[str] = []            # choice options, or the right column of a match
        self.eliminated: List[str] = []         # wrong answers given to this riddle
        self.hint_shown = False
        self.last: Optional[AnswerResult] = None
        self.mood = "neutral"                   # portrait expression
        self.line: Optional[Text] = None        # what the character is saying right now
        self.showdown: Optional[Showdown] = None
        self.elena_guess: Optional[str] = None

    @property
    def engine(self) -> GameEngine:
        return self.app.engine

    def compose(self) -> ComposeResult:
        with Horizontal():
            with VerticalScroll(id="main"):
                yield Static(id="scene")
                with Horizontal(id="talk"):
                    yield Static(id="portrait")
                    yield Typewriter(id="dialogue")
                with Vertical(id="riddle-box"):
                    yield Static(id="riddle")
                    yield AnswerInput(placeholder="Type here and press Enter", id="answer")
            yield Static(id="sidebar")
        yield Footer()

    def on_mount(self):
        self.new_question()

    # --- Helpers -------------------------------------------------------------

    @property
    def asking(self) -> bool:
        return self.mode == "question" and self.riddle is not None

    @property
    def typing(self) -> bool:
        """The current riddle is answered in the text box"""
        return self.asking and self.riddle.kind in ("type", "match")

    def say(self, text: str, mood: str = "neutral"):
        self.mood = mood
        self.line = Text(f'"{text}"', style=f"italic {PAPER}")

    def react(self, good: bool):
        loc = LOCATIONS[FINAL_LOCATION] if self.showdown else self.engine.location()
        lines = loc.good_lines if good else loc.bad_lines
        self.say(random.choice(lines), "good" if good else "bad")

    # --- Rendering -----------------------------------------------------------

    def new_question(self):
        self.mode = "question"
        self.riddle = self.showdown.current if self.showdown else self.engine.current_riddle()
        self.options = []
        if self.riddle and self.riddle.kind == "choice":
            self.options = self.engine.shuffled_options(self.riddle)
        elif self.riddle and self.riddle.kind == "match":
            self.options = self.engine.match_options(self.riddle)
        self.eliminated = []
        self.hint_shown = False
        self.last = None
        self.mood, self.line = "neutral", None
        self.render_all()

    def render_all(self):
        loc = LOCATIONS[FINAL_LOCATION] if self.showdown else self.engine.location()

        if self.showdown:
            scene = Text(art.SHOWDOWN_SCENE, style=SMOKE)
            scene.append("\nTHE SHOWDOWN", style=f"bold {BLOOD}")
            scene.append(f"   round {min(self.showdown.index + 1, len(self.showdown.riddles))} of "
                         f"{len(self.showdown.riddles)}\n", style=SMOKE)
            scene.append("A wrong answer costs a heart. Press e to throw evidence at him and dodge a question.",
                         style=PAPER)
        else:
            scene = Text(art.SCENES[loc.id], style=SMOKE)
            scene.append(f"\n{loc.name.upper()}\n", style=f"bold {AMBER}")
            scene.append(loc.description, style=PAPER)
        self.query_one("#scene", Static).update(scene)

        self.query_one("#portrait", Static).update(Text(art.PORTRAITS[loc.character][self.mood], style=PAPER))
        dialogue = Text(f"\n{loc.character}", style=f"bold {AMBER}")
        if not self.showdown and self.engine.interrogation(loc.id):
            trust = self.engine.trust_label(loc.character)
            dialogue.append(f"  ·  {trust}", style=TRUST_COLORS[trust])
        dialogue.append("\n")
        dialogue.append_text(self.dialogue_line())
        self.query_one("#dialogue", Typewriter).say(dialogue)

        self.query_one("#riddle", Static).update(
            self.render_result() if self.mode == "result" else self.render_question())
        box = self.query_one("#answer", AnswerInput)
        box.display = self.typing
        if self.typing and not box.has_focus:
            box.value = ""
            box.focus()
        elif not self.typing and box.has_focus:
            self.set_focus(None)  # a hidden box would still swallow Enter
        self.query_one("#sidebar", Static).update(self.render_sidebar())
        self.refresh_bindings()
        self.call_after_refresh(self.maybe_tip)

    def dialogue_line(self) -> Text:
        """Most important line wins: a new lead, a new beat, what was just said, then small talk"""
        loc = self.engine.location()
        if self.last and self.last.unlocked:
            return Text(loc.lead_text, style=f"italic {PAPER}")
        if self.last and self.last.beat:
            t = Text(f'"{self.last.beat}"', style=f"italic {PAPER}")
            t.append("\n(added to your case notes)", style=SMOKE)
            return t
        if self.line:
            return self.line
        if self.showdown:
            return Text(SHOWDOWN_INTRO, style=f"italic {PAPER}")
        if self.riddle is None:
            return Text(f'"{loc.done_text}"', style=f"italic {PAPER}")
        beats = self.engine.beats_unlocked(loc.id)
        return Text(f'"{beats[-1] if beats else loc.greeting}"', style=f"italic {PAPER}")

    def render_question(self) -> Text:
        t = Text()
        if not self.riddle:
            t.append("You've turned this place inside out.\n\n", style=PAPER)
            t.append("Press t to follow another lead, e to show someone your evidence, n to review your notes.",
                     style=SMOKE)
            if self.engine.can_confront():
                t.append("\nPress v to confront Volkov.", style=BLOOD)
            return t

        r = self.riddle
        if self.showdown:
            label = "VOLKOV ASKS"
        else:
            label = "LEAD" if r.id == self.engine.location().lead_riddle else "RIDDLE"
        t.append(f"{label}  ·  {r.language}  ·  {r.category}\n", style=f"bold {AMBER}")
        t.append(f"Clue: {r.clue}\n\n", style=f"bold {VIOLET}")
        t.append(f"{r.text}\n\n", style=PAPER)

        if r.kind == "choice":
            for i, option in enumerate(self.options):
                t.append(f"  [{i + 1}] ", style=AMBER)
                t.append(f"{option}\n", style=PAPER)
        elif r.kind == "match":
            width = max(len(left) for left, _ in r.pairs) + 4
            for i, (left, _) in enumerate(r.pairs):
                t.append(f"  {i + 1}. {left:<{width}}", style=PAPER)
                t.append(f"{chr(ord('A') + i)}. ", style=AMBER)
                t.append(f"{self.options[i]}\n", style=PAPER)
            t.append("\nType the letters for 1, 2, 3 in order (e.g. BCA). Esc for commands.", style=SMOKE)
        else:
            t.append("Type the word and press Enter. Esc for commands.", style=SMOKE)

        help_text = self.engine.item_help(r)
        if help_text:
            t.append(f"\n{help_text}", style=MOSS)
        if self.eliminated:
            s = self.engine.state
            blur = " The answers blur and rearrange." if r.kind != "type" else ""
            t.append(f"\n✗ Wrong.{blur} Sanity {s.sanity}/{s.max_sanity}.\n", style=BLOOD)
            t.append(f"{'Ruled out' if r.kind == 'choice' else 'Tried'}: {', '.join(self.eliminated)}",
                     style=f"strike {SMOKE}")
        if self.hint_shown:
            t.append(f"\nHint: {r.hint}", style=VIOLET)
        return t

    def render_result(self) -> Text:
        r = self.riddle
        t = Text()
        t.append(f"✓ CORRECT  ·  {r.display_answer()}\n\n", style=f"bold {MOSS}")
        t.append(f"{r.explanation}\n", style=PAPER)
        if self.showdown:
            if self.showdown.finished:
                t.append("\nVolkov has run out of questions. Press Enter.", style=f"bold {AMBER}")
            else:
                t.append("\nVolkov narrows his eyes. Press Enter for his next question.", style=SMOKE)
            return t

        res = self.last
        if r.item:
            if res.item_gained:
                t.append(f"\nEvidence collected: {r.item}", style=MOSS)
            else:
                t.append(f"\nYou fumbled earlier. The {r.item} slipped through your fingers.", style=SMOKE)
        if res.streak_bonus:
            t.append(f"\nStreak x{self.engine.state.streak}: +{res.streak_bonus} bonus", style=AMBER)
        if res.heart_restored:
            t.append("\nThree clean answers in a row steady your nerve. +1 ♥", style=BLOOD)
        t.append("\n")
        if res.unlocked:
            t.append(f"\nNEW LEAD: {LOCATIONS[res.unlocked].name}\n", style=f"bold {AMBER}")
            t.append("Press g to go now, or Enter to keep digging here.", style=SMOKE)
        else:
            t.append("\nPress Enter to continue.", style=SMOKE)
        return t

    def render_sidebar(self) -> Text:
        s = self.engine.state
        t = Text()
        t.append("CASE FILE\n\n", style=f"bold {AMBER}")
        t.append("Sanity  ", style=SMOKE)
        for i in range(s.max_sanity):
            t.append("♥" if i < s.sanity else "♡", style=BLOOD if i < s.sanity else SMOKE)
        t.append(f"\nScore   {s.score}\n", style=SMOKE)
        t.append("Streak  ", style=SMOKE)
        # Progress toward the next heart
        t.append("◆" * (s.streak % 3) + "◇" * (3 - s.streak % 3), style=AMBER)
        t.append("\n\n")

        t.append(f"EVIDENCE {len(s.inventory)}", style=f"bold {AMBER}")
        t.append("  (e: show or use)\n", style=SMOKE)
        for item in s.inventory:
            t.append(f" · {item}\n", style=PAPER)
        if not s.inventory:
            t.append(" nothing yet\n", style=SMOKE)

        t.append("\nLEADS\n", style=f"bold {AMBER}")
        for loc_id in STORY_ORDER:
            if loc_id in s.unlocked_locations:
                solved, total = self.engine.progress(loc_id)
                here = loc_id == s.current_location
                name = LOCATIONS[loc_id].name
                t.append(f"{'>' if here else ' '} {name:<20}{solved:>2}/{total}\n",
                         style=f"bold {PAPER}" if here else PAPER)
            else:
                t.append("  ???\n", style=SMOKE)
        t.append(f"\nNOTES {len(self.engine.case_notes())}", style=f"bold {AMBER}")
        t.append("  (n)\n", style=SMOKE)
        t.append(f"NOTEBOOK {len(self.engine.notebook)}/{len(ALL_RIDDLES)}", style=f"bold {AMBER}")
        t.append("  (b)", style=SMOKE)
        return t

    # --- Actions -------------------------------------------------------------

    def check_action(self, action: str, parameters: tuple) -> Optional[bool]:
        in_showdown = self.showdown is not None
        if action == "answer":
            return self.asking and self.riddle.kind == "choice" and parameters[0] < len(self.options)
        if action == "next":
            return self.mode == "result" or self.typing
        if action == "go":
            return self.mode == "result" and bool(self.last and self.last.unlocked)
        if action == "hint":
            return (self.asking and not in_showdown and not self.hint_shown
                    and bool(self.eliminated or self.engine.state.inventory or self.engine.favors()))
        if action == "evidence":
            return bool(self.engine.state.inventory) and (not in_showdown or self.asking)
        if action == "interrogate":
            return not in_showdown and self.engine.interrogation() is not None
        if action == "confront":
            return self.engine.can_confront() and not in_showdown
        if action in ("travel", "menu"):
            return not in_showdown
        return True

    def action_answer(self, i: int):
        self.respond(self.options[i])

    def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if not text or not self.typing:
            return
        response = text
        if self.riddle.kind == "match":
            response = self.engine.match_response(self.riddle, self.options, text)
            if response is None:
                self.notify(f"Type {len(self.riddle.pairs)} different letters, one per word, e.g. BCA.",
                            severity="warning")
                return
        event.input.value = ""
        self.respond(response, shown=text.upper() if self.riddle.kind == "match" else text)

    def respond(self, response: str, shown: Optional[str] = None):
        """Check an answer from the number keys or the text box"""
        r = self.riddle
        if self.showdown:
            correct = self.showdown.answer(response)
        else:
            self.last = self.engine.answer(r, response)
            correct = self.last.correct

        if correct:
            self.mode = "result"
            self.react(good=True)
            self.render_all()
            return

        self.last = None
        self.react(good=False)
        if r.kind == "choice":
            self.options = self.engine.replace_wrong_option(r, self.options, response, self.eliminated)
        else:
            self.eliminated.append(shown or response)
            if r.kind == "match":
                self.options = self.engine.match_options(r)

        if self.showdown and self.showdown.finished:
            self.finish_showdown()
        elif not self.showdown and self.engine.is_game_over():
            self.app.push_screen(
                EndScreen(self.engine, "GAME OVER", "Volkov's men found you first.", triumph=False, dead=True),
                self._back_to_title)
        else:
            self.render_all()

    def action_next(self):
        if self.typing:
            self.query_one("#answer", AnswerInput).focus()
            self.refresh_bindings()
        elif self.showdown:
            if self.showdown.finished:
                self.finish_showdown()
            else:
                self.new_question()
        elif self.engine.all_riddles_solved():
            self.end_case()
        else:
            self.new_question()

    def action_go(self):
        self.engine.travel(self.last.unlocked)
        self.new_question()

    # --- Evidence and hints ----------------------------------------------------

    def evidence_choices(self) -> List[Tuple[str, str, bool]]:
        return [(item, item, True) for item in self.engine.state.inventory]

    def action_evidence(self):
        if self.showdown:
            self.app.push_screen(ChoiceModal("Throw which evidence at Volkov? It dodges this question.",
                                             self.evidence_choices()), self._dodged)
        else:
            who = self.engine.location().character
            self.app.push_screen(ChoiceModal(f"Show {who} which evidence?", self.evidence_choices()),
                                 self._presented)

    def _presented(self, item: Optional[str]):
        if not item:
            return
        text = self.engine.present(item)
        if text:
            self.say(text, "good")
            self.notify("Added to your case notes.")
        else:
            self.say(f"The {item}? That means nothing to me.")
        self.render_all()

    def _dodged(self, item: Optional[str]):
        if item and self.showdown.dodge(item):
            self.notify(f"You slam the {item} on the table. Volkov falters and moves on.")
            if self.showdown.finished:
                self.finish_showdown()
            else:
                self.new_question()
                self.say(f"...The {item}. Where did you find that?", "good")
                self.render_all()

    def action_hint(self):
        if self.eliminated:
            self.hint_shown = True
            self.render_all()
        elif self.engine.favors():
            # People who trust you owe you a free hint each
            favors = [(f"favor:{who}", f"Call in {who}'s favor (free)", True) for who in self.engine.favors()]
            self.app.push_screen(ChoiceModal("Call in a favor, or trade evidence for a hint?",
                                             favors + self.evidence_choices()), self._traded)
        else:
            self.app.push_screen(ChoiceModal("Trade which evidence for a hint? You lose it.",
                                             self.evidence_choices()), self._traded)

    def _traded(self, item: Optional[str]):
        if item and item.startswith("favor:"):
            who = item[len("favor:"):]
            line = self.engine.call_in_favor(who)
            if line:
                self.hint_shown = True
                if who == self.engine.location().character:
                    self.say(line, "good")
                else:
                    self.notify(f'{who}: "{line}"', timeout=8)
                self.render_all()
            return
        if item and self.engine.spend_item(item):
            self.hint_shown = True
            self.render_all()

    # --- Interrogations ----------------------------------------------------------

    def action_interrogate(self):
        if self.engine.refuses():
            self.say(self.engine.interrogation().refuse, "bad")
            self.notify(self.engine.mend_advice(), severity="warning")
            self.render_all()
        elif self.app.tips.take("interrogation"):
            self.app.push_screen(TipModal("interrogation"), lambda _: self.open_interrogation())
        else:
            self.open_interrogation()

    def open_interrogation(self):
        self.app.push_screen(InterrogationModal(self.engine), self._interrogated)

    def _interrogated(self, last: Optional[Tuple[str, str]]):
        if last:
            mood, line = last
            self.say(line, mood)
        self.render_all()

    # --- Navigation ------------------------------------------------------------

    def action_notes(self):
        self.app.push_screen(notes_page(self.engine))

    def action_notebook(self):
        self.app.push_screen(notebook_page(self.engine))

    def action_travel(self):
        s = self.engine.state
        labels, choices = {}, []
        for n, loc_id in enumerate(STORY_ORDER, 1):
            loc = LOCATIONS[loc_id]
            if loc_id not in s.unlocked_locations:
                labels[loc_id] = "[?]"
                continue
            here = loc_id == s.current_location
            labels[loc_id] = f"[{'@' if here else n}] {loc.name}"
            solved, total = self.engine.progress(loc_id)
            choices.append((loc_id, f"{n}. {loc.name}  {solved}/{total}{'  (you are here)' if here else ''}", not here))
        self.app.push_screen(ChoiceModal("Where to, detective?", choices,
                                         above=Text(art.berlin_map(labels), style=SMOKE)),
                             self._traveled)

    def _traveled(self, loc_id: Optional[str]):
        if loc_id:
            self.engine.travel(loc_id)
            self.new_question()

    # --- The finale ---------------------------------------------------------------

    def action_confront(self):
        self.app.push_screen(ChoiceModal("Confront Volkov? This ends the case.", [
            ("yes", "Confront him now", True),
            ("no", "Not yet", True),
        ]), lambda choice: self.end_case() if choice == "yes" else None)

    def end_case(self):
        """Ask where Elena is, then face Volkov"""
        choices = [(str(i), place, True) for i, place in enumerate(ELENA_OPTIONS)]
        choices.append(("notes", "(Review your case notes first)", True))
        self.app.push_screen(ChoiceModal(ELENA_QUESTION, choices), self._elena_answered)

    def _elena_answered(self, choice: Optional[str]):
        if choice is None or choice == "notes":
            # Back out of the question to the notes; the question comes back afterwards
            self.app.push_screen(notes_page(self.engine), lambda _: self.end_case())
            return
        self.elena_guess = ELENA_OPTIONS[int(choice)]
        self.engine.travel(FINAL_LOCATION)
        blessing = self.engine.receive_blessing()
        self.showdown = self.engine.start_showdown()
        self.new_question()
        if blessing:
            who, line = blessing
            self.notify(f'You remember {who}\'s blessing: "{line}"  +1 ♥', timeout=10)

    def finish_showdown(self):
        won = self.showdown.won
        title, text = self.engine.get_ending(self.elena_guess, won)
        self.app.push_screen(EndScreen(self.engine, title, text, triumph=won), self._back_to_title)

    def _back_to_title(self, _=None):
        self.engine.new_game()
        self.app.switch_screen(TitleScreen())

    # --- Tips ---------------------------------------------------------------------

    def moment_tips(self) -> List[str]:
        """The tips that fit what is on screen, most urgent first"""
        keys = []
        if not self.showdown:
            keys.append("case")
        if self.typing:
            keys.append("typing")
        if self.mode == "result" and self.last and self.last.unlocked:
            keys.append("lead")
        if self.engine.state.current_location == FINAL_LOCATION and not self.showdown:
            keys.append("archive")
        if self.engine.state.inventory:
            keys.append("evidence")
        return keys

    def maybe_tip(self):
        """Show one tip the player hasn't seen yet, unless something else is already open"""
        if self.app.screen is not self:
            return
        key = self.app.tips.take(*self.moment_tips())
        if key:
            self.app.push_screen(TipModal(key))

    # --- Menu ---------------------------------------------------------------------

    def action_menu(self):
        self.app.push_screen(ChoiceModal("Menu", [
            ("back", "Back to the case", True),
            ("notes", "Case notes", True),
            ("notebook", "Etymology notebook", True),
            ("save", "Save", True),
            ("load", "Load", True),
            ("tips", f"Tips: {'on' if self.app.tips.enabled else 'off'}", True),
            ("title", "Title screen", True),
        ]), self._menu_choice)

    def _menu_choice(self, choice: Optional[str]):
        if choice == "notes":
            self.action_notes()
        elif choice == "notebook":
            self.action_notebook()
        elif choice == "save":
            self.app.push_screen(ChoiceModal("Save to slot", [
                (str(i), f"Slot {i}: {label}", True) for i, _, label in self.engine.get_save_slots()
            ]), self._saved)
        elif choice == "load":
            self.app.push_screen(load_modal(self.engine), self._loaded)
        elif choice == "tips":
            self.app.tips.set_enabled(not self.app.tips.enabled)
            self.notify(f"Tips are {'on' if self.app.tips.enabled else 'off'}.")
        elif choice == "title":
            self.app.switch_screen(TitleScreen())

    def _saved(self, slot: Optional[str]):
        if slot:
            self.engine.save_game(int(slot))
            self.notify(f"Case saved to slot {slot}.")

    def _loaded(self, slot: Optional[str]):
        if slot and self.engine.load_game(int(slot)):
            self.new_question()
            self.notify(f"Case loaded from slot {slot}.")


# =============================================================================
# APP
# =============================================================================

class NoirApp(App):
    TITLE = "Noir Language Riddles"
    CSS = f"""
    Screen {{ background: #0b0b0b; color: {PAPER}; }}
    #main {{ width: 1fr; }}
    #scene {{ height: auto; border: round #3a3a3a; padding: 0 1; }}
    #talk {{ height: auto; min-height: 10; border: round #3a3a3a; }}
    #portrait {{ width: 16; height: auto; }}
    #dialogue {{ width: 1fr; height: auto; padding-right: 1; }}
    #riddle-box {{ height: auto; min-height: 10; border: round {AMBER}; padding: 0 1; }}
    #riddle {{ height: auto; }}
    #answer {{ background: #141414; border: tall {AMBER}; }}
    #sidebar {{ width: 36; border: heavy #3a3a3a; padding: 0 1; }}
    #title-box {{ align: center middle; width: 100%; height: 100%; }}
    #title-box Static {{ width: auto; }}
    #title-menu {{ width: 40; height: auto; background: #0b0b0b; border: round {AMBER}; }}
    ChoiceModal, EndScreen, TextModal {{ align: center middle; background: rgba(0, 0, 0, 0.7); }}
    .dialog {{ width: 60; height: auto; background: #141414; border: heavy {AMBER}; padding: 1 2; }}
    .dialog OptionList {{ height: auto; max-height: 12; background: #141414; border: none; }}
    .dialog-title {{ margin-bottom: 1; }}
    .wide {{ width: 68; }}
    .end {{ width: 70; }}
    .page {{ width: 96; max-height: 90%; }}
    .page VerticalScroll {{ height: auto; max-height: 36; }}
    OptionList > .option-list--option-highlighted {{ background: {AMBER}; color: #0b0b0b; text-style: bold; }}
    Footer {{ background: #141414; }}
    InterrogationModal {{ align: center middle; background: rgba(0, 0, 0, 0.7); }}
    TipModal {{ align: left top; background: rgba(0, 0, 0, 0.3); }}
    .tip {{ width: 60; margin: 1 0 0 2; border: heavy {VIOLET}; }}
    .grill {{ width: 94; }}
    #grill-talk {{ height: auto; min-height: 10; }}
    #grill-portrait {{ width: 16; height: auto; }}
    #grill-line {{ width: 1fr; height: auto; }}
    .grill-keys {{ margin-top: 1; }}
    """

    def __init__(self, save_dir: Optional[Path] = None):
        super().__init__()
        self.engine = GameEngine(save_dir)
        self.tips = Tips(self.engine.SAVE_DIR)

    def on_mount(self):
        self.push_screen(TitleScreen())


def main():
    if "--web" not in sys.argv:
        NoirApp().run()
        return
    # Served to a browser (serve.py): every session is its own process, so give each one
    # a private save folder that disappears with it, instead of sharing the server's saves.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # closing the tab still cleans up
    with tempfile.TemporaryDirectory(prefix="noir-session-") as save_dir:
        NoirApp(Path(save_dir)).run()


if __name__ == "__main__":
    main()
