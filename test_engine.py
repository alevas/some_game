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
from engine import INTERROGATIONS, STORY_ORDER, TRUSTING, InterrogationDataError, load_interrogations
from tips import TIPS, Tips


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
        placed = sorted(i for loc in LOCATIONS.values() for i in loc.riddle_ids + [loc.lead_riddle] if i)
        self.assertEqual(placed, sorted(r.id for r in RIDDLES))


    def test_pool_is_big_enough(self):
        self.assertGreaterEqual(len(RIDDLES), 60)
        for loc in LOCATIONS.values():
            if loc.riddle_ids:
                # enough spare riddles that two cases differ
                self.assertGreaterEqual(len(loc.riddle_ids), loc.riddles_per_case + 5, loc.id)
        for kind in ("choice", "type", "match", "order"):
            self.assertTrue(any(r.kind == kind for r in RIDDLES), kind)
        self.assertTrue(any(r.category == "reconstruction" for r in RIDDLES))

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

    # --- The daily case -------------------------------------------------------------

    def play_daily(self, day="2026-09-30"):
        """Start the daily case, solve it all, win the showdown"""
        e = self.engine
        e.start_daily(day)
        self.play_through()
        sd = e.start_showdown()
        while not sd.finished:
            sd.answer(sd.current.answer)
        return sd

    def test_seeded_pick_is_stable(self):
        """Same seed, same pick, on any computer and Python version (sha256, not random)"""
        self.assertEqual(engine.seeded_sample(list(range(10)), 3, "noir"), [5, 9, 6])

    def test_daily_case_is_the_same_for_everyone(self):
        e = self.engine
        self.assertFalse(e.start_daily("2026-09-30"))
        first = copy.deepcopy(e.state.selection)
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        other = GameEngine(Path(elsewhere.name))
        other.start_daily("2026-09-30")
        self.assertEqual(other.state.selection, first)
        self.assertEqual([r.id for r in e.start_showdown().riddles], [r.id for r in other.start_showdown().riddles])
        for loc in LOCATIONS.values():
            self.assertEqual(len(first[loc.id]), loc.riddles_per_daily_case)
        self.assertLess(len(e.case_riddles()), sum(l.riddles_per_case + bool(l.lead_riddle) for l in LOCATIONS.values()))
        days = {str(e.state.selection) for day in ("2026-10-01", "2026-10-02", "2026-10-03") if not e.start_daily(day)}
        self.assertGreater(len(days), 1, "another day, other riddles")
        self.assertRegex(engine.utc_today(), r"^\d{4}-\d\d-\d\d$")

    def test_daily_story_still_works(self):
        """The shorter case still unlocks every place and every beat"""
        sd = self.play_daily()
        e = self.engine
        self.assertEqual(e.state.unlocked_locations, list(LOCATIONS))
        for loc in LOCATIONS.values():
            self.assertEqual(len(e.beats_unlocked(loc.id)), len(loc.beats), loc.id)
        self.assertTrue(sd.won)
        self.assertEqual(e.get_ending(ELENA_ANSWER, True)[0], "The Truth Revealed")

    def test_daily_does_not_touch_the_normal_autosave(self):
        e = self.engine
        self.solve_here()  # a normal case, autosaved
        normal = copy.deepcopy(e.state)
        self.assertFalse(e.start_daily("2026-09-30"))
        self.solve_here()
        self.assertTrue((e.SAVE_DIR / "daily_autosave.json").exists())
        e.end_case()  # the daily case ends
        self.assertFalse((e.SAVE_DIR / "daily_autosave.json").exists())
        self.assertTrue(e.load_game(0))  # Continue: still the normal case
        self.assertEqual(e.state, normal)
        self.assertEqual(e.state.daily, "")

    def test_daily_case_resumes(self):
        e = self.engine
        e.start_daily("2026-09-30")
        self.solve_here()
        solved = list(e.state.solved_riddles)
        e.new_game()  # a new normal case in between doesn't lose it
        self.assertEqual(e.daily_status("2026-09-30"), "in progress")
        self.assertTrue(e.start_daily("2026-09-30"))
        self.assertEqual(e.state.solved_riddles, solved)
        self.assertFalse(e.start_daily("2026-10-01"), "yesterday's unfinished case is not today's")

    def test_daily_result_is_recorded_and_replays_are_marked(self):
        e = self.engine
        self.assertEqual(e.daily_status("2026-09-30"), "new")
        self.play_daily()
        share = e.finish_daily("The Truth Revealed", ELENA_ANSWER)
        lines = share.split("\n")
        self.assertEqual(lines[0], f"Noir Riddles · Daily 2026-09-30 · ♥♥♥ · {len(e.case_riddles())}/{len(e.case_riddles())}")
        self.assertEqual(lines[1].replace(" ", ""), "🟩" * len(e.case_riddles()))
        self.assertEqual(lines[2], "Volkov 🟩🟩🟩 · Elena found · The Truth Revealed")
        self.assertNotIn("replay", share)
        e.end_case()
        self.assertEqual(e.daily_status("2026-09-30"), "done")

        self.assertFalse(e.start_daily("2026-09-30"))
        self.assertTrue(e.state.replay)
        e.answer(e.current_riddle(), "__wrong__")
        e.answer(e.current_riddle(), "__wrong__")
        e.answer(e.current_riddle(), "__wrong__")
        replay = e.finish_daily("GAME OVER")
        self.assertIn("· replay", replay.split("\n")[0])
        self.assertIn("♡♡♡", replay)
        self.assertTrue(replay.split("\n")[1].startswith("🟥"))
        self.assertEqual(replay.split("\n")[2], f"Caught at {LOCATIONS['ClientOffice'].name}")
        record = e.daily_records()["2026-09-30"]
        self.assertEqual(record["share"], share, "the first result stands")
        self.assertEqual(record["replays"], 1)

    def test_daily_result_gives_nothing_away(self):
        e = self.engine
        self.play_daily()
        share = e.finish_daily("The Truth Revealed", ELENA_OPTIONS[1])
        self.assertIn("Elena lost", share)
        for rid in e.case_riddles():
            self.assertNotIn(e.riddles[rid].answer, share)
        self.assertNotIn(ELENA_ANSWER, share)

    def test_showdown_log(self):
        e = self.engine
        e.state.inventory = ["A"]
        sd = e.start_showdown()
        sd.answer("__wrong__")
        sd.answer(sd.current.answer)
        sd.dodge("A")
        sd.answer(sd.current.answer)
        self.assertEqual(e.state.showdown_log, ["slip", "dodge", "clean"])

    def test_normal_case_has_no_daily_result(self):
        self.assertIsNone(self.engine.finish_daily("Case Closed"))
        self.assertEqual(self.engine.daily_records(), {})

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
            pools = [rid for loc_id in so_far for rid in LOCATIONS[loc_id].riddle_ids + [LOCATIONS[loc_id].lead_riddle]]
            items = {e.riddles[rid].item for rid in pools if rid}
            for q in talk.questions:
                for item in q.evidence:
                    self.assertIn(item, items, f"{talk.character} ({q.id}): the {item} comes too late")
                self.assertLessEqual(q.after, len(e.riddles_at(talk.location)), f"{talk.character}: {q.id}")

    def test_every_case_can_break_every_lie_and_hear_every_reveal(self):
        """Whatever a case picks, and on the daily case too, the evidence the story needs is in it"""
        for pick in [engine.pick_riddles(), engine.pick_riddles(seed="daily/2026-09-30", daily=True)]:
            asked = {rid for ids in pick.values() for rid in ids} | {loc.lead_riddle for loc in LOCATIONS.values()}
            items = {self.engine.riddles[rid].item for rid in asked if rid}
            for loc in LOCATIONS.values():
                for item in loc.present:
                    self.assertIn(item, items, f"{loc.character} can't be shown the {item}")
            for talk in INTERROGATIONS.values():
                for q in talk.questions:
                    if q.lie:
                        self.assertTrue(items & set(q.evidence), f"{talk.character} ({q.id}) can't be broken")

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


class TipsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_each_tip_shows_once(self):
        tips = Tips(self.dir)
        self.assertEqual(tips.take("case"), "case")
        self.assertIsNone(tips.take("case"))
        self.assertEqual(tips.take("case", "lead"), "lead")
        self.assertIsNone(Tips(self.dir).take("case", "lead"))  # remembered in tips.json
        self.assertEqual(Tips(self.dir).take("nonsense", "evidence"), "evidence")

    def test_tips_can_be_turned_off_and_on(self):
        Tips(self.dir).set_enabled(False)
        tips = Tips(self.dir)
        self.assertIsNone(tips.take("case"))
        tips.set_enabled(True)
        self.assertEqual(Tips(self.dir).take("case"), "case")
        tips.reset()
        self.assertEqual(Tips(self.dir).take("case"), "case")

    def test_broken_tips_file_is_ignored(self):
        (self.dir / "tips.json").write_text("{not json")
        self.assertEqual(Tips(self.dir).take("case"), "case")

    def test_every_tip_has_text_for_both_versions(self):
        self.assertEqual(set(TIPS), {"case", "typing", "evidence", "lead", "archive", "interrogation"})
        for key, tip in TIPS.items():
            self.assertTrue(tip["title"] and tip["tui"] and tip["console"], key)


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
