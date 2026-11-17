"""Deterministic rule regressions. Authored but not executed in this session."""
import unittest
from fractions import Fraction
from unittest.mock import patch
from app.games import engine


class EngineRules(unittest.TestCase):
    def test_catalog_has_all_twelve_and_fishing_is_free(self):
        items = engine.catalog()
        self.assertEqual(set(engine.GAME_IDS), {item["id"] for item in items})
        self.assertEqual(12, len(items))
        for item in items:
            self.assertTrue(item["rules"])
            if item.get("gameplay_version") != 1:
                self.assertTrue(item["probabilities"])
            self.assertEqual(1, item["rules_version"])
            self.assertEqual(0 if item["id"] == "fishing" else 10, item["min_bet"])

    def test_fraction_payout_always_floors(self):
        self.assertEqual(22, engine.payout(10, Fraction(9, 4)))
        self.assertEqual(19, engine.payout(10, Fraction(19, 10)))
        self.assertEqual(0, engine.payout(500, 0))

    def test_slot_triples_pairs_and_no_match(self):
        for symbol, multiplier in engine.SLOT_TRIPLES.items():
            with self.subTest(symbol=symbol), patch.object(engine.RNG, "choice", return_value=symbol):
                self.assertEqual(multiplier, engine.instant("slots", None).multiplier)
        for symbols, multiplier in [(["cherry", "lemon", "cherry"], 1), (["cherry", "lemon", "bell"], 0)]:
            with patch.object(engine.RNG, "choice", side_effect=symbols):
                outcome = engine.instant("slots", None)
                self.assertEqual(symbols, outcome.result["symbols"])
                self.assertEqual(multiplier, outcome.multiplier)

    def test_dice_range_and_coin(self):
        for value in range(1, 7):
            for choice in ("low", "high"):
                with self.subTest(value=value, choice=choice), patch.object(engine.RNG, "randrange", return_value=value):
                    expected = Fraction(19, 10) if (value <= 3) == (choice == "low") else 0
                    self.assertEqual(expected, engine.instant("dice", choice).multiplier)
        for side in ("heads", "tails"):
            with patch.object(engine.RNG, "choice", return_value=side):
                self.assertEqual(Fraction(19, 10), engine.instant("coin", side).multiplier)
                self.assertEqual(0, engine.instant("coin", "tails" if side == "heads" else "heads").multiplier)

    def test_sport_result_maps(self):
        for value in range(1, 6):
            for game, boundary, multiplier in [("basketball", 4, Fraction(9, 4)), ("football", 3, Fraction(3, 2))]:
                with patch.object(engine.RNG, "randrange", return_value=value):
                    outcome = engine.instant(game, None)
                    self.assertEqual(value >= boundary, outcome.result["success"])
                    self.assertEqual(multiplier if value >= boundary else 0, outcome.multiplier)
        for zone in engine.DART_ZONES:
            with patch.object(engine.RNG, "choice", return_value=zone):
                self.assertEqual(engine.DART_PAYOUTS[zone], engine.instant("darts", None).multiplier)
        for pins in range(11):
            with patch.object(engine.RNG, "randrange", return_value=pins):
                self.assertEqual(engine.BOWLING_PAYOUTS[pins], engine.instant("bowling", None).multiplier)

    def test_roulette_zero_is_not_even_and_exact_number_wins(self):
        with patch.object(engine.RNG, "randrange", return_value=0):
            for choice in ("even", "odd", "red", "black"):
                self.assertEqual(0, engine.instant("roulette", choice).multiplier)
            self.assertEqual(36, engine.instant("roulette", "number:0").multiplier)
        for number in range(1, 37):
            with patch.object(engine.RNG, "randrange", return_value=number):
                choice = "red" if number in engine.RED else "black"
                self.assertEqual(2, engine.instant("roulette", choice).multiplier)
                self.assertEqual(36, engine.instant("roulette", "number:" + str(number)).multiplier)

    def test_wheel_uses_actual_sector_multiplier(self):
        for multiplier in engine.WHEEL:
            with patch.object(engine.RNG, "choice", return_value=multiplier):
                self.assertEqual(multiplier, engine.instant("wheel", None).multiplier)
        self.assertEqual(10, len(engine.WHEEL))

    def test_blackjack_aces_naturals_and_hidden_card(self):
        self.assertEqual(21, engine.hand_total(["AS", "AH", "9D"]))
        self.assertEqual(12, engine.hand_total(["AS", "AH", "KD"]))
        secret = {"player": ["AS", "KD"], "dealer": ["9S", "8H"], "deck": ["2C"]}
        public = engine.blackjack_public(secret, False)
        self.assertEqual(["9S", "?"], public["dealer"])
        self.assertEqual(9, public["dealer_total"])
        self.assertNotIn("deck", public)
        self.assertEqual(Fraction(5, 2), engine.blackjack_finish(secret).multiplier)
        tie = {"player": ["AS", "KD"], "dealer": ["AH", "QS"], "deck": []}
        self.assertEqual(1, engine.blackjack_finish(tie).multiplier)
        dealt = engine.blackjack_start()
        cards = dealt["deck"] + dealt["player"] + dealt["dealer"]
        self.assertEqual(52, len(set(cards)))

    def test_mines_exact_multiplier_and_adjacent_cells(self):
        self.assertEqual(1, engine.mines_multiplier(3, 0))
        previous = Fraction(1)
        for opened in range(1, 23):
            current = engine.mines_multiplier(3, opened)
            self.assertGreater(current, previous)
            self.assertEqual(1, (current * 10000).denominator)
            previous = current
        self.assertEqual(2, engine.adjacent_mines(0, [1, 5, 24]))
        self.assertEqual(0, engine.adjacent_mines(0, [24]))

    def test_carp_is_a_distinct_catch_and_catalog_preserves_rarity_odds(self):
        species = [fish[0] for fish in engine.FISH]
        self.assertIn("Карп", species)
        self.assertIn("Карась", species)
        self.assertEqual(7, len(set(species)))
        index = species.index("Карп")
        for level, weights in enumerate(engine.FISH_WEIGHTS, 1):
            self.assertEqual(len(engine.FISH), len(weights))
            cursor = sum(weights[:index])
            with patch.object(engine.RNG, "randrange", return_value=cursor), patch.object(engine.RNG, "randint", return_value=8000):
                result = engine.fishing_result(level)
                self.assertEqual("Карп", result["species"])
                self.assertEqual(8000, result["weight_grams"])
        fishing = next(item for item in engine.catalog() if item["id"] == "fishing")
        for level, weights in enumerate(engine.FISH_WEIGHTS, 1):
            for rarity in {fish[1] for fish in engine.FISH}:
                expected = sum(weights[i] for i, fish in enumerate(engine.FISH) if fish[1] == rarity) / 100
                self.assertEqual(expected, fishing["probabilities"][f"rod_{level}_{rarity}"])
            self.assertGreater(fishing["probabilities"][f"rod_{level}_species_Карп"], 0)

    def test_fishing_weights_and_each_rarity(self):
        for level, weights in enumerate(engine.FISH_WEIGHTS, 1):
            self.assertEqual(100, sum(weights))
            cursor = 0
            for index, weight in enumerate(weights):
                if weight == 0:
                    continue
                with patch.object(engine.RNG, "randrange", return_value=cursor), patch.object(engine.RNG, "randint", return_value=engine.FISH[index][3]):
                    result = engine.fishing_result(level)
                    self.assertEqual(engine.FISH[index][0], result["species"])
                    self.assertEqual(engine.FISH[index][2], result["value"])
                cursor += weight


if __name__ == "__main__":
    unittest.main()
