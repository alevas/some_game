#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
A text-based detective game about etymology

Run with: python main.py
"""

from textual.app import App, ComposeResult
from textual.widgets import Button, Static, Label, Placeholder
from textual.containers import Container, ScrollableContainer, Grid
from textual.reactive import reactive
from textual.events import Key
from textual.binding import Binding

from game import GameEngine, GameState
from data import DATA, Riddle


class GameScreen(Static):
    """Base class for game screens"""
    pass


class LocationScreen(Static):
    """Screen showing a location and its riddle"""
    
    def __init__(self, engine: GameEngine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = engine
        self.riddle_id = None
    
    def compose(self) -> ComposeResult:
        loc = self.engine.get_current_location()
        if not loc:
            yield Label("Error: Location not found")
            return
        
        # Location header
        yield Label(f":: {loc.name.upper()} ::", classes="location")
        yield Label(loc.description)
        
        # Character dialogue
        char = self.engine.data.get_character(loc.id)
        if char and char.dialogue:
            yield Label(f'"{char.dialogue[0]}"', classes="dialogue")
        
        # Riddle
        riddle = self.engine.get_current_riddle()
        if riddle:
            self.riddle_id = riddle.id
            yield Label(riddle.clue, classes="clue")
            yield Label(riddle.text, classes="riddle-text")
            
            # Answer buttons
            answers = [riddle.answer] + riddle.wrong_answers
            random.shuffle(answers)
            
            for answer in answers:
                yield Button(answer, id=f"answer_{answer}", classes="answer-btn")
        else:
            yield Label("You've solved all riddles here.")
            yield Button("Look for more clues", id="random_riddle")
    
    def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        
        if button_id.startswith("answer_"):
            answer = button_id.replace("answer_", "")
            self.check_answer(answer)
        elif button_id == "random_riddle":
            self.engine.move_to_location("ClientOffice")  # Temporary
            self.parent.remove(self)
            self.parent.mount(LocationScreen(self.engine))
        elif button_id == "show_hint":
            self.show_hint()
        elif button_id == "continue":
            next_loc = self.engine.get_current_riddle().next_location
            if next_loc:
                self.engine.move_to_location(next_loc)
                self.parent.remove(self)
                self.parent.mount(LocationScreen(self.engine))
    
    def check_answer(self, selected: str):
        riddle = self.engine.data.get_riddle(self.riddle_id)
        if not riddle:
            return
        
        is_correct, riddle, next_loc = self.engine.check_answer(self.riddle_id, selected)
        
        self.parent.remove(self)
        
        if is_correct:
            result = ResultScreen(self.engine, riddle, next_loc, True)
        else:
            result = ResultScreen(self.engine, riddle, next_loc, False)
        
        self.parent.mount(result)


class ResultScreen(Static):
    """Screen showing answer result"""
    
    def __init__(self, engine: GameEngine, riddle: Riddle, next_loc: str, is_correct: bool):
        super().__init__()
        self.engine = engine
        self.riddle = riddle
        self.next_loc = next_loc
        self.is_correct = is_correct
    
    def compose(self) -> ComposeResult:
        if self.is_correct:
            yield Label("✓ Correct!", classes="correct")
            yield Label(self.riddle.answer, classes="answer-correct")
            yield Label(self.riddle.explanation)
            
            if self.riddle.item:
                yield Label(f"You collected: {self.riddle.item}", classes="correct")
            
            if self.next_loc:
                loc = self.engine.data.get_location(self.next_loc)
                if loc:
                    yield Button(f"Continue to {loc.name}", id="continue")
                else:
                    yield Button("Continue investigating", id="random")
            else:
                yield Button("Next riddle", id="random")
        else:
            yield Label("✗ Wrong.", classes="wrong")
            yield Label(f"'{self.riddle.answer}' was the correct answer.")
            yield Label("You lose 1 Sanity point!")
            
            yield Button("Try again", id="retry")
            yield Button("Show hint", id="show_hint")
    
    def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        
        if button_id == "continue":
            self.engine.move_to_location(self.next_loc)
            self.parent.remove(self)
            self.parent.mount(LocationScreen(self.engine))
        elif button_id == "random":
            riddle = self.engine.get_random_unsolved_riddle()
            if riddle:
                self.parent.remove(self)
                self.parent.mount(RiddleScreen(self.engine, riddle))
            else:
                self.parent.remove(self)
                self.parent.mount(EndingScreen(self.engine))
        elif button_id == "retry":
            self.parent.remove(self)
            self.parent.mount(LocationScreen(self.engine))
        elif button_id == "show_hint":
            self.parent.remove(self)
            self.parent.mount(HintScreen(self.engine, self.riddle))


class RiddleScreen(Static):
    """Screen showing a standalone riddle"""
    
    def __init__(self, engine: GameEngine, riddle: Riddle):
        super().__init__()
        self.engine = engine
        self.riddle = riddle
        self.riddle_id = riddle.id
    
    def compose(self) -> ComposeResult:
        yield Label(f"Riddle: {self.riddle.language}", classes="riddle-header")
        yield Label(self.riddle.clue, classes="clue")
        yield Label(self.riddle.text, classes="riddle-text")
        
        answers = [self.riddle.answer] + self.riddle.wrong_answers
        random.shuffle(answers)
        
        for answer in answers:
            yield Button(answer, id=f"answer_{answer}", classes="answer-btn")
    
    def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id.startswith("answer_"):
            answer = button_id.replace("answer_", "")
            is_correct, riddle, next_loc = self.engine.check_answer(self.riddle_id, answer)
            self.parent.remove(self)
            if is_correct:
                self.parent.mount(ResultScreen(self.engine, riddle, next_loc, True))
            else:
                self.parent.mount(ResultScreen(self.engine, riddle, next_loc, False))


class HintScreen(Static):
    """Screen showing a hint"""
    
    def __init__(self, engine: GameEngine, riddle: Riddle):
        super().__init__()
        self.engine = engine
        self.riddle = riddle
    
    def compose(self) -> ComposeResult:
        yield Label(f"Hint: {self.riddle.hint}")
        yield Button("Back to riddle", id="back")
    
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.parent.remove(self)
            self.parent.mount(LocationScreen(self.engine))


class EndingScreen(Static):
    """Screen showing game ending"""
    
    def __init__(self, engine: GameEngine):
        super().__init__()
        self.engine = engine
    
    def compose(self) -> ComposeResult:
        title, description = self.engine.get_ending()
        total_riddles = len(self.engine.data.riddles)
        total_items = len(self.engine.data.get_riddles_with_items())
        
        yield Label(title, classes="ending-title")
        yield Label(description)
        yield Label("")
        yield Label("--- STATS ---")
        yield Label(f"Riddles solved: {len(self.engine.state.solved_riddles)} of {total_riddles}")
        yield Label(f"Items collected: {len(self.engine.state.inventory)} of {total_items}")
        yield Label(f"Sanity remaining: {self.engine.state.sanity}")
        yield Label(f"Final score: {self.engine.state.score}")
        yield Label("")
        yield Label("All our words are connected.", classes="ending-quote")
        yield Button("New Case", id="new_game")
    
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "new_game":
            self.engine.reset_game()
            self.parent.remove(self)
            self.parent.mount(LocationScreen(self.engine))


class GameOverScreen(Static):
    """Screen shown when sanity reaches 0"""
    
    def __init__(self, engine: GameEngine):
        super().__init__()
        self.engine = engine
    
    def compose(self) -> ComposeResult:
        total_riddles = len(self.engine.data.riddles)
        total_items = len(self.engine.data.get_riddles_with_items())
        
        yield Label("GAME OVER", classes="game-over-title")
        yield Label("Volkov's men found you first.")
        yield Label("")
        yield Label("--- STATS ---")
        yield Label(f"Riddles solved: {len(self.engine.state.solved_riddles)} of {total_riddles}")
        yield Label(f"Items collected: {len(self.engine.state.inventory)} of {total_items}")
        yield Label(f"Final score: {self.engine.state.score}")
        yield Label("")
        yield Label("The Babel Society wins. For now.")
        yield Button("Retry Case", id="retry")
    
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "retry":
            self.engine.reset_game()
            self.parent.remove(self)
            self.parent.mount(LocationScreen(self.engine))


class SaveMenu(Static):
    """Save/Load menu screen"""
    
    def __init__(self, engine: GameEngine):
        super().__init__()
        self.engine = engine
    
    def compose(self) -> ComposeResult:
        yield Label("Save/Load Game", classes="menu-title")
        yield Label("")
        
        for slot in range(1, 4):
            info = self.engine.get_save_info(slot)
            with Container():
                yield Label(f"Slot {slot}", classes="slot-title")
                yield Label(info["label"], classes="slot-info")
                with Container(classes="slot-buttons"):
                    yield Button("Save", id=f"save_{slot}", classes="menu-btn")
                    yield Button("Load", id=f"load_{slot}", classes="menu-btn")
        
        yield Label("")
        yield Button("Close", id="close", classes="menu-btn")
    
    def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        
        if button_id.startswith("save_"):
            slot = int(button_id.replace("save_", ""))
            self.engine.save_game(slot)
            self.parent.remove(self)
        elif button_id.startswith("load_"):
            slot = int(button_id.replace("load_", ""))
            if self.engine.load_game(slot):
                self.parent.remove(self)
                self.parent.mount(LocationScreen(self.engine))
        elif button_id == "close":
            self.parent.remove(self)


class NoirApp(App):
    """Main game application"""
    
    CSS = """
    Screen {
        align: center middle;
    }
    
    Static {
        width: 100%;
        height: 100%;
        overflow-y: auto;
    }
    
    Label {
        width: 100%;
        text-align: center;
        color: $text;
    }
    
    Button {
        width: 100%;
        margin: 1 0;
        background: $background 15%;
        color: $text;
        border: solid $accent;
    }
    
    Button:hover {
        background: $background 25%;
    }
    
    Container {
        layout: horizontal;
        width: 100%;
        height: auto;
    }
    
    .location {
        color: $accent;
        font-style: bold;
    }
    
    .dialogue {
        color: $text 60%;
        font-style: italic;
    }
    
    .clue {
        background: $background 20%;
        border-left: solid $accent;
        padding: 1 2;
        margin: 1 0;
    }
    
    .riddle-text {
        font-style: italic;
        color: $text 80%;
    }
    
    .correct {
        color: $success;
    }
    
    .wrong {
        color: $error;
    }
    
    .answer-correct {
        color: $success;
        font-style: bold;
    }
    
    .ending-title {
        color: $success;
        font-size: 2;
    }
    
    .game-over-title {
        color: $error;
        font-size: 2;
    }
    
    .ending-quote {
        color: $text 60%;
        font-style: italic;
    }
    
    .menu-title {
        color: $accent;
        font-size: 1.5;
    }
    
    .slot-title {
        width: 30%;
    }
    
    .slot-info {
        width: 40%;
    }
    
    .slot-buttons {
        width: 30%;
    }
    
    .menu-btn {
        width: auto;
        padding: 0 2;
    }
    
    .answer-btn {
        width: auto;
        margin: 0 1;
        min-width: 15;
    }
    """
    
    # Color theme for noir aesthetic
    TITLE = "Noir Language Riddles: The Babel Conspiracy"
    SUBTITLE = "A detective game about linguistic roots"
    
    # Key bindings
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("m", "menu", "Save/Load Menu"),
        Binding("escape", "back", "Go Back"),
    ]
    
    def __init__(self):
        super().__init__()
        self.engine = GameEngine()
        # Load autosave if exists
        self.engine.load_game(0)
    
    def compose(self) -> ComposeResult:
        yield Label(self.TITLE)
        yield Label(self.SUBTITLE)
        yield Label("")
        yield Label("Press any key to begin...")
    
    def on_ready(self):
        """Start the game when ready"""
        self.call_after_refresh(self.start_game)
    
    def start_game(self):
        """Clear intro and show first location"""
        self.query(Label).remove()
        self.mount(LocationScreen(self.engine))
        self.show_ui()
    
    def show_ui(self):
        """Show the game UI at the bottom"""
        # Create UI container
        ui = Container(classes="ui-container")
        
        # Sanity meter
        sanity_text = Label("SANITY: ")
        sanity_icons = Label(self.get_sanity_icons())
        
        with Container(classes="ui-section"):
            yield sanity_text
            yield sanity_icons
        
        # Score
        score_label = Label(f"SCORE: {self.engine.state.score}")
        with Container(classes="ui-section"):
            yield score_label
        
        # Inventory
        inv_label = Label("INVENTORY: ")
        inv_items = Label(self.get_inventory_text())
        with Container(classes="ui-section"):
            yield inv_label
            yield inv_items
        
        # Menu button
        with Container(classes="ui-section"):
            yield Button("Menu [M]", id="menu_btn")
        
        # Add to screen
        self.mount(ui)
    
    def get_sanity_icons(self) -> str:
        """Get sanity icons for display"""
        icons = ""
        for i in range(self.engine.state.max_sanity):
            if i < self.engine.state.sanity:
                icons += "♥"
            else:
                icons += "♡"
        return icons
    
    def get_inventory_text(self) -> str:
        """Get inventory items as text"""
        if not self.engine.state.inventory:
            return "Empty"
        return ", ".join(self.engine.state.inventory)
    
    def update_ui(self):
        """Update the UI display"""
        # Update sanity
        sanity_icons = self.query(Label).filter("Label[node_id*='sanity_icons']").first()
        if sanity_icons:
            sanity_icons.update(self.get_sanity_icons())
        
        # Update score
        score_label = self.query(Label).filter("Label:contains('SCORE:')").first()
        if score_label:
            score_label.update(f"SCORE: {self.engine.state.score}")
        
        # Update inventory
        inv_items = self.query(Label).filter("Label[node_id*='inv_items']").first()
        if inv_items:
            inv_items.update(self.get_inventory_text())
        
        # Check for game over
        if self.engine.is_game_over():
            self.mount(GameOverScreen(self.engine))
    
    def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses"""
        if event.button.id == "menu_btn":
            self.mount(SaveMenu(self.engine))
        elif event.button.id == "save_1":
            self.engine.save_game(1)
        elif event.button.id == "load_1":
            if self.engine.load_game(1):
                self.update_ui()
    
    def on_key(self, event: Key):
        """Handle key presses"""
        if event.key == "m":
            self.mount(SaveMenu(self.engine))
        elif event.key == "escape":
            # Close any overlays
            overlays = self.query(Static).filter(".save-menu, .menu")
            if overlays:
                overlays.first().remove()


if __name__ == "__main__":
    app = NoirApp()
    app.run()
