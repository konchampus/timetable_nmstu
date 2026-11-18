"""Offline, deterministic contracts tests: no DB, app settings or environment."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import HTTPException

spec = importlib.util.spec_from_file_location(
    'contracts_under_test', Path(__file__).resolve().parents[1] / 'app/games/monopoly_contracts.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
PROPERTY_IDS = [1, 3, 5, 6, 8, 9, 11, 12, 13, 14, 15, 16, 18, 19,
                21, 23, 24, 25, 26, 27, 28, 29, 31, 32, 34, 35, 37, 39]


class ContractsTest(unittest.TestCase):
    def setUp(self):
        self.s = dict(mode='friendly', phase='playing', turn='c', turn_number=10,
                      players=[dict(id=pid, name=name, cash=1500, out=False)
                               for pid, name in [('a', 'Alice'), ('b', 'Bob'), ('c', 'Carol')]],
                      properties={str(i): dict(owner='a', houses=0, mortgaged=False) for i in PROPERTY_IDS},
                      auction=None, debt=None, pending=None, trade=None, log=[])
        self.uuid = patch.object(c, 'uuid4', side_effect=[f'id-{i}' for i in range(200)])
        self.uuid.start()
        self.addCleanup(self.uuid.stop)

    def propose(self, **kw):
        args = dict(pid='a', target='b', tiles=[1, 3], turns=3, fee=100)
        args.update(kw)
        return c.propose(self.s, **args)

    def accept(self, **kw):
        self.propose(**kw)
        return c.respond(self.s, 'b', True)

    def reject_call(self, fn, *args, **kw):
        before = deepcopy(self.s)
        with self.assertRaises(HTTPException) as caught:
            fn(self.s, *args, **kw)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.s, before, 'Failure must not mutate even cleanup/log state')

    def balances(self):
        return [p['cash'] for p in self.s['players']]

    def test_proposal_has_no_money_effect_and_detaches_arguments_and_result(self):
        tiles = [1, 39]
        offer = self.propose(tiles=tiles)
        self.assertEqual(offer, dict(id='id-0', offerer='a', target='b', tiles=[1, 39], turns=3, fee=100))
        self.assertEqual(self.balances(), [1500] * 3)
        tiles.clear()
        offer['tiles'].clear()
        self.assertEqual(self.s['contract_offer']['tiles'], [1, 39])
        self.assertEqual(self.s['contracts'], [])

    def test_accept_immediate_conserved_fee_and_exact_fields(self):
        contract = self.accept()
        self.assertEqual(contract, dict(id='id-0', owner='a', beneficiary='b', tiles=[1, 3], expires_turn=13, fee=100))
        self.assertEqual(self.balances(), [1600, 1400, 1500])
        self.assertEqual(sum(self.balances()), 4500)
        self.assertIsNone(self.s['contract_offer'])
        contract['tiles'].clear()
        self.assertEqual(self.s['contracts'][0]['tiles'], [1, 3])
        self.reject_call(c.respond, 'b', True)

    def test_free_waiver_and_all_28_tiles(self):
        self.accept(tiles=PROPERTY_IDS, turns=12, fee=0)
        self.assertEqual(self.balances(), [1500] * 3)
        self.assertEqual(len(self.s['contracts'][0]['tiles']), 28)
        self.assertTrue(c.waived(self.s, 'a', 'b', 39))

    def test_reject_and_cancel_do_not_move_money(self):
        self.propose()
        self.assertIsNone(c.respond(self.s, 'b', False))
        self.assertIsNone(self.s['contract_offer'])
        self.propose()
        self.assertIsNone(c.cancel(self.s, 'a'))
        self.assertIsNone(self.s['contract_offer'])
        self.assertEqual(self.balances(), [1500] * 3)

    def test_only_target_responds_and_only_owner_cancels(self):
        self.propose()
        for pid in ['a', 'c', 'missing']:
            self.reject_call(c.respond, pid, True)
            self.reject_call(c.respond, pid, False)
        for pid in ['b', 'c', 'missing']:
            self.reject_call(c.cancel, pid)
        for value in [1, 0, None, 'yes']:
            self.reject_call(c.respond, 'b', value)

    def test_no_offer_and_no_revocation_of_accepted_contract(self):
        self.reject_call(c.cancel, 'a')
        self.reject_call(c.respond, 'b', False)
        self.accept()
        self.reject_call(c.cancel, 'a')
        self.assertTrue(c.waived(self.s, 'a', 'b', 1))

    def test_only_one_pending_offer(self):
        self.propose()
        self.reject_call(c.propose, 'c', 'b', [1], 1, 0)

    def test_all_mutations_enforce_friendly_mode_and_playing(self):
        self.propose()
        baseline = deepcopy(self.s)
        for key, value in [('mode', 'classic'), ('mode', 'standard'), ('mode', None),
                           ('phase', 'lobby'), ('phase', 'finished')]:
            for fn, args in [(c.propose, ('a', 'b', [1], 1, 0)),
                             (c.respond, ('b', True)), (c.respond, ('b', False)), (c.cancel, ('a',))]:
                with self.subTest(key=key, value=value, fn=fn.__name__, args=args):
                    self.s = deepcopy(baseline)
                    self.s[key] = value
                    self.reject_call(fn, *args)

    def test_missing_mode_is_not_friendly(self):
        del self.s['mode']
        self.reject_call(c.propose, 'a', 'b', [1], 1, 0)

    def test_all_mutations_block_outstanding_decisions(self):
        self.propose()
        baseline = deepcopy(self.s)
        for key, value in [('debt', {'amount': 1}), ('auction', {'bid': 0}),
                           ('pending', 1), ('pending', 0), ('trade', {'target': 'b'})]:
            for fn, args in [(c.propose, ('a', 'b', [1], 1, 0)),
                             (c.respond, ('b', True)), (c.respond, ('b', False)), (c.cancel, ('a',))]:
                with self.subTest(key=key, fn=fn.__name__, args=args):
                    self.s = deepcopy(baseline)
                    self.s[key] = value
                    self.reject_call(fn, *args)

    def test_any_turn_and_rolled_does_not_change_contract_clock(self):
        self.s['rolled'] = True
        self.assertEqual(self.s['turn'], 'c')
        self.accept()
        self.assertEqual(self.s['turn_number'], 10)
        self.assertEqual(self.s['turn'], 'c')

    def test_invalid_participants(self):
        for owner, target in [('a', 'a'), ('missing', 'b'), ('a', 'missing')]:
            self.reject_call(c.propose, owner, target, [1], 1, 0)
        for index in [0, 1]:
            self.s['players'][index]['out'] = True
            self.reject_call(c.propose, 'a', 'b', [1], 1, 0)
            self.s['players'][index]['out'] = False

    def test_strict_numeric_and_tile_validation(self):
        for tiles in [None, (), [], [1, 1], [True], [1.0], ['1'], [-1], [0], [40], [2], [1]*29, {}]:
            with self.subTest(tiles=tiles):
                self.reject_call(c.propose, 'a', 'b', tiles, 1, 0)
        for turns in [True, False, 0, 13, -1, 1.0, '1', None]:
            self.reject_call(c.propose, 'a', 'b', [1], turns, 0)
        for fee in [True, False, -1, 1.0, '1', None]:
            self.reject_call(c.propose, 'a', 'b', [1], 1, fee)

    def test_exact_property_ownership_not_same_group(self):
        self.s['properties']['3']['owner'] = 'c'
        self.reject_call(c.propose, 'a', 'b', [1, 3], 1, 0)
        self.propose(tiles=[1])

    def test_accept_revalidates_refetched_ownership(self):
        self.propose()
        self.s = json.loads(json.dumps(self.s))
        self.s['properties']['3']['owner'] = 'c'
        self.reject_call(c.respond, 'b', True)

    def test_accept_revalidates_refetched_cash_and_can_retry(self):
        self.propose()
        self.s = json.loads(json.dumps(self.s))
        self.s['players'][1]['cash'] = 99
        self.reject_call(c.respond, 'b', True)
        self.s['players'][1]['cash'] = 100
        c.respond(self.s, 'b', True)
        self.assertEqual(self.balances(), [1600, 0, 1500])

    def test_no_loan_even_if_owner_has_cash(self):
        self.s['players'][1]['cash'] = 0
        self.propose(fee=1501)
        self.reject_call(c.respond, 'b', True)

    def test_accept_revalidates_out_removed_self_and_tampered_terms(self):
        self.propose()
        baseline = deepcopy(self.s)
        for change in ['owner_out', 'target_out', 'owner_removed', 'self', 'duplicates', 'turns', 'fee', 'tiles']:
            self.s = deepcopy(baseline)
            if change == 'owner_out': self.s['players'][0]['out'] = True
            elif change == 'target_out': self.s['players'][1]['out'] = True
            elif change == 'owner_removed': self.s['players'].pop(0)
            elif change == 'self': self.s['contract_offer']['offerer'] = 'b'
            elif change == 'duplicates': self.s['contract_offer']['tiles'] = [1, 1]
            elif change == 'turns': self.s['contract_offer']['turns'] = True
            elif change == 'fee': self.s['contract_offer']['fee'] = -1
            elif change == 'tiles': self.s['contract_offer']['tiles'] = [2]
            self.reject_call(c.respond, 'b', True)

    def test_same_pair_tile_overlap_forbidden_but_other_visitor_allowed(self):
        self.accept()
        self.reject_call(c.propose, 'a', 'b', [3, 5], 1, 0)
        self.propose(target='c', tiles=[1])
        c.respond(self.s, 'c', True)
        self.assertEqual(len(self.s['contracts']), 2)

    def seed_cap(self):
        self.s['contracts'] = [dict(id=str(i), owner='a', beneficiary='b', tiles=[tile], expires_turn=20, fee=0)
                               for i, tile in enumerate(PROPERTY_IDS[:8])]

    def test_cap_proposal_and_accept_recheck(self):
        self.seed_cap()
        self.reject_call(c.propose, 'a', 'b', [39], 1, 0)
        self.s['contracts'] = []
        self.propose(tiles=[39])
        self.seed_cap()
        self.reject_call(c.respond, 'b', True)

    def test_overlap_accept_recheck_is_atomic(self):
        self.propose()
        self.s['contracts'] = [dict(id='other', owner='a', beneficiary='b', tiles=[3], expires_turn=20, fee=0)]
        self.reject_call(c.respond, 'b', True)

    def test_cap_counts_only_active_and_does_not_reset_expiry(self):
        self.seed_cap()
        self.s['contracts'][0]['expires_turn'] = 10
        self.propose(tiles=[39], turns=1)
        self.assertEqual(len(self.s['contracts']), 7)
        c.respond(self.s, 'b', True)
        self.assertEqual(len(self.s['contracts']), 8)
        self.assertEqual(self.s['contracts'][0]['expires_turn'], 20)
        self.assertEqual(self.s['contracts'][-1]['expires_turn'], 11)

    def test_expiry_exact_global_boundary_no_refund(self):
        self.accept(turns=1)
        self.assertTrue(c.waived(self.s, 'a', 'b', 1))
        self.s['turn_number'] = 11
        self.assertFalse(c.waived(self.s, 'a', 'b', 1))
        c.cleanup(self.s)
        self.assertEqual(self.s['contracts'], [])
        self.assertEqual(self.balances(), [1600, 1400, 1500])
        self.assertEqual(self.s['turn_number'], 11)

    def test_clock_defaults_zero_and_starts_at_accept_not_propose(self):
        del self.s['turn_number']
        self.propose(turns=12)
        self.assertNotIn('turn_number', self.s)
        self.s['turn_number'] = 5
        contract = c.respond(self.s, 'b', True)
        self.assertEqual(contract['expires_turn'], 17)

    def test_invalid_clock_rejected_atomically(self):
        for value in [True, -1, 1.0, '1', None]:
            self.s['turn_number'] = value
            self.reject_call(c.propose, 'a', 'b', [1], 1, 0)

    def test_transfer_invalidates_only_subset_permanently(self):
        self.accept()
        self.s['properties']['1']['owner'] = 'c'
        self.assertFalse(c.waived(self.s, 'a', 'b', 1))
        self.assertTrue(c.waived(self.s, 'a', 'b', 3))
        c.cleanup(self.s)
        self.assertEqual(self.s['contracts'][0]['tiles'], [3])
        self.s['properties']['1']['owner'] = 'a'
        self.assertFalse(c.waived(self.s, 'a', 'b', 1))
        self.s['properties']['3']['owner'] = None
        c.cleanup(self.s)
        self.assertEqual(self.s['contracts'], [])
        self.assertEqual(self.balances(), [1600, 1400, 1500])

    def test_out_or_removed_participant_invalidates(self):
        self.accept()
        baseline = deepcopy(self.s)
        for index in [0, 1]:
            self.s = deepcopy(baseline)
            self.s['players'][index]['out'] = True
            self.assertFalse(c.waived(self.s, 'a', 'b', 1))
            c.cleanup(self.s)
            self.assertEqual(self.s['contracts'], [])
        self.s = deepcopy(baseline)
        self.s['players'].pop(0)
        c.cleanup(self.s)
        self.assertEqual(self.s['contracts'], [])

    def test_waiver_exact_direction_visitor_and_tile_and_read_only(self):
        self.accept(tiles=[1])
        before = deepcopy(self.s)
        for args in [('a', 'c', 1), ('b', 'a', 1), ('a', 'b', 3), ('a', 'a', 1), ('a', 'b', True)]:
            self.assertFalse(c.waived(self.s, *args))
        self.assertTrue(c.waived(self.s, 'a', 'b', 1))
        self.assertEqual(self.s, before)

    def test_active_mortgage_does_not_destroy_waiver(self):
        self.accept()
        self.s['properties']['1']['mortgaged'] = True
        c.cleanup(self.s)
        self.s['properties']['1']['mortgaged'] = False
        self.assertTrue(c.waived(self.s, 'a', 'b', 1))
        self.assertEqual(self.s['contracts'][0]['expires_turn'], 13)

    def test_cleanup_offer_invalidated_on_transfer_out_mode_or_finish(self):
        self.propose()
        baseline = deepcopy(self.s)
        for change in ['transfer', 'out', 'mode', 'finish']:
            self.s = deepcopy(baseline)
            if change == 'transfer': self.s['properties']['3']['owner'] = 'c'
            elif change == 'out': self.s['players'][1]['out'] = True
            elif change == 'mode': self.s['mode'] = 'classic'
            else: self.s['phase'] = 'finished'
            c.cleanup(self.s)
            self.assertIsNone(self.s['contract_offer'])

    def test_waiver_never_applies_in_classic_or_finished(self):
        self.accept()
        baseline = deepcopy(self.s)
        for key, value in [('mode', 'classic'), ('phase', 'finished')]:
            self.s = deepcopy(baseline)
            self.s[key] = value
            self.assertFalse(c.waived(self.s, 'a', 'b', 1))
            c.cleanup(self.s)
            self.assertEqual(self.s['contracts'], [])

    def test_failed_accept_does_not_cleanup_expired_contract_or_log(self):
        self.propose()
        self.s['contracts'] = [dict(id='old', owner='a', beneficiary='b', tiles=[1], expires_turn=0, fee=0)]
        self.s['players'][1]['cash'] = 0
        self.reject_call(c.respond, 'b', True)

    def test_public_snapshot_allowlist_detached_json_and_summary(self):
        self.accept()
        self.s['contracts'][0]['secret'] = 'hidden'
        self.propose(tiles=[39])
        self.s['contract_offer']['secret'] = 'hidden'
        self.s['decks'] = {'secret': 'hidden'}
        before = deepcopy(self.s)
        snapshot = c.public(self.s)
        self.assertEqual(json.loads(json.dumps(snapshot)), snapshot)
        self.assertEqual(set(snapshot), {'contracts', 'contract_offer'})
        self.assertNotIn('hidden', json.dumps(snapshot))
        text = c.summary(self.s)
        self.assertIn('не классическая', text)
        self.assertIn('Alice', text)
        self.assertIn('Bob', text)
        self.assertIn('13', text)
        self.assertIn('100', text)
        self.assertNotIn('hidden', text)
        snapshot['contracts'][0]['tiles'].clear()
        snapshot['contract_offer']['tiles'].clear()
        self.assertEqual(self.s, before)

    def test_stale_offer_hidden_in_public_without_mutation(self):
        self.propose()
        self.assertIn('Alice', c.summary(self.s))
        self.assertIn('Bob', c.summary(self.s))
        self.s['properties']['1']['owner'] = 'c'
        before = deepcopy(self.s)
        self.assertIsNone(c.public(self.s)['contract_offer'])
        self.assertEqual(self.s, before)

    def test_logs_bounded_and_cleanup_idempotent(self):
        self.s['log'] = ['old'] * 100
        self.accept()
        self.assertEqual(len(self.s['log']), 100)
        self.assertIn('Bob', self.s['log'][-1])
        c.cleanup(self.s)
        before = deepcopy(self.s)
        c.cleanup(self.s)
        self.assertEqual(self.s, before)


if __name__ == '__main__':
    unittest.main()
