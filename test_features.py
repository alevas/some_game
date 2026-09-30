"""Tests for difficulty modes, save codes, achievements and settings. Run with: python -m unittest"""

import json
import os
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock

import savecode
from achievements import ACHIEVEMENTS, Achievements, case_riddles
from engine import (GameEngine, GameState, SaveCodeError, DIFFICULTIES, ALL_RIDDLES, ELENA_ANSWER,
                    ELENA_OPTIONS, SHOWDOWN_ROUNDS, VOLKOV_RIDDLES)
from settings import Settings


class FeatureTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.save_dir = Path(tmp.name)
        patcher = mock.patch.object(GameEngine, "SAVE_DIR", self.save_dir)
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

    def solve_next(self):
        """Solve the next riddle, moving on when a location runs out (however many riddles it has)"""
        e = self.engine
        if e.current_riddle() is None:
            e.travel(next(l.id for l in e.unlocked_locations() if e.progress(l.id)[0] < e.progress(l.id)[1]))
        return self.solve_here()

    def play_through(self):
        """Solve every riddle cleanly, following the story in order"""
        while not self.engine.all_riddles_solved():
            self.solve_next()

    def win_showdown(self, guess=ELENA_ANSWER):
        sd = self.engine.start_showdown(guess)
        while not sd.finished:
            sd.answer(sd.current.answer)
        return sd


class DifficultyTest(FeatureTest):
    def test_detective_keeps_the_old_rules(self):
        rules = DIFFICULTIES["detective"]
        self.assertEqual(rules.hearts, GameState().max_sanity)
        self.assertEqual(rules.showdown_rounds, SHOWDOWN_ROUNDS)
        self.assertEqual(self.engine.difficulty(), rules)

    def test_new_game_sets_hearts(self):
        for key, rules in DIFFICULTIES.items():
            self.engine.new_game(key)
            s = self.engine.state
            self.assertEqual((s.difficulty, s.sanity, s.max_sanity), (key, rules.hearts, rules.hearts))
        self.assertEqual(DIFFICULTIES["rookie"].hearts, 5)
        self.assertEqual(DIFFICULTIES["noir"].hearts, 2)

    def test_hint_costs(self):
        e = self.engine
        e.new_game("rookie")
        self.assertEqual((e.hint_cost(False), e.hint_cost(True)), ("free", "free"))
        e.new_game("detective")
        self.assertEqual((e.hint_cost(False), e.hint_cost(True)), ("evidence", "free"))
        e.new_game("noir")
        self.assertEqual((e.hint_cost(False), e.hint_cost(True)), (None, None))

    def test_noir_streak_never_restores_a_heart(self):
        e = self.engine
        e.new_game("noir")
        self.solve_here(wrong_first=True)  # 1 heart left
        results = [self.solve_next() for _ in range(3)]
        self.assertEqual(e.state.streak, 3)
        self.assertFalse(any(r.heart_restored for r in results))
        self.assertEqual(e.state.sanity, 1)

    def test_showdown_length_follows_difficulty(self):
        for key, rules in DIFFICULTIES.items():
            self.engine.new_game(key)
            self.assertEqual(len(self.engine.start_showdown().riddles), min(rules.showdown_rounds, len(VOLKOV_RIDDLES)))

    def test_difficulty_is_saved(self):
        e = self.engine
        e.new_game("noir")
        self.solve_here()
        e.save_game(1)
        self.assertIn("Noir", e.get_save_slots()[0][2])
        e.new_game()
        self.assertTrue(e.load_game(1))
        self.assertEqual(e.difficulty().name, "Noir")
        self.assertEqual(e.state.max_sanity, 2)

    def test_old_saves_load_as_detective(self):
        data = asdict(GameState())
        del data["difficulty"]
        (self.save_dir / "slot_2.json").write_text(json.dumps(data))
        self.assertTrue(self.engine.load_game(2))
        self.assertEqual(self.engine.state.difficulty, "detective")

    def test_unknown_difficulty_plays_as_detective(self):
        self.engine.state.difficulty = "impossible"
        self.assertEqual(self.engine.difficulty(), DIFFICULTIES["detective"])


class SaveCodeTest(FeatureTest):
    def advance(self):
        e = self.engine
        e.new_game("rookie")
        self.solve_here()
        e.travel("Library")
        self.solve_here(wrong_first=True)
        self.solve_here()
        e.present("Case File")

    def test_round_trip(self):
        self.advance()
        code = self.engine.save_code()
        self.assertRegex(code, rf"^N{savecode.VERSION}(-[A-Z2-7]{{1,5}})+$")
        other = GameEngine(Path(tempfile.mkdtemp(dir=self.save_dir)))
        other.load_code(code)
        self.assertEqual(asdict(other.state), asdict(self.engine.state))
        self.assertTrue(other.load_game(0), "a loaded code becomes the case in progress")

    def test_fresh_case_code_is_short(self):
        # A fresh case still holds its random pick of riddles, one number per place
        self.assertLess(len(self.engine.save_code()), 100)

    def test_version_1_codes_still_load(self):
        data = asdict(self.engine.state)
        data["score"] = 55
        del data["selection"], data["daily"], data["replay"], data["showdown_log"]  # not in version 1
        code = savecode.encode(data, version=1)
        self.assertTrue(code.startswith("N1-"))
        self.engine.load_code(code)
        self.assertEqual(self.engine.state.score, 55)
        self.assertTrue(self.engine.state.selection, "a version 1 case gets riddles picked when it loads")

    def test_every_field_is_included(self):
        data = savecode.decode(self.engine.save_code())
        self.assertEqual(set(data), set(GameState.__dataclass_fields__))
        # Fields added later ride along without any changes here
        extra = dict(asdict(GameState()), daily="2026-09-30", trust={"Karl": 2})
        self.assertEqual(savecode.decode(savecode.encode(extra)), extra)

    def test_forgiving_about_how_it_is_typed(self):
        self.advance()
        code = self.engine.save_code()
        prefix, body = code[:2], code[2:]
        sloppy = [
            code.lower(),
            code.replace("-", " "),
            "\n".join(savecode.lines(code, groups=3)),
            prefix + body.replace("O", "0").replace("I", "1").replace("B", "8"),
            "  " + code.replace("-", "") + "  ",
        ] + (["nl" + body] if prefix == "N1" else [])
        for text in sloppy:
            self.assertEqual(savecode.decode(text), savecode.decode(code), text)

    def assertRejected(self, code, fragment):
        with self.assertRaises(SaveCodeError) as caught:
            savecode.decode(code)
        self.assertIn(fragment, str(caught.exception))

    def test_bad_codes_are_rejected_clearly(self):
        self.advance()
        code = self.engine.save_code()
        i = len(code) // 2
        while code[i] == "-":
            i += 1
        swapped = "A" if code[i] != "A" else "B"
        self.assertRejected("", "Type or paste")
        self.assertRejected("hello detective", "isn't a save code")
        self.assertRejected("N9" + code[2:], "different version")
        self.assertRejected("N0-ABCDE", "different version")
        self.assertRejected(code[:i] + "9" + code[i + 1:], "never contain 9")
        self.assertRejected(code[:i] + swapped + code[i + 1:], "doesn't check out")
        self.assertRejected(code[:i] + code[i + 1:], "")
        self.assertRejected(code[:-6], "")
        self.assertRejected("N1-AAAAA-AAAAA", "check")
        self.assertRejected("N1" + "A" * 6000, "too long")

    def test_valid_checksum_but_not_a_case(self):
        with self.assertRaises(SaveCodeError):
            savecode.decode(savecode.encode([1, 2, 3]))
        with self.assertRaises(SaveCodeError):
            self.engine.load_code(savecode.encode({"sanity": "plenty"}))

    def test_bad_code_changes_nothing(self):
        self.advance()
        before = asdict(self.engine.state)
        autosave = (self.save_dir / "autosave.json").read_text()
        for bad in ["N1-ZZZZZ", savecode.encode({"solved_riddles": "all"})]:
            with self.assertRaises(SaveCodeError):
                self.engine.load_code(bad)
        self.assertEqual(asdict(self.engine.state), before)
        self.assertEqual((self.save_dir / "autosave.json").read_text(), autosave)

    def test_codes_from_before_new_fields_still_load(self):
        data = asdict(GameState())
        data["score"] = 40
        del data["difficulty"], data["presented"]
        self.engine.load_code(savecode.encode(data))
        self.assertEqual(self.engine.state.score, 40)
        self.assertEqual(self.engine.state.difficulty, "detective")
        self.assertEqual(self.engine.state.presented, [])


class AchievementTest(FeatureTest):
    def setUp(self):
        super().setUp()
        self.tracker = Achievements(self.engine)

    def unlocked(self):
        return set(self.tracker.unlocked)

    def test_definitions(self):
        ids = [a.id for a in ACHIEVEMENTS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(10 <= len(ids) <= 12)
        for a in ACHIEVEMENTS:
            self.assertTrue(a.name and a.hint and a.text, a.id)

    def test_nothing_for_starting_out(self):
        self.solve_here()
        self.assertEqual(self.unlocked(), set())

    def test_persisted_and_announced_once(self):
        self.play_through()
        self.win_showdown()
        announced = self.tracker.take_pending()
        self.assertEqual({a.id for a in announced}, self.unlocked())
        self.assertEqual(self.tracker.take_pending(), [])
        self.assertEqual(set(Achievements(GameEngine()).unlocked), self.unlocked())

    def test_perfect_case(self):
        self.play_through()
        self.win_showdown()
        got = self.unlocked()
        # Bookworm (half the notebook) needs more than one case now that the pool is bigger
        for aid in ["sherlock", "clean_sweep", "bare_hands", "hot_streak", "rookie_win", "detective_win"]:
            self.assertIn(aid, got)
        # These depend on the case's random pick of riddles
        e = self.engine
        asked = [e.riddles[rid] for rid in e.case_riddles()]
        has_sound_shifts = any(r.category == "sound shift" for r in asked)
        self.assertEqual("grimm_reaper" in got, has_sound_shifts)
        languages = {r.language for r in asked} | {e.riddles[rid].language for rid in e.notebook if rid in e.riddles}
        if len(languages) >= 10:
            self.assertIn("polyglot", got)
        self.assertNotIn("noir_win", got)
        self.assertNotIn("close_shave", got)

    def test_a_single_slip_costs_the_clean_sweep(self):
        self.solve_here(wrong_first=True)
        self.play_through()
        self.win_showdown()
        self.assertNotIn("clean_sweep", self.unlocked())
        self.assertIn("sherlock", self.unlocked())

    def test_wrong_guess(self):
        self.win_showdown(guess=ELENA_OPTIONS[0])
        self.assertNotIn("sherlock", self.unlocked())
        self.assertIn("rookie_win", self.unlocked())

    def test_lost_showdown_still_finds_elena(self):
        sd = self.engine.start_showdown(ELENA_ANSWER)
        while not sd.finished:
            sd.answer("__wrong__")
        self.assertEqual(self.unlocked(), {"sherlock"})

    def test_throwing_evidence_costs_bare_hands(self):
        e = self.engine
        e.state.inventory = ["Case File"]
        sd = e.start_showdown()
        sd.dodge("Case File")
        while not sd.finished:
            sd.answer(sd.current.answer)
        self.assertTrue(sd.won)
        self.assertIn("rookie_win", self.unlocked())
        self.assertNotIn("bare_hands", self.unlocked())

    def test_close_shave(self):
        self.engine.state.sanity = 2
        sd = self.engine.start_showdown()
        sd.answer("__wrong__")
        while not sd.finished:
            sd.answer(sd.current.answer)
        self.assertIn("close_shave", self.unlocked())

    def test_victories_count_harder_difficulties(self):
        self.engine.new_game("noir")
        self.win_showdown()
        self.assertTrue({"rookie_win", "detective_win", "noir_win"} <= self.unlocked())

    def test_rookie_victory_only(self):
        self.engine.new_game("rookie")
        self.win_showdown()
        self.assertIn("rookie_win", self.unlocked())
        self.assertNotIn("detective_win", self.unlocked())

    def test_grimm_reaper_finds_sound_shifts_by_category(self):
        e = self.engine
        shifts = [r for r in case_riddles(e) if r.category == "sound shift"]
        if not shifts:
            self.skipTest("no sound-shift riddles in this case")
        for r in shifts[:-1]:
            e.answer(r, r.answer)
        self.assertNotIn("grimm_reaper", self.unlocked())
        e.answer(shifts[-1], shifts[-1].answer)
        self.assertIn("grimm_reaper", self.unlocked())

    def test_show_and_tell(self):
        e = self.engine
        places = [loc for loc in e.locations.values() if loc.present]
        for loc in places:
            e.state.unlocked_locations.append(loc.id)
            e.state.inventory.extend(loc.present)
        for loc in places:
            e.travel(loc.id)
            self.assertNotIn("show_and_tell", self.unlocked())
            e.present(next(iter(loc.present)))
        self.assertIn("show_and_tell", self.unlocked())

    def test_hot_streak(self):
        for _ in range(9):
            self.solve_next()
        self.assertNotIn("hot_streak", self.unlocked())
        self.solve_next()
        self.assertIn("hot_streak", self.unlocked())

    def test_polyglot_and_bookworm_add_up_across_cases(self):
        e = self.engine
        by_language = {}
        for r in ALL_RIDDLES.values():
            if r.category != "cipher":
                by_language.setdefault(r.language, r)
        for n, r in enumerate(list(by_language.values())[:10], 1):
            e.new_game()  # a new case every time: only the notebook carries over
            e.learn(r)
            e.emit("answer")
            self.assertEqual("polyglot" in self.unlocked(), n == 10)
        for r in ALL_RIDDLES.values():
            e.learn(r)
            e.emit("answer")
            if len(e.notebook) * 2 < len(ALL_RIDDLES):
                self.assertNotIn("bookworm", self.unlocked())
        self.assertIn("bookworm", self.unlocked())

    def test_case_end_is_reported_once(self):
        events = []
        self.engine.listeners.append(lambda engine, event, info: events.append(event))
        self.win_showdown()
        self.assertEqual(events.count("case_end"), 1)
        self.assertEqual(events[-1], "case_end")


class SettingsTest(unittest.TestCase):
    def test_reduce_motion_default_follows_environment(self):
        cases = [({}, False), ({"RENDER": "true"}, True), ({"NOIR_REDUCE_MOTION": "1"}, True),
                 ({"NOIR_REDUCE_MOTION": "0"}, False), ({"RENDER": ""}, False)]
        for env, expected in cases:
            clean = {k: v for k, v in os.environ.items() if k not in ("RENDER", "NOIR_REDUCE_MOTION")}
            with mock.patch.dict(os.environ, dict(clean, **env), clear=True):
                self.assertEqual(Settings().reduce_motion, expected, env)

    def test_saved_choice_beats_the_default(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"RENDER": "true"}):
            self.assertTrue(Settings.load(Path(d)).reduce_motion)
            Settings(reduce_motion=False).save(Path(d))
            self.assertFalse(Settings.load(Path(d)).reduce_motion)

    def test_unreadable_settings_fall_back(self):
        with tempfile.TemporaryDirectory() as d:
            for junk in ["{", "[1, 2]", '{"reduce_motion": "yes", "volume": 3}']:
                (Path(d) / "settings.json").write_text(junk)
                self.assertIsInstance(Settings.load(Path(d)).reduce_motion, bool)


if __name__ == "__main__":
    unittest.main()
