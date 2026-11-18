"""Pure rules tests: no configuration, database, network, or environment loading.
Run: backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p test_monopoly_engine.py -v
"""
import importlib.util
import json
import random
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import HTTPException

spec = importlib.util.spec_from_file_location("monopoly_rules_under_test", Path(__file__).resolve().parents[1] / "app/games/monopoly_engine.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.s = e.new_state("a", "Alice")
        self.s["players"] += [e.new_player("b", "Bob"), e.new_player("c", "Carol")]
        self.s["phase"] = "playing"
        self.s["decks"] = {name: list(range(16)) for name in ("chance", "chest")}

    def p(self, pid="a"):
        return e.player(self.s, pid)

    def own(self, *ids, pid="a", houses=0, mortgaged=False):
        for i in ids:
            self.s["properties"][str(i)].update(owner=pid, houses=houses, mortgaged=mortgaged)

    def do(self, action, pid="a", **kwargs):
        self.s = e.act(self.s, pid, action, **kwargs)
        return self.s

    def roll(self, first, second, pid="a"):
        with patch.object(e, "randbelow", side_effect=[first - 1, second - 1]):
            return self.do("roll", pid)

    def reject(self, action, pid="a", status=409, **kwargs):
        original = deepcopy(self.s)
        with self.assertRaises(HTTPException) as caught:
            e.act(self.s, pid, action, **kwargs)
        self.assertEqual(caught.exception.status_code, status)
        self.assertEqual(self.s, original, "Rejected commands must not mutate persisted state")

    def draw(self, deck, card, pid="a"):
        self.s["decks"][deck].remove(card)
        self.s["decks"][deck].insert(0, card)
        e.draw(self.s, self.p(pid), deck)

    def test_roll_sequence_changes_only_after_accepted_roll(self):
        self.assertNotIn("roll_sequence", self.s)
        self.roll(1, 2)
        self.assertEqual(self.s["roll_sequence"], 1)
        before = deepcopy(self.s)
        self.reject("roll")
        self.assertEqual(self.s, before)
        self.assertEqual(e.act(self.s, "a", "buy")["roll_sequence"], 1)

    def test_board_standard_economy(self):
        self.assertEqual(len(e.BOARD), 40)
        self.assertEqual([t["id"] for t in e.BOARD], list(range(40)))
        self.assertEqual(sum(t["kind"] == "street" for t in e.BOARD), 22)
        self.assertEqual(sum(t["kind"] == "rail" for t in e.BOARD), 4)
        self.assertEqual(sum(t["kind"] == "utility" for t in e.BOARD), 2)
        self.assertEqual(e.BOARD[39]["rents"], [50, 200, 600, 1400, 1700, 2000])
        self.assertEqual(len(self.s["properties"]), 28)

    def test_initial_state_and_json_roundtrip(self):
        self.assertEqual(self.p()["cash"], 1500)
        self.assertEqual(self.p()["pos"], 0)
        self.assertFalse(self.p()["jailed"])
        self.assertEqual(json.loads(json.dumps(self.s)), self.s)
        for deck in e.new_state("x", "X")["decks"].values():
            self.assertEqual(sorted(deck), list(range(16)))

    def test_lobby_only_ready_toggle(self):
        self.s["phase"] = "lobby"
        self.do("ready")
        self.assertTrue(self.p()["ready"])
        self.do("ready")
        self.assertFalse(self.p()["ready"])
        self.reject("roll")

    def test_unknown_out_and_finished_players_rejected(self):
        self.reject("roll", pid="absent")
        self.p("b")["out"] = True
        self.reject("roll", pid="b")
        self.s["phase"] = "finished"
        self.reject("roll")

    def test_turn_and_unknown_action(self):
        self.reject("roll", pid="b")
        self.reject("end")
        self.reject("unsupported", status=422)

    def test_success_is_copy_on_write(self):
        before = deepcopy(self.s)
        self.roll(1, 2)
        self.assertEqual(before["players"][0]["pos"], 0)
        self.assertEqual(self.p()["pos"], 3)
        self.assertIsNone(before["pending"])

    def test_start_salary_once(self):
        self.p()["pos"] = 39
        self.roll(2, 4)
        self.assertEqual(self.p()["cash"], 1700)
        self.assertEqual(self.p()["pos"], 5)

    def test_landing_start_salary(self):
        self.p()["pos"] = 37
        self.roll(1, 2)
        self.assertEqual(self.p()["pos"], 0)
        self.assertEqual(self.p()["cash"], 1700)

    def test_buy_pending_and_end(self):
        self.roll(1, 2)
        self.assertEqual(self.s["pending"], 3)
        self.reject("end")
        self.do("buy")
        self.assertEqual(e.prop(self.s, 3)["owner"], "a")
        self.assertEqual(self.p()["cash"], 1440)
        self.do("end")
        self.assertEqual(self.s["turn"], "b")
        self.assertFalse(self.s["rolled"])

    def test_purchase_requires_money_and_offer(self):
        self.reject("buy")
        self.s["pending"] = 39
        self.p()["cash"] = 399
        self.reject("buy")
        self.do("auction")
        self.assertEqual(self.s["auction"]["tile"], 39)

    def test_cannot_roll_twice(self):
        self.roll(1, 2)
        self.do("buy")
        self.reject("roll")

    def test_double_extra_turn_then_triple_jail(self):
        self.p()["pos"] = 8
        self.roll(1, 1)  # visiting jail
        self.assertTrue(self.s["extra"])
        self.do("end")
        self.assertEqual(self.s["turn"], "a")
        self.assertFalse(self.s["rolled"])
        self.roll(5, 5)  # free parking
        self.do("end")
        self.roll(2, 2)
        self.assertEqual(self.p()["pos"], 10)
        self.assertTrue(self.p()["jailed"])
        self.assertFalse(self.s["extra"])
        self.assertEqual(self.s["doubles"], 0)
        self.do("end")
        self.assertEqual(self.s["turn"], "b")

    def test_go_to_jail_has_no_salary_or_extra(self):
        self.p()["pos"] = 26
        self.roll(2, 2)
        self.assertEqual(self.p()["cash"], 1500)
        self.assertTrue(self.p()["jailed"])
        self.assertFalse(self.s["extra"])

    def test_jail_failed_roll_stays(self):
        e.jail(self.s, self.p())
        self.roll(1, 2)
        self.assertTrue(self.p()["jailed"])
        self.assertEqual(self.p()["jail"], 1)
        self.assertEqual(self.p()["pos"], 10)
        self.do("end")
        self.assertEqual(self.s["turn"], "b")

    def test_jail_double_releases_without_extra(self):
        e.jail(self.s, self.p())
        self.roll(5, 5)
        self.assertFalse(self.p()["jailed"])
        self.assertEqual(self.p()["pos"], 20)
        self.assertFalse(self.s["extra"])
        self.do("end")
        self.assertEqual(self.s["turn"], "b")

    def test_jail_third_failure_pays_and_moves(self):
        e.jail(self.s, self.p())
        self.p()["jail"] = 2
        self.roll(1, 2)
        self.assertFalse(self.p()["jailed"])
        self.assertEqual(self.p()["cash"], 1450)
        self.assertEqual(self.p()["pos"], 13)
        self.assertEqual(self.s["pending"], 13)

    def test_jail_debt_resumes_move_immediately_after_mortgage(self):
        e.jail(self.s, self.p())
        self.p().update(jail=2, cash=0)
        self.own(39)
        self.roll(1, 2)
        self.assertEqual(self.p()["pos"], 10)
        self.assertEqual(self.s["debt"]["amount"], 50)
        self.do("mortgage", tile=39)
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.p()["pos"], 13)
        self.assertEqual(self.s["pending"], 13)
        self.assertNotIn("jail_move", self.s)
        self.assertEqual(self.p()["cash"], 150)

    def test_deferred_jail_move_can_create_another_debt(self):
        e.jail(self.s, self.p())
        self.p().update(jail=2, cash=0)
        self.own(1)
        self.own(13, pid="b", houses=5)
        self.roll(1, 2)
        self.do("mortgage", tile=1)  # 30 only, still owes 20
        self.assertEqual(self.s["debt"]["amount"], 20)
        self.own(3)
        self.do("mortgage", tile=3)
        self.assertEqual(self.p()["pos"], 13)
        self.assertEqual(self.s["debt"], dict(player="a", amount=740, creditor="b"))
        self.assertNotIn("jail_move", self.s)

    def test_bail_before_roll(self):
        e.jail(self.s, self.p())
        self.do("bail")
        self.assertFalse(self.p()["jailed"])
        self.assertEqual(self.p()["cash"], 1450)
        self.assertFalse(self.s["rolled"])

    def test_bail_requires_cash_and_jail(self):
        self.reject("bail")
        e.jail(self.s, self.p())
        self.p()["cash"] = 49
        self.reject("bail")
        self.reject("jail_card")

    def test_jail_card_removed_from_deck_and_returned(self):
        self.draw("chance", 0)
        self.assertEqual(self.p()["cards"], ["chance"])
        self.assertNotIn(0, self.s["decks"]["chance"])
        e.jail(self.s, self.p())
        self.do("jail_card")
        self.assertFalse(self.p()["jailed"])
        self.assertEqual(self.p()["cards"], [])
        self.assertEqual(self.s["decks"]["chance"].count(0), 1)

    def test_income_and_luxury_tax(self):
        for tile, cost in [(4, 200), (38, 100)]:
            with self.subTest(tile=tile):
                self.p().update(pos=tile, cash=1500)
                e.land(self.s, self.p())
                self.assertEqual(self.p()["cash"], 1500-cost)

    def test_unowned_rent_is_zero(self):
        self.assertEqual(e.rent(self.s, 1, 7), 0)
        self.assertEqual(e.rent(self.s, 5, 7), 0)

    def test_street_rent_and_monopoly(self):
        self.own(1, pid="b")
        self.assertEqual(e.rent(self.s, 1, 7), 2)
        self.own(3, pid="b")
        self.assertEqual(e.rent(self.s, 1, 7), 4)
        e.prop(self.s, 3)["mortgaged"] = True
        self.assertEqual(e.rent(self.s, 1, 7), 4)
        self.assertEqual(e.rent(self.s, 3, 7), 0)
        for level, amount in enumerate([4, 10, 30, 90, 160, 250]):
            e.prop(self.s, 1)["houses"] = level
            self.assertEqual(e.rent(self.s, 1, 7), amount)

    def test_rent_transfers_only_real_money_and_creates_debt(self):
        self.own(39, pid="b", houses=5)
        self.p().update(pos=39, cash=100)
        e.land(self.s, self.p())
        self.assertEqual(self.p()["cash"], 0)
        self.assertEqual(self.p("b")["cash"], 1600)
        self.assertEqual(self.s["debt"], dict(player="a", amount=1900, creditor="b"))
        self.reject("end")
        self.reject("roll")
        self.reject("trade", target="c", cash=1)

    def test_self_owned_property_no_rent(self):
        self.own(1)
        self.p()["pos"] = 1
        e.land(self.s, self.p())
        self.assertEqual(self.p()["cash"], 1500)
        self.assertIsNone(self.s["pending"])

    def test_railroad_counts_and_special_multiplier(self):
        for index, tile in enumerate([5, 15, 25, 35]):
            self.own(tile, pid="b")
            self.assertEqual(e.rent(self.s, 5, 7), 25*2**index)
            self.assertEqual(e.rent(self.s, 5, 7, "rail"), 50*2**index)

    def test_utility_rent(self):
        self.own(12, pid="b")
        self.assertEqual(e.rent(self.s, 12, 7), 28)
        self.assertEqual(e.rent(self.s, 12, 7, "utility"), 70)
        self.own(28, pid="b")
        self.assertEqual(e.rent(self.s, 12, 7), 70)

    def test_auction_everybody_passes(self):
        self.s["pending"] = 1
        self.do("auction")
        for pid in ["a", "b", "c"]:
            self.do("pass", pid=pid)
        self.assertIsNone(self.s["auction"])
        self.assertIsNone(e.prop(self.s, 1)["owner"])

    def test_auction_bidder_skipped_and_winner_pays(self):
        e.auction(self.s, 1)
        self.do("bid", amount=10)
        self.assertEqual(self.s["auction"]["actor"], "b")
        self.do("bid", pid="b", amount=11)
        self.do("pass", pid="c")
        self.assertEqual(self.s["auction"]["actor"], "a")
        self.do("pass")
        self.assertIsNone(self.s["auction"])
        self.assertEqual(e.prop(self.s, 1)["owner"], "b")
        self.assertEqual(self.p("b")["cash"], 1489)
        self.assertEqual(self.p()["cash"], 1500)

    def test_auction_validation(self):
        e.auction(self.s, 1)
        self.reject("bid", pid="b", amount=10)
        self.reject("roll")
        for amount in [0, -1, 1501, True, 1.5]:
            self.reject("bid", amount=amount)
        self.do("bid", amount=1500)
        self.reject("bid", pid="b", amount=1500)

    def test_auction_excludes_out_players(self):
        self.p("b")["out"] = True
        e.auction(self.s, 1)
        self.do("bid", amount=1)
        self.assertEqual(self.s["auction"]["actor"], "c")
        self.do("pass", pid="c")
        self.assertEqual(e.prop(self.s, 1)["owner"], "a")

    def test_build_requires_full_unmortgaged_street_group(self):
        self.own(1)
        self.reject("build", tile=1)
        self.own(3, mortgaged=True)
        self.reject("build", tile=1)
        self.own(5, 15, 25, 35)
        self.reject("build", tile=5)
        self.reject("build", tile=True)
        self.reject("build", tile=0)
        self.reject("build", tile=40)

    def test_even_development_and_sale(self):
        self.own(1, 3)
        self.do("build", tile=1)
        self.assertEqual(self.p()["cash"], 1450)
        self.reject("build", tile=1)
        self.do("build", tile=3)
        self.do("build", tile=1)
        self.reject("sell", tile=3)
        self.do("sell", tile=1)
        self.assertEqual(e.prop(self.s, 1)["houses"], 1)
        self.assertEqual(self.p()["cash"], 1375)

    def test_build_cannot_exceed_hotel(self):
        self.own(1, 3, houses=5)
        self.reject("build", tile=1)

    def test_build_requires_cash(self):
        self.own(1, 3)
        self.p()["cash"] = 49
        self.reject("build", tile=1)

    def test_32_house_inventory_and_hotel_releases_four(self):
        self.own(1, 3, 6, 8, 9, 11, 13, 14, houses=4)
        self.own(37, 39)
        self.reject("build", tile=37)
        self.do("build", tile=1)
        self.assertEqual(e.prop(self.s, 1)["houses"], 5)
        self.do("build", tile=37)
        self.assertEqual(e.prop(self.s, 37)["houses"], 1)

    def test_12_hotel_inventory(self):
        streets = [t["id"] for t in e.BOARD if t["kind"] == "street" and t["id"] not in [1, 3]]
        self.own(*streets[:12], houses=5)
        self.own(1, 3, houses=4)
        self.reject("build", tile=1)

    def test_hotel_sale_needs_four_bank_houses(self):
        self.own(1, 3, houses=5)
        self.own(6, 8, 9, 11, 13, 14, 16, 18, houses=4)
        self.reject("sell", tile=1)
        self.do("sell", tile=6)
        self.do("sell", tile=8)
        self.do("sell", tile=9)
        self.do("sell", tile=11)
        self.do("sell", tile=1)
        self.assertEqual(e.prop(self.s, 1)["houses"], 4)

    def test_mortgage_and_redemption_interest(self):
        self.own(1)
        self.do("mortgage", tile=1)
        self.assertEqual(self.p()["cash"], 1530)
        self.assertTrue(e.prop(self.s, 1)["mortgaged"])
        self.reject("mortgage", tile=1)
        self.do("redeem", tile=1)
        self.assertEqual(self.p()["cash"], 1497)
        self.assertFalse(e.prop(self.s, 1)["mortgaged"])
        self.reject("redeem", tile=1)

    def test_cannot_mortgage_group_with_buildings(self):
        self.own(1, 3)
        e.prop(self.s, 3)["houses"] = 1
        self.reject("mortgage", tile=1)
        self.reject("mortgage", pid="b", tile=1)

    def test_sale_pays_debt_to_creditor(self):
        self.own(1, 3, houses=1)
        self.p()["cash"] = 0
        e.charge(self.s, self.p(), 20, "b")
        self.do("sell", tile=1)
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.p()["cash"], 5)
        self.assertEqual(self.p("b")["cash"], 1520)

    def test_debtor_only_can_raise_cash(self):
        self.own(39, pid="b")
        self.p("b")["cash"] = 0
        e.charge(self.s, self.p("b"), 100, "a")
        self.reject("end")
        self.reject("build", pid="b", tile=39)
        self.do("mortgage", pid="b", tile=39)
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.p("b")["cash"], 100)
        self.assertEqual(self.p()["cash"], 1600)
        self.assertEqual(self.s["turn"], "a")

    def test_negative_charge_rejected(self):
        with self.assertRaises(HTTPException):
            e.charge(self.s, self.p(), -10)
        self.assertEqual(self.p()["cash"], 1500)

    def test_chance_payout_does_not_mint_money(self):
        self.p()["cash"] = 20
        before = sum(p["cash"] for p in self.s["players"])
        self.draw("chance", 11)
        self.assertEqual(sum(p["cash"] for p in self.s["players"]), before)
        self.assertEqual(self.p("b")["cash"], 1520)
        self.assertEqual(self.p("c")["cash"], 1500)
        self.assertEqual(self.s["debt"], dict(player="a", amount=30, creditor="b"))
        self.own(39)
        self.do("mortgage", tile=39)
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.p("b")["cash"], 1550)
        self.assertEqual(self.p("c")["cash"], 1550)
        self.assertEqual(self.p()["cash"], 120)

    def test_chance_bankruptcy_cancels_unfunded_remaining_payouts(self):
        self.p()["cash"] = 0
        self.draw("chance", 11)
        self.do("bankrupt")
        self.assertEqual(self.p("b")["cash"], 1500)
        self.assertEqual(self.p("c")["cash"], 1500)
        self.assertFalse(self.s.get("payments"))
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.s["turn"], "b")

    def test_birthday_collects_sequential_debts(self):
        self.p("b")["cash"] = 3
        self.p("c")["cash"] = 5
        self.own(1, pid="b")
        self.own(3, pid="c")
        self.draw("chest", 4)
        self.assertEqual(self.p()["cash"], 1503)
        self.assertEqual(self.s["debt"], dict(player="b", amount=7, creditor="a"))
        self.do("mortgage", pid="b", tile=1)
        self.assertEqual(self.p()["cash"], 1515)
        self.assertEqual(self.s["debt"], dict(player="c", amount=5, creditor="a"))
        self.do("mortgage", pid="c", tile=3)
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.p()["cash"], 1520)

    def test_birthday_continues_after_nonturn_bankruptcy(self):
        self.p("b")["cash"] = 0
        self.draw("chest", 4)
        self.do("bankrupt", pid="b")
        self.assertEqual(self.s["turn"], "a")
        self.assertEqual(self.p()["cash"], 1510)
        self.assertIsNone(self.s["debt"])

    def test_card_salary_and_backwards_no_salary(self):
        self.p()["pos"] = 36
        self.draw("chance", 1)
        self.assertEqual(self.p()["cash"], 1700)
        self.p()["pos"] = 7
        self.draw("chance", 6)  # back to income tax
        self.assertEqual(self.p()["cash"], 1500)
        self.assertEqual(self.p()["pos"], 4)

    def test_back_three_chains_into_chest(self):
        self.p()["pos"] = 36
        self.s["decks"]["chest"] = [5] + [x for x in range(16) if x != 5]
        self.draw("chance", 6)
        self.assertEqual(self.p()["pos"], 33)
        self.assertEqual(self.p()["cash"], 1700)

    def test_both_nearest_rail_cards_charge_double_and_start_salary(self):
        for card in [7, 15]:
            with self.subTest(card=card):
                self.p().update(pos=36, cash=1500)
                self.p("b")["cash"] = 1500
                self.own(5, pid="b")
                self.draw("chance", card)
                self.assertEqual(self.p()["pos"], 5)
                self.assertEqual(self.p()["cash"], 1650)
                self.assertEqual(self.p("b")["cash"], 1550)

    def test_nearest_utility_uses_fresh_dice(self):
        self.p()["pos"] = 7
        self.own(12, pid="b")
        with patch.object(e, "randbelow", side_effect=[2, 3]):
            self.draw("chance", 8)
        self.assertEqual(self.p()["cash"], 1430)
        self.assertNotIn("rent_dice", self.s)

    def test_unowned_utility_does_not_leak_card_dice(self):
        self.p()["pos"] = 7
        with patch.object(e, "randbelow", side_effect=[5, 5]):
            self.draw("chance", 8)
        self.assertNotIn("rent_dice", self.s)
        self.do("buy")
        self.own(28, pid="b")
        self.p()["pos"] = 28
        self.s["dice"] = [1, 2]
        e.land(self.s, self.p())
        self.assertEqual(self.p("b")["cash"], 1512)

    def test_repairs_count_hotels_as_one_hotel(self):
        self.own(1, houses=3)
        self.own(3, houses=5)
        self.draw("chance", 9)
        self.assertEqual(self.p()["cash"], 1325)
        self.draw("chest", 3)
        self.assertEqual(self.p()["cash"], 1090)

    def test_all_nonmovement_money_cards(self):
        for deck, mapping in [("chance", {12:50, 13:150, 14:-15}),
                              ("chest", {5:200,6:-50,7:50,8:100,9:20,10:100,11:-100,12:-50,13:25,14:10,15:100})]:
            for card, delta in mapping.items():
                with self.subTest(deck=deck, card=card):
                    self.p()["cash"] = 1500
                    self.draw(deck, card)
                    self.assertEqual(self.p()["cash"], 1500+delta)
                    self.assertIn(card, self.s["decks"][deck])

    def test_bankruptcy_to_creditor_transfers_assets_cash_and_cards(self):
        self.own(1, houses=2)
        self.own(3, mortgaged=True)
        self.draw("chance", 0)
        self.p()["cash"] = 0
        e.charge(self.s, self.p(), 100, "b")
        self.do("bankrupt")
        self.assertTrue(self.p()["out"])
        self.assertEqual(e.prop(self.s, 1), dict(owner="b", houses=0, mortgaged=False))
        self.assertEqual(e.prop(self.s, 3), dict(owner="b", houses=0, mortgaged=True))
        self.assertEqual(self.p("b")["cash"], 1547)  # 50 building liquidation minus 3 interest
        self.assertEqual(self.p("b")["cards"], ["chance"])
        self.assertNotIn(0, self.s["decks"]["chance"])
        self.assertEqual(self.p()["cards"], [])
        self.assertEqual(self.s["turn"], "b")

    def test_bankruptcy_inherited_interest_can_create_new_debt(self):
        self.own(39, mortgaged=True)
        self.p()["cash"] = self.p("b")["cash"] = 0
        e.charge(self.s, self.p(), 100, "b")
        self.do("bankrupt")
        self.assertEqual(self.s["debt"], dict(player="b", amount=20, creditor=None))
        self.assertEqual(e.prop(self.s, 39)["owner"], "b")
        self.do("bankrupt", pid="b")
        self.assertEqual(self.s["phase"], "finished")
        self.assertEqual(self.s["winner"], "c")

    def test_bank_bankruptcy_queues_all_properties(self):
        self.own(1, 3, houses=1)
        self.draw("chest", 0)
        self.p()["cash"] = 0
        e.charge(self.s, self.p(), 200)
        self.do("bankrupt")
        self.assertEqual(self.s["auction"]["tile"], 1)
        self.assertEqual(self.s["bank_queue"], [3])
        self.assertEqual(e.prop(self.s, 1), dict(owner=None, houses=0, mortgaged=False))
        self.assertIn(0, self.s["decks"]["chest"])
        self.do("pass", pid="b")
        self.do("pass", pid="c")
        self.assertEqual(self.s["auction"]["tile"], 3)
        self.do("bid", pid="b", amount=1)
        self.do("pass", pid="c")
        self.assertIsNone(self.s["auction"])
        self.assertFalse(self.s["bank_queue"])

    def test_waiting_bank_queue_resumes_after_debt_is_paid(self):
        self.own(39, pid="b")
        self.p("b")["cash"] = 0
        self.s["bank_queue"] = [1, 3]
        e.charge(self.s, self.p("b"), 100)
        self.do("mortgage", pid="b", tile=39)
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.s["auction"]["tile"], 1)
        self.assertEqual(self.s["bank_queue"], [3])

    def test_bankruptcy_discards_dead_players_deferred_jail_move(self):
        e.jail(self.s, self.p())
        self.p().update(cash=0, jail=2)
        self.roll(1, 2)
        self.do("bankrupt")
        self.assertNotIn("jail_move", self.s)
        self.assertEqual(self.p("b")["pos"], 0)
        self.assertEqual(self.s["turn"], "b")

    def test_resign_and_win_cleans_pending_work(self):
        self.p("c")["out"] = True
        self.s["pending"] = 1
        self.do("resign")
        self.assertEqual(self.s["phase"], "finished")
        self.assertEqual(self.s["winner"], "b")
        for key in ["debt", "pending", "auction", "trade"]:
            self.assertIsNone(self.s[key])
        self.assertEqual(self.s["bank_queue"], [])

    def test_resign_and_bankrupt_permissions(self):
        self.reject("bankrupt")
        self.do("resign",pid="b")
        self.assertTrue(self.p("b")["out"])
        self.p()["cash"] = 0
        e.charge(self.s, self.p(), 100)
        self.do("resign")
        self.assertTrue(self.p()["out"])

    def test_trade_cash_and_property_atomic_exchange(self):
        self.own(1)
        self.own(5, pid="b")
        self.do("trade", target="b", give=[1, 1], take=[5], cash=100, ask=50)
        self.assertEqual(self.s["trade"]["give"], [1])
        self.reject("accept_trade", pid="c")
        self.assertEqual(self.s["turn"], "a")
        self.do("accept_trade", pid="b")
        self.assertEqual(self.p()["cash"], 1450)
        self.assertEqual(self.p("b")["cash"], 1550)
        self.assertEqual(e.prop(self.s, 1)["owner"], "b")
        self.assertEqual(e.prop(self.s, 5)["owner"], "a")
        self.assertIsNone(self.s["trade"])

    def test_trade_mortgaged_property_charges_receiving_interest(self):
        self.own(39, mortgaged=True)
        self.do("trade",target="b",give=[39])
        self.do("accept_trade",pid="b")
        self.assertEqual(self.p("b")["cash"],1480)
        self.assertEqual(e.prop(self.s,39)["owner"],"b")
        self.assertTrue(e.prop(self.s,39)["mortgaged"])

    def test_trade_revalidates_cash_and_assets(self):
        self.own(1)
        self.do("trade", target="b", give=[1], ask=50)
        self.p("b")["cash"] = 49
        self.reject("accept_trade", pid="b")
        self.p("b")["cash"] = 1500
        e.prop(self.s, 1)["owner"] = "c"
        self.reject("accept_trade", pid="b")

    def test_trade_buildings_in_entire_group_block_transfer(self):
        self.own(1, 3)
        e.prop(self.s, 3)["houses"] = 1
        self.reject("trade", target="b", give=[1])

    def test_trade_validation(self):
        for values in [dict(cash=-1), dict(cash=1501), dict(cash=1.1), dict(cash=True), dict(ask=1.1), dict(ask=-1), dict(give=[True]), dict(give=[40]), dict(give=[5])]:
            with self.subTest(values=values):
                self.reject("trade", target="b", **values)
        self.reject("trade", target="a", cash=1)
        self.reject("trade", target="missing", cash=1)
        self.reject("trade", target="b")

    def test_trade_reject_cancel_and_management_clear_offer(self):
        self.do("trade", target="b", cash=1)
        self.do("reject_trade", pid="b")
        self.assertIsNone(self.s["trade"])
        self.do("trade", target="b", cash=1)
        self.do("cancel_trade")
        self.assertIsNone(self.s["trade"])
        self.own(1)
        self.do("trade", target="b", cash=1)
        self.do("mortgage", tile=1)
        self.assertIsNone(self.s["trade"])

    def test_malformed_trade_lists_raise_http_errors_not_type_errors(self):
        self.own(1)
        for value in [1, [[1]], {1: "x"}, [1, True], "1"]:
            with self.subTest(value=value):
                self.reject("trade", target="b", give=value)

    def test_card_direct_destinations_and_jail(self):
        for deck, cards in [("chance", {2:24, 3:11, 4:39, 10:5}), ("chest", {1:0})]:
            for card, destination in cards.items():
                with self.subTest(deck=deck, card=card):
                    self.p().update(pos=36, cash=1500)
                    self.s["pending"] = None
                    self.draw(deck, card)
                    self.assertEqual(self.p()["pos"], destination)
                    self.assertEqual(self.p()["cash"], 1700 if destination < 36 else 1500)
                    self.assertEqual(self.s["pending"], destination if e.BOARD[destination]["price"] else None)
        for deck, card in [("chance", 5), ("chest", 2)]:
            self.p().update(pos=36, cash=1500)
            self.draw(deck, card)
            self.assertTrue(self.p()["jailed"])
            self.assertEqual(self.p()["pos"], 10)
            self.assertEqual(self.p()["cash"], 1500)

    def test_timeout_foreign_debtor_bankruptcy_then_inheritor_bankruptcy(self):
        # Same public helper calls as HTTP timeout, with a non-turn debtor.
        self.s["players"].append(e.new_player("d", "Dan"))
        self.p()["cash"] = self.p("b")["cash"] = 0
        self.own(1, pid="b", mortgaged=True)
        self.draw("chest", 4)
        self.assertEqual(self.s["debt"]["player"], "b")
        e.bankrupt(self.s, self.p("b"))
        self.assertEqual(self.s["turn"], "a")
        self.assertEqual(self.s["debt"], dict(player="a", amount=3, creditor=None))
        self.assertEqual(self.p("c")["cash"], 1500)
        e.bankrupt(self.s, self.p())
        self.assertEqual(self.s["turn"], "c")
        self.assertFalse(self.s.get("collections"))
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.s["auction"]["tile"], 1)
        self.do("bid", pid="c", amount=10)
        # Timeout of last challenger: auto-pass, then award the property.
        self.s["auction"]["passed"].append(self.s["auction"]["actor"])
        e.advance_auction(self.s)
        self.assertIsNone(self.s["auction"])
        self.assertEqual(e.prop(self.s, 1)["owner"], "c")
        self.assertEqual(self.p("c")["cash"], 1490)
        self.assertEqual(self.p("d")["cash"], 1500)

    def test_foreign_debt_interest_paid_then_birthday_continues(self):
        self.p()["cash"] = self.p("b")["cash"] = 0
        self.own(1, pid="b", mortgaged=True)
        self.own(39)
        self.draw("chest", 4)
        e.bankrupt(self.s, self.p("b"))
        self.assertEqual(self.s["debt"]["player"], "a")
        self.do("mortgage", tile=39)
        self.assertIsNone(self.s["debt"])
        self.assertEqual(self.p()["cash"], 207)  # +200 mortgage -3 interest +10 birthday
        self.assertEqual(self.p("c")["cash"], 1490)
        self.assertFalse(self.s.get("collections"))

    def test_foreign_bank_debt_bankruptcy_auctions_preserve_current_turn(self):
        self.own(1, 3, pid="b")
        self.p("b")["cash"] = 0
        e.charge(self.s, self.p("b"), 100)
        e.bankrupt(self.s, self.p("b"))
        self.assertEqual(self.s["turn"], "a")
        self.assertEqual(self.s["auction"]["actor"], "a")
        for _ in range(2):
            self.s["auction"]["passed"].append(self.s["auction"]["actor"])
            e.advance_auction(self.s)
            self.s["auction"]["passed"].append(self.s["auction"]["actor"])
            e.advance_auction(self.s)
        self.assertIsNone(self.s["auction"])
        self.assertEqual(self.s["bank_queue"], [])
        self.assertFalse(self.s["rolled"])
        self.assertEqual(self.s["turn"], "a")

    def test_seeded_complete_games_preserve_invariants_and_never_stall(self):
        # 12 reproducible games. Check every accepted state, not just final outcome.
        for seed in range(12):
            rng = random.Random(seed)
            s = e.new_state("a", "Alice")
            s["players"] += [e.new_player("b", "Bob"), e.new_player("c", "Carol")]
            s["phase"] = "playing"
            for deck in s["decks"].values():
                deck.sort()
                rng.shuffle(deck)
            with patch.object(e, "randbelow", side_effect=rng.randrange):
                for step in range(3000):
                    if s["phase"] == "finished":
                        break
                    if s["debt"]:
                        pid = s["debt"]["player"]
                        owned = [int(i) for i, a in s["properties"].items() if a["owner"] == pid and not a["mortgaged"]
                                 and not any(e.prop(s, n)["houses"] for n in e.group_ids(int(i)))]
                        houses_used = sum(a["houses"] for a in s["properties"].values() if a["houses"] < 5)
                        sellable = [int(i) for i, a in s["properties"].items() if a["owner"] == pid and a["houses"] > 0
                                    and a["houses"] == max(e.prop(s, n)["houses"] for n in e.group_ids(int(i)))
                                    and (a["houses"] < 5 or houses_used <= 28)]
                        if sellable:
                            s = e.act(s, pid, "sell", tile=sellable[0])
                        elif owned:
                            s = e.act(s, pid, "mortgage", tile=owned[0])
                        else:
                            s = e.act(s, pid, "bankrupt")
                    elif s["auction"]:
                        a = s["auction"]
                        pid = a["actor"]
                        funds = e.player(s, pid)["cash"]
                        if a["bid"] < min(funds, e.BOARD[a["tile"]]["price"] // 2) and rng.randrange(3):
                            s = e.act(s, pid, "bid", amount=min(funds, e.BOARD[a["tile"]]["price"] // 2, a["bid"] + 25))
                        else:
                            s = e.act(s, pid, "pass")
                    elif s["pending"] is not None:
                        pid = s["turn"]
                        if e.player(s, pid)["cash"] >= e.BOARD[s["pending"]]["price"]:
                            s = e.act(s, pid, "buy")
                        else:
                            s = e.act(s, pid, "auction")
                    else:
                        pid = s["turn"]
                        candidates = [int(i) for i, a in s["properties"].items()
                                      if a["owner"] == pid and e.BOARD[int(i)]["kind"] == "street"
                                      and a["houses"] < 5 and e.complete(s, pid, int(i))
                                      and not any(e.prop(s, n)["mortgaged"] for n in e.group_ids(int(i)))
                                      and a["houses"] == min(e.prop(s, n)["houses"] for n in e.group_ids(int(i)))
                                      and e.player(s, pid)["cash"] >= e.BOARD[int(i)]["build"] + 100]
                        if step > 2500:
                            s = e.act(s, pid, "resign")
                        elif candidates:
                            s = e.act(s, pid, "build", tile=candidates[0])
                        else:
                            s = e.act(s, pid, "end" if s["rolled"] else "roll")
                    self.assertEqual(json.loads(json.dumps(s)), s)
                    for p in s["players"]:
                        self.assertIs(type(p["cash"]), int)
                        self.assertGreaterEqual(p["cash"], 0)
                        self.assertIn(p["pos"], range(40))
                    alive = {p["id"] for p in s["players"] if not p["out"]}
                    for a in s["properties"].values():
                        self.assertTrue(a["owner"] is None or a["owner"] in alive)
                        self.assertIn(a["houses"], range(6))
                    if s["phase"] == "playing":
                        self.assertIn(s["turn"], alive)
                    if s["debt"]:
                        self.assertIn(s["debt"]["player"], alive)
                        self.assertGreater(s["debt"]["amount"], 0)
                        self.assertTrue(s["debt"]["creditor"] is None or s["debt"]["creditor"] in alive)
                    if s["auction"]:
                        self.assertIsNone(s["debt"])
                        self.assertIsNone(s["pending"])
                        self.assertIn(s["auction"]["actor"], alive)
                    for deck in ["chance", "chest"]:
                        self.assertEqual(s["decks"][deck].count(0) + sum(p["cards"].count(deck) for p in s["players"]), 1)
                self.assertEqual(s["phase"], "finished", (seed, step))
                self.assertEqual(len([p for p in s["players"] if not p["out"]]), 1)
                self.assertEqual(s["winner"], next(p["id"] for p in s["players"] if not p["out"]))

    def test_log_bounded(self):
        for i in range(150):
            e.log(self.s, str(i))
        self.assertEqual(len(self.s["log"]), 100)
        self.assertEqual(self.s["log"][0], "50")


if __name__ == "__main__":
    unittest.main()
