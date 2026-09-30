"""Engine tests. Run with: python -m unittest"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import art
from engine import GameEngine, LOCATIONS, RIDDLES, VOLKOV_RIDDLES, ELENA_ANSWER, ELENA_OPTIONS, SHOWDOWN_ROUNDS
from engine import INTERROGATIONS, STORY_ORDER, TRUSTING, InterrogationDataError, load_interrogations


# A valid interrogations.toml to break in the loader tests
GOOD_TOML = '''
[[character]]
name = "Karl"
opening = "Coffee?"
refuse = "No."
wrong = ["Wrong."]
favor = "Here."

[[character.question]]
id = "elena"
ask = "Seen her?"
answer = "Never."
lie = true
evidence = ["Photograph"]
truth = "Every evening."
'''


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

    def test_separate_save_dirs_do_not_mix(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = GameEngine(Path(a)), GameEngine(Path(b))
            r = first.current_riddle()
            first.answer(r, r.answer)
            self.assertFalse(second.load_game(0))
            self.assertEqual(second.notebook, [])
            self.assertTrue(GameEngine(Path(a)).load_game(0))

    def test_autosave_feeds_continue(self):
        self.solve_here()
        fresh = GameEngine()
        self.assertTrue(fresh.load_game(0))
        self.assertEqual(fresh.state.solved_riddles, [1])

    # --- Interrogations -----------------------------------------------------------

    def visit(self, loc_id):
        self.engine.state.unlocked_locations.append(loc_id)
        self.engine.travel(loc_id)

    def test_every_character_can_be_questioned(self):
        self.assertEqual(set(INTERROGATIONS), {loc.character for loc in LOCATIONS.values()})
        for talk in INTERROGATIONS.values():
            self.assertEqual(LOCATIONS[talk.location].character, talk.character)
            self.assertTrue(3 <= len(talk.questions) <= 5, talk.character)
            self.assertEqual(len([q for q in talk.questions if q.lie]), 1, f"{talk.character} tells one lie")
            self.assertTrue(any(q.after == 0 for q in talk.questions), talk.character)
            self.assertTrue(any(q.after > 0 for q in talk.questions), talk.character)
            for q in talk.questions:
                self.assertEqual(bool(q.evidence and q.truth), q.lie, f"{talk.character}: {q.id}")

    def test_lies_break_with_evidence_you_can_have_by_then(self):
        """Evidence that breaks a lie comes from the character's location or an earlier one,
        and every question comes up before the location runs out of riddles"""
        e = self.engine
        for talk in INTERROGATIONS.values():
            so_far = STORY_ORDER[:STORY_ORDER.index(talk.location) + 1]
            items = {e.riddles[rid].item for loc_id in so_far for rid in e.riddles_at(loc_id)}
            for q in talk.questions:
                for item in q.evidence:
                    self.assertIn(item, items, f"{talk.character} ({q.id}): the {item} comes too late")
                self.assertLessEqual(q.after, len(e.riddles_at(talk.location)), f"{talk.character}: {q.id}")

    def test_bad_interrogation_file_says_where(self):
        cases = [
            (GOOD_TOML.replace('truth = "Every evening."', ''), ["Karl", "'elena'", "'truth' is missing"]),
            (GOOD_TOML.replace('"Karl"', '"Kurt"'), ["Kurt", "'name'", "Karl"]),
            (GOOD_TOML.replace('"Photograph"', '"Ray Gun"'), ["Karl", "'elena'", "'evidence'", "Ray Gun"]),
            (GOOD_TOML.replace("answer =", "anwser ="), ["Karl", "'elena'", "unknown field 'anwser'"]),
            (GOOD_TOML.replace("lie = true", "after = -1\nlie = true"), ["Karl", "'elena'", "'after'"]),
            (GOOD_TOML.replace('wrong = ["Wrong."]', 'wrong = "Wrong."'), ["Karl", "'wrong'"]),
            (GOOD_TOML.replace("lie = true", "lie = false"), ["Karl", "'elena'", "lie = true"]),
            (GOOD_TOML.replace('favor = "Here."', 'favor = "Here'), ["not valid TOML"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "interrogations.toml"
            path.write_text(GOOD_TOML)
            self.assertEqual(load_interrogations(path)["Karl"].questions[0].evidence, ["Photograph"])
            for text, expected in cases:
                path.write_text(text)
                with self.assertRaises(InterrogationDataError) as caught:
                    load_interrogations(path)
                message = str(caught.exception)
                for part in ["interrogations.toml"] + expected:
                    self.assertIn(part, message)
            with self.assertRaises(InterrogationDataError):
                load_interrogations(Path(tmp) / "missing.toml")

    def test_questions_unlock_as_riddles_are_solved(self):
        e = self.engine
        self.solve_here()
        e.travel("Library")
        self.assertEqual([q.id for q in e.questions()], ["work", "readers"])
        self.assertEqual(e.locked_questions(), 2)
        self.solve_here()
        self.solve_here()
        self.assertIn("elsewhere", [q.id for q in e.questions()])

    def test_right_evidence_breaks_a_lie(self):
        e = self.engine
        self.solve_here()  # Case File
        self.assertIn("home all day", e.ask("last-seen"))
        result = e.press("last-seen", "Case File")
        self.assertTrue(result.broken)
        self.assertEqual(result.line, e.ask("last-seen"))  # asking again gets the truth
        self.assertEqual(e.trust_label("Klaus Weber"), "trusting")
        self.assertEqual(e.state.sanity, 3)
        self.assertIn("Case File", e.state.inventory)  # pressing doesn't use it up
        self.assertTrue(any("caught in a lie" in note and "Staatsbibliothek" in note for _, note in e.case_notes()))

    def test_wrong_evidence_costs_trust_and_a_heart(self):
        e = self.engine
        self.solve_here()
        e.travel("Library")
        self.solve_here()
        self.solve_here()
        result = e.press("elsewhere", "Case File")  # the lie, but the wrong evidence
        self.assertFalse(result.broken)
        self.assertTrue(result.heart_lost)
        self.assertTrue(result.clammed_up)
        self.assertEqual(e.state.sanity, 2)
        self.assertEqual(e.trust_label("Herr Schmidt"), "distrustful")
        self.assertEqual(e.ask("work"), INTERROGATIONS["Herr Schmidt"].refuse)
        self.assertIn("here", e.mend_advice())
        self.solve_here()  # another riddle here wins him back
        self.assertFalse(e.refuses())
        self.assertEqual(e.trust_label("Herr Schmidt"), "guarded")

    def test_pressing_the_truth_is_wrong_too(self):
        e = self.engine
        self.solve_here()
        self.assertFalse(e.press("sister", "Case File").broken)
        self.assertTrue(e.refuses())
        self.assertIn("anywhere", e.mend_advice())  # nothing left to solve in his office
        e.travel("Library")
        self.solve_here()
        self.assertFalse(e.refuses("ClientOffice"))

    def test_wrong_evidence_never_takes_the_last_heart(self):
        e = self.engine
        self.solve_here()
        e.state.sanity = 1
        result = e.press("sister", "Case File")
        self.assertFalse(result.heart_lost)
        self.assertEqual(e.state.sanity, 1)
        self.assertFalse(e.is_game_over())

    def test_trusting_character_owes_one_free_hint(self):
        e = self.engine
        self.solve_here()
        self.assertEqual(e.favors(), [])
        self.assertIsNone(e.call_in_favor("Klaus Weber"))
        e.press("last-seen", "Case File")
        self.assertEqual(e.favors(), ["Klaus Weber"])
        self.assertEqual(e.call_in_favor("Klaus Weber"), INTERROGATIONS["Klaus Weber"].favor)
        self.assertEqual(e.favors(), [])
        e.new_game()
        self.assertEqual(e.trust("Klaus Weber"), 0)

    def test_father_thomas_blesses_you_before_the_showdown(self):
        e = self.engine
        e.state.inventory.append("Sugar Packet")
        self.visit("Church")
        self.solve_here()
        self.solve_here()
        e.state.sanity = 1
        self.assertIsNone(e.receive_blessing())  # he doesn't trust you yet
        self.assertIn("Nothing living", e.ask("crypt"))
        self.assertTrue(e.press("crypt", "Sugar Packet").broken)
        who, line = e.receive_blessing()
        self.assertEqual(who, "Father Thomas")
        self.assertEqual(e.state.sanity, 2)
        e.state.sanity = e.state.max_sanity
        self.assertIsNone(e.receive_blessing())  # nothing to restore

    def test_volkov_can_be_caught_before_the_showdown(self):
        e = self.engine
        e.state.inventory.append("Parish Ledger")
        self.visit("Archive")
        self.assertNotIn("church", [q.id for q in e.questions()])
        self.solve_here()
        self.solve_here()
        self.assertTrue(e.press("church", "Parish Ledger").broken)
        self.assertEqual(e.trust_label("Igor Volkov"), "trusting")

    def test_interrogations_survive_save_and_load(self):
        e = self.engine
        self.solve_here()
        e.ask("sister")
        e.ask("last-seen")
        e.press("last-seen", "Case File")
        e.save_game(1)
        e.new_game()
        self.assertTrue(e.load_game(1))
        self.assertEqual(e.trust("Klaus Weber"), TRUSTING)
        self.assertTrue(all(e.was_asked(q) for q in e.questions() if q.id in ("sister", "last-seen")))
        self.assertEqual([q.id for q in e.caught_lies("ClientOffice")], ["last-seen"])


if __name__ == "__main__":
    unittest.main()
