#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
Full-screen ASCII art version (needs Textual: pip install -r requirements.txt)

Run with: python tui.py
"""

import random
from typing import List, Optional, Tuple

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

import art
from engine import GameEngine, AnswerResult, STORY_ORDER, LOCATIONS, ELENA_QUESTION, ELENA_OPTIONS


AMBER = "#e0b050"
PAPER = "#d8d0c0"
SMOKE = "grey50"
BLOOD = "#c0392b"
MOSS = "#7fae6b"


def heading(text: str) -> Text:
    return Text(text.upper(), style=f"bold {AMBER}")


# =============================================================================
# MODALS
# =============================================================================

class ChoiceModal(ModalScreen[Optional[str]]):
    """A small boxed menu. Dismisses with the chosen option id, or None."""

    BINDINGS = [Binding("escape", "cancel", "Back")]

    def __init__(self, title: str, choices: List[Tuple[str, str, bool]]):
        super().__init__()
        self.title_text = title
        self.choices = choices  # (id, label, enabled)

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(heading(self.title_text), classes="dialog-title")
            yield OptionList(*[Option(label, id=cid, disabled=not enabled)
                               for cid, label, enabled in self.choices])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.dismiss(event.option.id)

    def action_cancel(self):
        self.dismiss(None)


class EndScreen(ModalScreen[None]):
    """Ending or game over card"""

    BINDINGS = [Binding("enter", "done", "Back to title")]

    def __init__(self, engine: GameEngine, title: str, text: str, won: bool):
        super().__init__()
        self.engine, self.end_title, self.text, self.won = engine, title, text, won

    def compose(self) -> ComposeResult:
        s = self.engine.state
        color = AMBER if self.won else BLOOD
        body = Text()
        body.append(art.LOGO if self.won else art.GAME_OVER, style=color)
        body.append(f"\n{self.end_title}\n\n", style=f"bold {color}")
        body.append(f"{self.text}\n\n", style=PAPER)
        body.append(f"Riddles solved   {len(s.solved_riddles)}/{len(self.engine.riddles)}\n", style=SMOKE)
        body.append(f"Evidence         {len(s.inventory)}/{self.engine.total_items()}\n", style=SMOKE)
        body.append(f"Final score      {s.score}\n\n", style=SMOKE)
        cracked = self.won and self.engine.all_riddles_solved()
        body.append("All our words are connected." if cracked else "The Babel Society wins. For now.",
                    style=f"italic {PAPER}")
        body.append("\n\nPress Enter", style=SMOKE)
        with Vertical(classes="dialog end"):
            yield Static(body)

    def action_done(self):
        self.dismiss(None)


# =============================================================================
# TITLE
# =============================================================================

class TitleScreen(Screen):
    def compose(self) -> ComposeResult:
        title = Text()
        title.append(art.LOGO, style=f"bold {AMBER}")
        title.append("\n   LANGUAGE RIDDLES: THE BABEL CONSPIRACY\n", style=f"bold {PAPER}")
        title.append(art.TITLE_SCENE, style=SMOKE)
        title.append("\n   Berlin, 1947. A linguist has disappeared.\n", style=SMOKE)
        title.append("   Solve etymological riddles to uncover the truth.", style=SMOKE)
        with Vertical(id="title-box"):
            yield Static(title)
            yield OptionList(
                Option("New case", id="new"),
                Option("Continue", id="continue"),
                Option("Load a saved case", id="load"),
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
        elif choice == "quit":
            self.app.exit()

    def _loaded(self, slot: Optional[str]):
        if slot and self.app.engine.load_game(int(slot)):
            self.app.switch_screen(GameScreen())


def load_modal(engine: GameEngine) -> ChoiceModal:
    return ChoiceModal("Load from slot",
                       [(str(i), f"Slot {i}: {label}", exists) for i, exists, label in engine.get_save_slots()])


# =============================================================================
# GAME
# =============================================================================

class NotesScreen(ModalScreen[None]):
    """Everything the detective has learned, to piece together where Elena is"""

    BINDINGS = [Binding("escape,enter,n", "close", "Close")]

    def __init__(self, engine: GameEngine):
        super().__init__()
        self.engine = engine

    def compose(self) -> ComposeResult:
        body = Text()
        notes = self.engine.case_notes()
        current = None
        for place, note in notes:
            if place != current:
                body.append(f"\n{place.upper()}\n", style=f"bold {AMBER}")
                current = place
            body.append(f" · {note}\n", style=PAPER)
        if not notes:
            body.append("\nNothing yet. Solve riddles and people will start talking.\n", style=SMOKE)
        body.append("\nPress Enter to close", style=SMOKE)
        with Vertical(classes="dialog notes"):
            yield Static(heading("Case notes"))
            with VerticalScroll():
                yield Static(body)

    def action_close(self):
        self.dismiss(None)


class GameScreen(Screen):
    BINDINGS = [
        Binding("1", "answer(0)", "Answer", show=False),
        Binding("2", "answer(1)", "Answer", show=False),
        Binding("3", "answer(2)", "Answer", show=False),
        Binding("4", "answer(3)", "Answer", show=False),
        Binding("enter", "next", "Continue"),
        Binding("g", "go", "Follow lead"),
        Binding("h", "hint", "Hint"),
        Binding("n", "notes", "Notes"),
        Binding("t", "travel", "Travel"),
        Binding("v", "confront", "Confront Volkov"),
        Binding("m,escape", "menu", "Menu"),
    ]

    def __init__(self):
        super().__init__()
        self.mode = "question"          # "question" or "result"
        self.riddle = None
        self.options: List[str] = []
        self.eliminated: List[str] = []  # wrong picks, swapped out for decoys
        self.hint_shown = False
        self.last: Optional[AnswerResult] = None
        self.mood = "neutral"            # portrait expression
        self.reaction: Optional[str] = None

    @property
    def engine(self) -> GameEngine:
        return self.app.engine

    def compose(self) -> ComposeResult:
        with Horizontal():
            with VerticalScroll(id="main"):
                yield Static(id="scene")
                with Horizontal(id="talk"):
                    yield Static(id="portrait")
                    yield Static(id="dialogue")
                yield Static(id="riddle")
            yield Static(id="sidebar")
        yield Footer()

    def on_mount(self):
        self.new_question()

    # --- Rendering -----------------------------------------------------------

    def new_question(self):
        self.mode = "question"
        self.riddle = self.engine.current_riddle()
        self.options = self.engine.shuffled_options(self.riddle) if self.riddle else []
        self.eliminated = []
        self.hint_shown = False
        self.last = None
        self.mood = "neutral"
        self.reaction = None
        self.render_all()

    def render_all(self):
        loc = self.engine.location()

        scene = Text(art.SCENES[loc.id], style=SMOKE)
        scene.append(f"\n{loc.name.upper()}\n", style=f"bold {AMBER}")
        scene.append(loc.description, style=PAPER)
        self.query_one("#scene", Static).update(scene)

        self.query_one("#portrait", Static).update(Text(art.PORTRAITS[loc.character][self.mood], style=PAPER))
        self.query_one("#dialogue", Static).update(self.render_dialogue())
        self.query_one("#riddle", Static).update(
            self.render_result() if self.mode == "result" else self.render_question())
        self.query_one("#sidebar", Static).update(self.render_sidebar())
        self.refresh_bindings()

    def render_dialogue(self) -> Text:
        """Most important line wins: a new lead, a new beat, a reaction, then small talk"""
        loc = self.engine.location()
        t = Text()
        t.append(f"\n{loc.character}\n", style=f"bold {AMBER}")
        if self.last and self.last.unlocked:
            t.append(loc.lead_text, style=f"italic {PAPER}")
        elif self.last and self.last.beat:
            t.append(f'"{self.last.beat}"', style=f"italic {PAPER}")
            t.append("\n(added to your case notes)", style=SMOKE)
        elif self.reaction:
            t.append(f'"{self.reaction}"', style=f"italic {PAPER}")
        elif self.riddle is None:
            t.append(f'"{loc.done_text}"', style=f"italic {PAPER}")
        else:
            beats = self.engine.beats_unlocked(loc.id)
            t.append(f'"{beats[-1] if beats else loc.greeting}"', style=f"italic {PAPER}")
        return t

    def render_question(self) -> Text:
        t = Text()
        if not self.riddle:
            t.append("You've turned this place inside out.\n\n", style=PAPER)
            t.append("Press t to follow another lead, n to review your notes.", style=SMOKE)
            if self.engine.can_confront():
                t.append("\nPress v to confront Volkov.", style=BLOOD)
            return t

        r = self.riddle
        is_lead = r.id == self.engine.location().lead_riddle
        t.append(f"{'LEAD' if is_lead else 'RIDDLE'}  ·  {r.language}  ·  {r.category}\n", style=f"bold {AMBER}")
        t.append(f"Clue: {r.clue}\n\n", style="bold #c49bd8")
        t.append(f"{r.text}\n\n", style=PAPER)
        for i, option in enumerate(self.options):
            t.append(f"  [{i + 1}] ", style=AMBER)
            t.append(f"{option}\n", style=PAPER)
        if self.eliminated:
            s = self.engine.state
            t.append(f"\n✗ Wrong. The answers blur and rearrange. Sanity {s.sanity}/{s.max_sanity}.\n", style=BLOOD)
            t.append(f"Ruled out: {', '.join(self.eliminated)}", style=f"strike {SMOKE}")
            if self.hint_shown:
                t.append(f"\nHint: {r.hint}", style="#c49bd8")
            else:
                t.append("\nPress h for a hint.", style=SMOKE)
        return t

    def render_result(self) -> Text:
        res = self.last
        r = res.riddle
        t = Text()
        t.append(f"✓ CORRECT  ·  {r.answer}\n\n", style=f"bold {MOSS}")
        t.append(f"{r.explanation}\n", style=PAPER)
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

        t.append(f"EVIDENCE {len(s.inventory)}/{self.engine.total_items()}\n", style=f"bold {AMBER}")
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
        t.append("  (press n)", style=SMOKE)
        return t

    # --- Actions -------------------------------------------------------------

    def check_action(self, action: str, parameters: tuple) -> Optional[bool]:
        asking = self.mode == "question" and self.riddle is not None
        if action == "answer":
            return asking and parameters[0] < len(self.options)
        if action == "next":
            return self.mode == "result"
        if action == "go":
            return self.mode == "result" and bool(self.last and self.last.unlocked)
        if action == "hint":
            return asking and bool(self.eliminated) and not self.hint_shown
        if action == "confront":
            return self.engine.can_confront()
        return True

    def action_answer(self, i: int):
        loc = self.engine.location()
        picked = self.options[i]
        result = self.engine.answer(self.riddle, picked)
        if result.correct:
            self.mode = "result"
            self.last = result
            self.mood = "good"
            self.reaction = random.choice(loc.good_lines) if loc.good_lines else None
        else:
            self.options = self.engine.replace_wrong_option(self.riddle, self.options, picked, self.eliminated)
            self.mood = "bad"
            self.reaction = random.choice(loc.bad_lines) if loc.bad_lines else None
            if self.engine.is_game_over():
                self.app.push_screen(
                    EndScreen(self.engine, "GAME OVER", "Volkov's men found you first.", won=False),
                    self._back_to_title)
                return
        self.render_all()

    def action_next(self):
        if self.engine.all_riddles_solved():
            self.end_case()
        else:
            self.new_question()

    def action_go(self):
        self.engine.travel(self.last.unlocked)
        self.new_question()

    def action_hint(self):
        self.hint_shown = True
        self.render_all()

    def action_notes(self):
        self.app.push_screen(NotesScreen(self.engine))

    def action_travel(self):
        s = self.engine.state
        choices = []
        for loc in self.engine.unlocked_locations():
            solved, total = self.engine.progress(loc.id)
            here = " (you are here)" if loc.id == s.current_location else ""
            choices.append((loc.id, f"{loc.name}  {solved}/{total}{here}", loc.id != s.current_location))
        self.app.push_screen(ChoiceModal("Where to, detective?", choices), self._traveled)

    def _traveled(self, loc_id: Optional[str]):
        if loc_id:
            self.engine.travel(loc_id)
            self.new_question()

    def action_confront(self):
        self.app.push_screen(ChoiceModal("Confront Volkov? This ends the case.", [
            ("yes", "Confront him now", True),
            ("no", "Not yet", True),
        ]), lambda choice: self.end_case() if choice == "yes" else None)

    def end_case(self):
        """Ask where Elena is, then show the ending"""
        choices = [(str(i), place, True) for i, place in enumerate(ELENA_OPTIONS)]
        choices.append(("notes", "(Review your case notes first)", True))
        self.app.push_screen(ChoiceModal(ELENA_QUESTION, choices), self._elena_answered)

    def _elena_answered(self, choice: Optional[str]):
        if choice is None or choice == "notes":
            # Back out of the question to the notes; the question comes back afterwards
            self.app.push_screen(NotesScreen(self.engine), lambda _: self.end_case())
            return
        title, text = self.engine.get_ending(ELENA_OPTIONS[int(choice)])
        self.app.push_screen(EndScreen(self.engine, title, text, won=True), self._back_to_title)

    def _back_to_title(self, _=None):
        self.engine.new_game()
        self.app.switch_screen(TitleScreen())

    def action_menu(self):
        self.app.push_screen(ChoiceModal("Menu", [
            ("back", "Back to the case", True),
            ("notes", "Case notes", True),
            ("save", "Save", True),
            ("load", "Load", True),
            ("title", "Title screen", True),
        ]), self._menu_choice)

    def _menu_choice(self, choice: Optional[str]):
        if choice == "notes":
            self.action_notes()
        elif choice == "save":
            self.app.push_screen(ChoiceModal("Save to slot", [
                (str(i), f"Slot {i}: {label}", True) for i, _, label in self.engine.get_save_slots()
            ]), self._saved)
        elif choice == "load":
            self.app.push_screen(load_modal(self.engine), self._loaded)
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
    #talk {{ height: auto; border: round #3a3a3a; }}
    #portrait {{ width: 16; height: auto; }}
    #dialogue {{ width: 1fr; height: auto; padding-right: 1; }}
    #riddle {{ height: auto; min-height: 10; border: round {AMBER}; padding: 0 1; }}
    #sidebar {{ width: 36; border: heavy #3a3a3a; padding: 0 1; }}
    #title-box {{ align: center middle; width: 100%; height: 100%; }}
    #title-box Static {{ width: auto; }}
    #title-menu {{ width: 40; height: auto; background: #0b0b0b; border: round {AMBER}; }}
    ChoiceModal, EndScreen, NotesScreen {{ align: center middle; background: rgba(0, 0, 0, 0.7); }}
    .dialog {{ width: 60; height: auto; background: #141414; border: heavy {AMBER}; padding: 1 2; }}
    .dialog OptionList {{ height: auto; background: #141414; border: none; }}
    .dialog-title {{ margin-bottom: 1; }}
    .end {{ width: 70; }}
    .notes {{ width: 90; max-height: 80%; }}
    .notes VerticalScroll {{ height: auto; max-height: 30; }}
    OptionList > .option-list--option-highlighted {{ background: {AMBER}; color: #0b0b0b; text-style: bold; }}
    Footer {{ background: #141414; }}
    """

    def __init__(self):
        super().__init__()
        self.engine = GameEngine()

    def on_mount(self):
        self.push_screen(TitleScreen())


if __name__ == "__main__":
    NoirApp().run()
