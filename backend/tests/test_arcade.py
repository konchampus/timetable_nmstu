"""Local simulation and request-boundary regressions; no database or network."""
import json
import unittest
from pydantic import ValidationError
from app.games import arcade, engine
from app.games.schemas import RoundAction, StartRound

CHALLENGE = {"gameplay_version": 1, "wind": -85, "target_x": 120, "target_y": -70}
SHOT = {"aim_x": 205, "aim_y": -70, "power": 650, "ticks": 150}

class ArcadeTests(unittest.TestCase):
    def test_input_changes_outcome_and_never_uses_rng(self):
        for game in arcade.SPORTS:
            good = arcade.replay(game, CHALLENGE, SHOT)
            bad = arcade.replay(game, CHALLENGE, {**SHOT, "aim_x": -1000, "aim_y": 1000})
            self.assertGreater(good.multiplier, bad.multiplier)
            self.assertEqual(120, good.result["impact_x"])
            self.assertEqual(-70, good.result["impact_y"])

    def test_power_changes_ballistic_impact(self):
        low = arcade.trajectory(CHALLENGE, {**SHOT, "power": 100})[-1]
        high = arcade.trajectory(CHALLENGE, {**SHOT, "power": 1000})[-1]
        self.assertLess(low["y"], high["y"])
        self.assertEqual(61, len(arcade.trajectory(CHALLENGE, SHOT)))

    def test_bad_or_injected_input_rejected(self):
        base = {"key": "test-shot", "action": "finish", "version": 1, "shot": SHOT}
        RoundAction(**base)
        for shot in ({**SHOT, "power": 1001}, {**SHOT, "aim_x": True}, {**SHOT, "aim_y": 1.5},
                     {**SHOT, "payout": 999999}, {**SHOT, "ticks": 119}, {**SHOT, "ticks": 18001}):
            with self.subTest(shot=shot), self.assertRaises(ValidationError):
                RoundAction(**{**base, "shot": shot})
        for action in ({**base, "shot": None}, {**base, "action": "collect"}, {**base, "cell": 3}):
            with self.assertRaises(ValidationError):
                RoundAction(**action)

    def test_opt_in_preserves_legacy_starts_and_rejects_wrong_game(self):
        for game in arcade.SPORTS:
            self.assertEqual(1, StartRound(key="start", game=game, bet=10, gameplay_version=1).gameplay_version)
            self.assertIsNone(StartRound(key="start", game=game, bet=10).gameplay_version)
        for game in ("slots", "blackjack", "coin"):
            with self.assertRaises(ValidationError):
                StartRound(key="bad", game=game, bet=10, gameplay_version=1)

    def test_catalog_exposes_skill_not_random_probability(self):
        for item in engine.catalog():
            if item["id"] in arcade.SPORTS:
                self.assertEqual(1, item["gameplay_version"])
                self.assertEqual({}, item["probabilities"])

    def test_client_server_reference_vectors(self):
        from pathlib import Path
        vectors = json.loads((Path(__file__).parent / "arcade_vectors.json").read_text(encoding="utf-8"))
        for vector in vectors:
            with self.subTest(game=vector["game"], shot=vector["shot"]):
                result = arcade.replay(vector["game"], vector["challenge"], vector["shot"])
                self.assertEqual(vector["result"], result.result)

if __name__ == "__main__":
    unittest.main()
