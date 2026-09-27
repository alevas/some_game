"""Engine tests. Run with: python -m unittest"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import art
from engine import GameEngine, LOCATIONS, RIDDLES, VOLKOV_RIDDLES, ELENA_ANSWER, ELENA_OPTIONS, SHOWDOWN_ROUNDS


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

    def play_through(self):
        """Solve every riddle, following the story in order"""
        e = self.engine
        while not e.all_riddles_solved():
            if e.current_riddle() is None:
                nxt = next(l.id for l in e.unlocked_locations() if e.progress(l.id)[0] < e.progress(l.id)[1])
                e.travel(nxt)
            self.solve_here()
            e.state.sanity = e.state.max_sanity  # keep the run alive

    # --- Data -----------------------------------------------------------------

    def test_every_riddle_placed_once(self):
        placed = sorted(i for loc in LOCATIONS.values() for i in self.engine.riddles_at(loc.id))
        self.assertEqual(placed, sorted(r.id for r in RIDDLES))

    def test_riddles_are_well_formed(self):
        ids = [r.id for r in RIDDLES + VOLKOV_RIDDLES]
        self.assertEqual(len(ids), len(set(ids)))
        for r in RIDDLES + VOLKOV_RIDDLES:
            if r.kind == "choice":
                options = [r.answer] + r.wrong_answers + r.decoys
                self.assertEqual(len({o.lower() for o in options}), len(options), r.id)
                self.assertLessEqual(len(r.wrong_answers) + 1, 4, f"riddle {r.id} has more options than number keys")
                self.assertEqual(len(r.decoys), 2, r.id)
            elif r.kind == "match":
                self.assertEqual(r.answer, "|".join(right for _, right in r.pairs), r.id)
            else:
                self.assertEqual(r.kind, "type", r.id)
                self.assertFalse(r.wrong_answers, r.id)

    def test_every_character_has_every_mood(self):
        for loc in LOCATIONS.values():
            self.assertEqual(set(art.PORTRAITS[loc.character]), {"neutral", "good", "bad"})
            self.assertIn(loc.id, art.SCENES)

    def test_elena_answer_is_an_option(self):
        self.assertIn(ELENA_ANSWER, ELENA_OPTIONS)
        self.assertNotEqual(ELENA_OPTIONS[0], ELENA_ANSWER, "the default highlight would give it away")

    def test_presentable_evidence_exists(self):
        items = {r.item for r in RIDDLES if r.item}
        for loc in LOCATIONS.values():
            for item in loc.present:
                self.assertIn(item, items, loc.id)

    # --- Riddle kinds -------------------------------------------------------------

    def test_typed_answers_are_forgiving(self):
        foot = self.engine.riddles[31]
        for response in ["foot", " Foot. ", "FEET"]:
            self.assertTrue(GameEngine.is_correct(foot, response), response)
        self.assertFalse(GameEngine.is_correct(foot, "hand"))

    def test_match_letters(self):
        e = self.engine
        r = e.riddles[36]
        shown = ["boss", "advice", "to receive"]
        self.assertTrue(GameEngine.is_correct(r, e.match_response(r, shown, "b c a")))
        self.assertFalse(GameEngine.is_correct(r, e.match_response(r, shown, "abc")))
        self.assertIsNone(e.match_response(r, shown, "AAB"))
        self.assertIsNone(e.match_response(r, shown, "AB"))

    def test_cipher_wheel_helps(self):
        e = self.engine
        cipher = e.riddles[39]
        self.assertIsNone(e.item_help(cipher))
        e.state.inventory.append("Cipher Wheel")
        self.assertIn("three", e.item_help(cipher))

    # --- Evidence ---------------------------------------------------------------

    def test_presenting_evidence_reveals_a_note(self):
        e = self.engine
        self.solve_here()  # Case File
        e.travel("Library")
        self.assertIsNone(e.present("Lantern"))
        text = e.present("Case File")
        self.assertIn("St. Nicholas", text)
        self.assertTrue(any("shown the Case File" in note for _, note in e.case_notes()))

    def test_spending_evidence(self):
        e = self.engine
        self.solve_here()
        self.assertTrue(e.spend_item("Case File"))
        self.assertEqual(e.state.inventory, [])
        self.assertFalse(e.spend_item("Case File"))

    # --- Showdown ---------------------------------------------------------------

    def test_showdown_win(self):
        sd = self.engine.start_showdown()
        while not sd.finished:
            sd.answer(sd.current.answer)
        self.assertTrue(sd.won)

    def test_showdown_dodge_with_evidence(self):
        e = self.engine
        e.state.inventory = ["A", "B", "C"]
        sd = e.start_showdown()
        for item in ["A", "B", "C"]:
            self.assertTrue(sd.dodge(item))
        self.assertTrue(sd.won)
        self.assertEqual(e.state.inventory, [])

    def test_showdown_loss(self):
        e = self.engine
        sd = e.start_showdown()
        for _ in range(e.state.sanity):
            self.assertFalse(sd.answer("__wrong__"))
        self.assertTrue(sd.finished)
        self.assertFalse(sd.won)
        self.assertEqual(len(sd.riddles), SHOWDOWN_ROUNDS)

    # --- Notebook ---------------------------------------------------------------

    def test_notebook_survives_new_cases(self):
        e = self.engine
        self.solve_here()
        e.new_game()
        self.assertEqual([r.id for r in GameEngine().notebook_entries()], [1])

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
        title, text = self.engine.get_ending(ELENA_ANSWER, volkov_beaten=True)
        self.assertEqual(title, "The Truth Revealed")
        self.assertIn("alive", text)

    def test_wrong_deduction_blocks_best_ending(self):
        self.play_through()
        title, text = self.engine.get_ending(ELENA_OPTIONS[1], volkov_beaten=True)
        self.assertEqual(title, "Partial Victory")
        self.assertIn("never seen again", text)

    def test_losing_the_showdown_blocks_best_ending(self):
        self.play_through()
        self.assertEqual(self.engine.get_ending(ELENA_ANSWER, volkov_beaten=False)[0], "A Lead, Not a Victory")

    def test_early_confrontation_endings(self):
        e = self.engine
        self.assertEqual(e.get_ending(ELENA_ANSWER, False)[0], "Case Closed")
        self.assertEqual(e.get_ending(ELENA_ANSWER, True)[0], "Partial Victory")
        for rid in list(e.riddles)[:len(e.riddles) // 2 + 1]:
            e.state.solved_riddles.append(rid)
        self.assertEqual(e.get_ending(ELENA_ANSWER, False)[0], "A Lead, Not a Victory")

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
