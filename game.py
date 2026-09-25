"""
Noir Language Riddles - Game Engine
Clean, extensible game logic
"""

import json
import os
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path

from data import DATA, Riddle, Location


@dataclass
class GameState:
    """Current game state"""
    current_location: str = "ClientOffice"
    solved_riddles: List[int] = field(default_factory=list)
    inventory: List[str] = field(default_factory=list)
    sanity: int = 3
    max_sanity: int = 3
    score: int = 0
    visited_locations: List[str] = field(default_factory=list)


class GameEngine:
    """Main game logic"""
    
    SAVE_DIR = Path.home() / ".babel_conspiracy"
    
    def __init__(self):
        self.state = GameState()
        self.data = DATA
        self._ensure_save_dir()
    
    def _ensure_save_dir(self):
        """Create save directory if it doesn't exist"""
        self.SAVE_DIR.mkdir(parents=True, exist_ok=True)
    
    def get_current_location(self) -> Optional[Location]:
        """Get the current location object"""
        return self.data.get_location(self.state.current_location)
    
    def get_current_riddle(self) -> Optional[Riddle]:
        """Get the current riddle for the location"""
        loc = self.get_current_location()
        if not loc:
            return None
        
        # Find first unsolved riddle for this location
        # First check riddles that point to this location
        for riddle in self.data.riddles:
            if riddle.next_location == loc.id and riddle.id not in self.state.solved_riddles:
                return riddle
        
        # Then check the location's first riddle
        first_riddle = self.data.get_riddle(loc.first_riddle)
        if first_riddle and first_riddle.id not in self.state.solved_riddles:
            return first_riddle
        
        # No unsolved riddles here
        return None
    
    def check_answer(self, riddle_id: int, selected_answer: str) -> tuple:
        """
        Check if an answer is correct.
        Returns: (is_correct, riddle, next_location_id)
        """
        riddle = self.data.get_riddle(riddle_id)
        if not riddle:
            return False, None, None
        
        is_correct = selected_answer == riddle.answer
        
        if is_correct:
            if riddle.id not in self.state.solved_riddles:
                self.state.solved_riddles.append(riddle.id)
            self.state.score += riddle.difficulty * 10
            
            if riddle.item and riddle.item not in self.state.inventory:
                self.state.inventory.append(riddle.item)
        else:
            self.state.sanity -= 1
        
        return is_correct, riddle, riddle.next_location
    
    def move_to_location(self, location_id: str):
        """Move player to a new location"""
        loc = self.data.get_location(location_id)
        if loc:
            self.state.current_location = location_id
            if location_id not in self.state.visited_locations:
                self.state.visited_locations.append(location_id)
            return True
        return False
    
    def get_random_unsolved_riddle(self) -> Optional[Riddle]:
        """Get a random unsolved riddle"""
        unsolved = [r for r in self.data.riddles if r.id not in self.state.solved_riddles]
        return random.choice(unsolved) if unsolved else None
    
    def get_ending(self) -> tuple:
        """
        Determine which ending the player gets.
        Returns: (title, description)
        """
        total_riddles = len(self.data.riddles)
        total_items = len(self.data.get_riddles_with_items())
        solved = len(self.state.solved_riddles)
        collected = len(self.state.inventory)
        high_score = self.state.score >= 200
        
        if solved >= total_riddles and collected >= total_items:
            return "The Truth Revealed", \
                   "With all clues and the complete Babel Manuscript, you expose the Babel Society to the world."
        elif solved >= total_riddles or high_score:
            return "Partial Victory", \
                   "You solve the case and recover the manuscript, but Volkov escapes."
        elif solved >= total_riddles / 2:
            return "A Lead, Not a Victory", \
                   "You gather enough evidence to close Elena's case, but the Babel Society remains."
        else:
            return "Case Closed", \
                   "You solved the case, but Volkov escaped with the manuscript."
    
    def is_game_over(self) -> bool:
        """Check if game is over (sanity <= 0)"""
        return self.state.sanity <= 0
    
    def save_game(self, slot: int = 0):
        """Save game state to file"""
        state_dict = {
            "current_location": self.state.current_location,
            "solved_riddles": self.state.solved_riddles,
            "inventory": self.state.inventory,
            "sanity": self.state.sanity,
            "max_sanity": self.state.max_sanity,
            "score": self.state.score,
            "visited_locations": self.state.visited_locations
        }
        
        slot_path = self.SAVE_DIR / f"slot_{slot}.json"
        with open(slot_path, 'w') as f:
            json.dump(state_dict, f, indent=2)
        
        # Also save to auto-save
        auto_path = self.SAVE_DIR / "autosave.json"
        with open(auto_path, 'w') as f:
            json.dump(state_dict, f, indent=2)
        
        return True
    
    def load_game(self, slot: int = 0) -> bool:
        """Load game state from file. slot=0 is autosave"""
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
    
    def get_save_info(self, slot: int) -> Dict[str, Any]:
        """Get save slot info for display"""
        if slot == 0:
            save_path = self.SAVE_DIR / "autosave.json"
        else:
            save_path = self.SAVE_DIR / f"slot_{slot}.json"
        
        if not save_path.exists():
            return {"exists": False, "label": "Empty"}
        
        try:
            with open(save_path, 'r') as f:
                state_dict = json.load(f)
            return {
                "exists": True,
                "label": f"Score: {state_dict.get('score', 0)}, Sanity: {state_dict.get('sanity', 3)}",
                "location": state_dict.get("current_location", "Unknown")
            }
        except:
            return {"exists": False, "label": "Corrupted"}
    
    def reset_game(self):
        """Reset game to initial state"""
        self.state = GameState()
        # Remove autosave
        auto_path = self.SAVE_DIR / "autosave.json"
        if auto_path.exists():
            auto_path.unlink()
