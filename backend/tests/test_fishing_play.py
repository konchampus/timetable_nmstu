import json
import unittest
from pathlib import Path
from pydantic import ValidationError
from app.games import fishing_play
from app.games.schemas import FishingInput, RoundAction, StartRound

class FishingPlayTests(unittest.TestCase):
    def setUp(self):
        self.vectors = json.loads((Path(__file__).parent / "fishing_play_vectors.json").read_text(encoding="utf-8"))

    def test_replay_shared_vectors_and_all_rod_levels(self):
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                proof = FishingInput(**vector["proof"]).model_dump()
                actual = fishing_play.replay(vector["challenge"], proof)
                self.assertEqual(vector["result"], actual)
                self.assertEqual("caught" if vector["name"].startswith("balanced") else "lost", actual["status"])

    def test_early_late_and_missed_hook_cannot_award_fish(self):
        v = self.vectors[0]
        for hook in (None, 0, 599):
            proof = {**v["proof"], "hook_tick": hook, "events": [], "end_tick": 600}
            self.assertEqual("missed_hook", fishing_play.replay(v["challenge"], proof)["reason"])

    def test_cannot_end_fight_early_or_extend_terminal_journal(self):
        v = self.vectors[0]
        with self.assertRaises(ValueError):
            fishing_play.replay(v["challenge"], {**v["proof"], "end_tick": v["proof"]["hook_tick"] + 1})
        with self.assertRaises(ValueError):
            fishing_play.replay(v["challenge"], {**v["proof"], "end_tick": v["proof"]["end_tick"] + 1})

    def test_strict_bounded_ordered_input(self):
        p = self.vectors[0]["proof"]
        for bad in ({**p, "species": "Карп"}, {**p, "cast_x": True}, {**p, "end_tick": 601},
                    {**p, "events": [{"tick": 93, "held": True}, {"tick": 93, "held": False}]},
                    {**p, "events": [{"tick": 93, "held": 1}]}, {**p, "events": p["events"] * 129}):
            with self.assertRaises(ValidationError):
                FishingInput(**bad)

    def test_protocol_cannot_bypass_fishing_via_collect(self):
        p = self.vectors[0]["proof"]
        StartRound(key="local", game="fishing", bet=0, gameplay_version=1)
        RoundAction(key="finish", action="finish_fishing", version=1, fishing=p)
        for action in ({"action": "collect", "fishing": p}, {"action": "finish_fishing"},
                       {"action": "finish_fishing", "fishing": p, "shot": {"aim_x": 0, "aim_y": 0, "power": 650, "ticks": 120}}):
            with self.assertRaises(ValidationError):
                RoundAction(key="invalid", version=1, **action)

if __name__ == "__main__":
    unittest.main()
