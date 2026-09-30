"""Engine tests. Run with: python -m unittest"""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import art
import engine
from engine import GameEngine, LOCATIONS, RIDDLES, VOLKOV_RIDDLES, ELENA_ANSWER, ELENA_OPTIONS, SHOWDOWN_ROUNDS
from engine import DataError, load_game_data, read_toml


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
        placed = sorted(i for loc in LOCATIONS.values() for i in loc.riddle_ids + [loc.lead_riddle] if i)
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
            elif r.kind == "order":
                self.assertEqual(r.answer, "|".join(r.sequence), r.id)
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

    def test_order_letters(self):
        e = self.engine
        r = e.riddles[64]
        self.assertEqual(r.kind, "order")
        for _ in range(30):  # shuffled, but never already in order
            self.assertNotEqual(e.match_options(r), r.sequence)
        shown = ["French magasin", "Arabic makhāzin", "English magazine", "Italian magazzino"]
        self.assertTrue(GameEngine.is_correct(r, e.match_response(r, shown, "B D A C")))
        self.assertFalse(GameEngine.is_correct(r, e.match_response(r, shown, "BADC")))
        self.assertIsNone(e.match_response(r, shown, "BDA"))
        self.assertEqual(r.display_answer(), "Arabic makhāzin → Italian magazzino → French magasin → English magazine")

    def test_family_tree_diagram(self):
        trees = [r for r in RIDDLES if r.diagram]
        self.assertGreaterEqual(len(trees), 5)
        for r in trees:
            self.assertEqual(r.kind, "choice", r.id)
            self.assertIn("???", r.diagram, r.id)
            self.assertGreater(r.diagram.count("\n"), 2, r.id)
            self.assertLessEqual(max(len(line) for line in r.diagram.split("\n")), 56, r.id)

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
        case = e.case_riddles()
        e.state.solved_riddles.extend(case[:len(case) // 2 + 1])
        self.assertEqual(e.get_ending(ELENA_ANSWER, False)[0], "A Lead, Not a Victory")

    # --- One case, a handful of each pool -------------------------------------------

    def test_each_case_picks_from_the_pools(self):
        e = self.engine
        for loc in LOCATIONS.values():
            picked = e.state.selection[loc.id]
            self.assertEqual(len(picked), loc.riddles_per_case, loc.id)
            self.assertEqual(picked, [rid for rid in loc.riddle_ids if rid in picked], "kept in pool order")
            self.assertNotIn(loc.lead_riddle, picked)
            if loc.lead_riddle:
                self.assertEqual(e.riddles_at(loc.id)[-1], loc.lead_riddle, "the lead is always asked")
        picks = set()
        for _ in range(5):
            e.new_game()
            picks.add(str(e.state.selection))
        self.assertGreater(len(picks), 1, "new cases pick different riddles")

    def test_counts_follow_the_case(self):
        e = self.engine
        case = e.case_riddles()
        self.assertEqual(len(case), sum(l.riddles_per_case + bool(l.lead_riddle) for l in LOCATIONS.values()))
        self.assertEqual(e.progress("Library")[1], LOCATIONS["Library"].riddles_per_case + 1)
        self.assertEqual(e.total_items(), sum(1 for rid in case if e.riddles[rid].item))
        self.assertLess(len(case), len(RIDDLES))

    def test_beats_and_leads_fit_the_case(self):
        """Every beat can be heard and every lead reached, in a full case and a daily one"""
        for daily in (False, True):
            e = self.engine
            e.state.selection = engine.pick_riddles(seed="test", daily=daily) if daily else engine.pick_riddles()
            for loc in LOCATIONS.values():
                total = len(e.riddles_at(loc.id))
                thresholds = [e.needed(loc.id, after) for after, _ in loc.beats]
                self.assertEqual(len(set(thresholds)), len(thresholds), (loc.id, daily))
                self.assertLessEqual(max(thresholds, default=0), total, (loc.id, daily))
                self.assertLessEqual(e.needed(loc.id, loc.lead_after), len(e.state.selection[loc.id]), (loc.id, daily))

    def test_perfect_run_hears_every_beat(self):
        self.play_through()
        e = self.engine
        for loc in LOCATIONS.values():
            self.assertEqual(len(e.beats_unlocked(loc.id)), len(loc.beats), loc.id)
        self.assertEqual(sorted(e.state.solved_riddles), sorted(e.case_riddles()))
        self.assertEqual(e.solved_count(), len(e.case_riddles()))

    def test_saves_keep_the_case(self):
        e = self.engine
        self.solve_here()
        picked = copy.deepcopy(e.state.selection)
        fresh = GameEngine()
        self.assertTrue(fresh.load_game(0))  # Continue
        self.assertEqual(fresh.state.selection, picked)
        e.save_game(1)
        e.new_game()
        self.assertNotEqual(e.state.selection, picked)
        self.assertTrue(e.load_game(1))
        self.assertEqual(e.state.selection, picked)

    def test_old_saves_get_a_case(self):
        """A save from before pools keeps what was solved, and fills up each place"""
        e = self.engine
        with open(e.SAVE_DIR / "slot_3.json", "w") as f:
            json.dump({"current_location": "Library", "solved_riddles": [1, 2, 3, 9, 31],
                       "unlocked_locations": ["ClientOffice", "Library", "Cafe"], "sanity": 2, "score": 50}, f)
        self.assertTrue(e.load_game(3))
        library = e.state.selection["Library"]
        self.assertTrue({3, 9, 31} <= set(library))
        self.assertEqual(len(library), LOCATIONS["Library"].riddles_per_case)
        self.assertEqual(e.progress("Library")[0], 4)  # three riddles and the lead
        for loc in LOCATIONS.values():
            self.assertEqual(len(e.state.selection[loc.id]), loc.riddles_per_case)

    def test_saved_riddle_removed_from_the_data(self):
        e = self.engine
        e.state.selection["Library"] = [3, 9999]
        e.save_game(2)
        self.assertTrue(e.load_game(2))
        self.assertEqual(e.state.selection["Library"], [3])

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


class DataFileTest(unittest.TestCase):
    """The data files are checked on load, and mistakes are reported in words"""

    @classmethod
    def setUpClass(cls):
        cls.riddles_doc = read_toml("riddles.toml")
        cls.story_doc = read_toml("story.toml")

    def docs(self):
        return copy.deepcopy(self.riddles_doc), copy.deepcopy(self.story_doc)

    @staticmethod
    def riddle(doc, rid):
        return next(t for t in doc["riddle"] + doc["volkov_riddle"] if t["id"] == rid)

    @staticmethod
    def place(doc, loc_id):
        return next(t for t in doc["location"] if t["id"] == loc_id)

    def assertDataError(self, riddles_doc, story_doc, *fragments):
        with self.assertRaises(DataError) as caught:
            load_game_data(riddles_doc, story_doc)
        for fragment in fragments:
            self.assertIn(fragment, str(caught.exception))

    def test_real_files_load(self):
        data = load_game_data(*self.docs())
        self.assertEqual([r.id for r in data.riddles], [r.id for r in RIDDLES])
        self.assertEqual(list(data.locations), list(LOCATIONS))

    def test_long_text_lines_are_joined(self):
        riddles, story = self.docs()
        self.riddle(riddles, 3)["explanation"] = "First line.\n   Second line.\n"
        data = load_game_data(riddles, story)
        self.assertEqual(next(r for r in data.riddles if r.id == 3).explanation, "First line. Second line.")

    def test_missing_field(self):
        riddles, story = self.docs()
        del self.riddle(riddles, 3)["answer"]
        self.assertDataError(riddles, story, "data/riddles.toml, riddle 3", "missing field 'answer'")

    def test_misspelt_field(self):
        riddles, story = self.docs()
        self.riddle(riddles, 3)["hnit"] = "..."
        self.assertDataError(riddles, story, "riddle 3", "unknown field 'hnit'")

    def test_wrong_type(self):
        riddles, story = self.docs()
        self.riddle(riddles, 3)["difficulty"] = "hard"
        self.assertDataError(riddles, story, "riddle 3", "'difficulty' should be a whole number")

    def test_duplicate_id(self):
        riddles, story = self.docs()
        self.riddle(riddles, 9)["id"] = 3
        self.assertDataError(riddles, story, "two riddles have id 3")

    def test_answer_among_its_options(self):
        riddles, story = self.docs()
        self.riddle(riddles, 3)["decoys"] = ["book", "Page"]
        self.assertDataError(riddles, story, "riddle 3", "the answer 'Book' is also listed")

    def test_too_many_options(self):
        riddles, story = self.docs()
        self.riddle(riddles, 3)["wrong_answers"] += ["Scroll", "Tome"]
        self.assertDataError(riddles, story, "riddle 3", "1 to 3 wrong_answers")

    def test_field_of_another_kind(self):
        riddles, story = self.docs()
        self.riddle(riddles, 31)["decoys"] = ["hand", "leg"]
        self.assertDataError(riddles, story, "riddle 31", "'decoys' does not belong in a type riddle")

    def test_order_needs_three_steps(self):
        riddles, story = self.docs()
        self.riddle(riddles, 64)["sequence"] = ["Arabic makhāzin", "English magazine"]
        self.assertDataError(riddles, story, "riddle 64", "3 to 6 steps")

    def test_diagram_only_on_choice_riddles(self):
        riddles, story = self.docs()
        self.riddle(riddles, 31)["diagram"] = "a\n|\nb"
        self.assertDataError(riddles, story, "riddle 31", "'diagram' does not belong in a type riddle")

    def test_diagram_layout_is_kept(self):
        riddles, story = self.docs()
        self.riddle(riddles, 42)["diagram"] = "\n      Latin\n        |\n   +----+----+\n  ???\n\n"
        data = load_game_data(riddles, story)
        self.assertEqual(next(r for r in data.riddles if r.id == 42).diagram,
                         "    Latin\n      |\n +----+----+\n???")
        self.riddle(riddles, 42)["diagram"] = "x" * 57
        self.assertDataError(riddles, story, "riddle 42", "wider than 56")

    def test_unknown_location(self):
        riddles, story = self.docs()
        self.riddle(riddles, 3)["location"] = "Libary"
        self.assertDataError(riddles, story, "riddle 3", 'unknown location "Libary"')

    def test_lead_placed_elsewhere(self):
        riddles, story = self.docs()
        self.riddle(riddles, 2)["location"] = "Cafe"
        self.assertDataError(riddles, story, 'data/story.toml, location "Library"', "lead_riddle 2")

    def test_unknown_evidence(self):
        riddles, story = self.docs()
        self.place(story, "Cafe")["present"][0]["evidence"] = "Sugar Pakcet"
        self.assertDataError(riddles, story, 'location "Cafe"', "Sugar Pakcet")

    def test_character_without_portrait(self):
        riddles, story = self.docs()
        self.place(story, "Cafe")["character"] = "Carl"
        self.assertDataError(riddles, story, 'location "Cafe"', "no portrait for 'Carl'")

    def test_unreachable_location(self):
        riddles, story = self.docs()
        self.place(story, "Cafe")["leads_to"] = "Library"
        self.assertDataError(riddles, story, 'reaches "Church"')

    def test_elena_answer_must_be_an_option(self):
        riddles, story = self.docs()
        story["elena"]["answer"] = "The crypt"
        self.assertDataError(riddles, story, "[elena]", "not one of the options")

    def test_syntax_error_names_the_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "story.toml").write_text('[[location]]\nid = "Cafe\n', encoding="utf-8")
            with mock.patch.object(engine, "DATA_DIR", Path(tmp)):
                with self.assertRaises(DataError) as caught:
                    read_toml("story.toml")
        self.assertIn("data/story.toml", str(caught.exception))
        self.assertIn("line 2", str(caught.exception))

    def test_bundled_data_dir(self):
        """A PyInstaller onefile build unpacks data/ under sys._MEIPASS"""
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(engine.DATA_DIR, Path(tmp, "data"))
            code = f"import sys; sys._MEIPASS = {tmp!r}; import engine; print(engine.DATA_DIR)"
            out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                 cwd=Path(engine.__file__).parent, check=True).stdout
        self.assertEqual(out.strip(), str(Path(tmp, "data")))


if __name__ == "__main__":
    unittest.main()
