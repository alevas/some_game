"""Engine tests. Run with: python -m unittest"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import art
from engine import GameEngine, LOCATIONS, RIDDLES, ELENA_ANSWER, ELENA_OPTIONS


class EngineTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(GameEngine, "SAVE_DIR", Path(tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.engine = GameEngine()
        self.engine.new_game()

    def solve_here(self, wrong_first=False):
        e = self.engine
        r = e.current_riddle()
        if wrong_first:
            e.answer(r, "__wrong__")
        return e.answer(r, r.answer)

    def play_through(self, wrong_on_items=False):
        """Solve every riddle, following the story in order"""
        e = self.engine
        while not e.all_riddles_solved():
            if e.current_riddle() is None:
                nxt = next(l.id for l in e.unlocked_locations() if e.progress(l.id)[0] < e.progress(l.id)[1])
                e.travel(nxt)
            r = e.current_riddle()
            self.solve_here(wrong_first=wrong_on_items and bool(r.item))
            e.state.sanity = e.state.max_sanity  # keep the run alive

    # --- Data -----------------------------------------------------------------

    def test_every_riddle_placed_once(self):
        placed = sorted(i for loc in LOCATIONS.values() for i in self.engine.riddles_at(loc.id))
        self.assertEqual(placed, sorted(r.id for r in RIDDLES))

    def test_options_are_unique_and_answer_is_not_a_decoy(self):
        for r in RIDDLES:
            options = [r.answer] + r.wrong_answers + r.decoys
            self.assertEqual(len({o.lower() for o in options}), len(options), r.id)
            self.assertLessEqual(len(r.wrong_answers) + 1, 4, f"riddle {r.id} has more options than number keys")

    def test_every_character_has_every_mood(self):
        for loc in LOCATIONS.values():
            self.assertEqual(set(art.PORTRAITS[loc.character]), {"neutral", "good", "bad"})
            self.assertIn(loc.id, art.SCENES)

    def test_elena_answer_is_an_option(self):
        self.assertIn(ELENA_ANSWER, ELENA_OPTIONS)

    # --- Progression ------------------------------------------------------------

    def test_lead_unlocks_next_location(self):
        result = self.solve_here()
        self.assertEqual(result.unlocked, "Library")
        self.assertTrue(self.engine.travel("Library"))
        self.assertFalse(self.engine.travel("Archive"))

    def test_lead_appears_after_enough_riddles(self):
        e = self.engine
        self.solve_here()
        e.travel("Library")
        lib = LOCATIONS["Library"]
        for _ in range(lib.lead_after):
            self.assertNotEqual(e.current_riddle().id, lib.lead_riddle)
            self.solve_here()
        self.assertEqual(e.current_riddle().id, lib.lead_riddle)

    # --- Anti-guessing ----------------------------------------------------------

    def test_wrong_pick_is_replaced_by_decoy(self):
        e = self.engine
        r = e.current_riddle()
        options = e.shuffled_options(r)
        eliminated = []
        wrong = next(o for o in options if o != r.answer)
        new = e.replace_wrong_option(r, options, wrong, eliminated)
        self.assertEqual(len(new), len(options))
        self.assertNotIn(wrong, new)
        self.assertIn(r.answer, new)
        self.assertIn(r.decoys[0], new)

    def test_streak_restores_a_heart_every_third_clean_solve(self):
        e = self.engine
        self.solve_here()
        e.travel("Library")
        e.answer(e.current_riddle(), "__wrong__")  # sanity 2, streak reset
        self.solve_here()                            # fumbled: no streak
        self.assertEqual(e.state.streak, 0)
        self.solve_here()
        self.solve_here()
        result = self.solve_here()
        self.assertEqual(e.state.streak, 3)
        self.assertTrue(result.heart_restored)
        self.assertEqual(e.state.sanity, 3)

    # --- Story and endings ------------------------------------------------------

    def test_beats_unlock_and_reach_case_notes(self):
        e = self.engine
        self.solve_here()
        e.travel("Library")
        self.assertIsNone(self.solve_here().beat)
        self.assertIsNotNone(self.solve_here().beat)  # Schmidt's first beat at 2 solved
        self.assertTrue(any("St. Nicholas" in note for _, note in e.case_notes()))

    def test_perfect_run_with_right_deduction(self):
        self.play_through()
        title, text = self.engine.get_ending(ELENA_ANSWER)
        self.assertEqual(title, "The Truth Revealed")
        self.assertIn("alive", text)

    def test_wrong_deduction_blocks_best_ending(self):
        self.play_through()
        title, text = self.engine.get_ending(ELENA_OPTIONS[1])
        self.assertEqual(title, "Partial Victory")
        self.assertIn("never seen again", text)

    def test_fumbled_evidence_blocks_best_ending(self):
        self.play_through(wrong_on_items=True)
        self.assertEqual(self.engine.get_ending(ELENA_ANSWER)[0], "Partial Victory")

    def test_early_confrontation_endings(self):
        e = self.engine
        self.assertEqual(e.get_ending(ELENA_ANSWER)[0], "Case Closed")
        for rid in list(e.riddles)[:15]:
            e.state.solved_riddles.append(rid)
        self.assertEqual(e.get_ending(ELENA_ANSWER)[0], "A Lead, Not a Victory")

    # --- Saving -----------------------------------------------------------------

    def test_save_load_roundtrip(self):
        e = self.engine
        self.solve_here()
        e.travel("Library")
        e.answer(e.current_riddle(), "__wrong__")
        e.save_game(2)
        e.new_game()
        self.assertTrue(e.load_game(2))
        self.assertEqual(e.state.current_location, "Library")
        self.assertEqual(e.state.unlocked_locations, ["ClientOffice", "Library"])
        self.assertEqual(e.state.sanity, 2)

    def test_autosave_feeds_continue(self):
        self.solve_here()
        fresh = GameEngine()
        self.assertTrue(fresh.load_game(0))
        self.assertEqual(fresh.state.solved_riddles, [1])


if __name__ == "__main__":
    unittest.main()
