"""C1009-aligned rules and explicit online/house policies; no real database."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from test_monopoly_engine import e


class MonopolyV2(unittest.TestCase):
    def setUp(self):
        self.s=e.new_state('a','Alice')
        self.s['players'] += [e.new_player('b','Bob'),e.new_player('c','Carol')]
        self.s['phase']='playing'

    def own(self,pid,ids,houses=0,mortgaged=False):
        for tile in ids:e.prop(self.s,tile).update(owner=pid,houses=houses,mortgaged=mortgaged)

    def p(self,pid='a'):return e.player(self.s,pid)

    def act(self,action,pid='a',**kw):
        self.s=e.act(self.s,pid,action,**kw)
        return self.s

    def reject(self,action,pid='a',**kw):
        before=deepcopy(self.s)
        with self.assertRaises(HTTPException):e.act(self.s,pid,action,**kw)
        self.assertEqual(before,self.s)

    def card(self,pid,deck):
        self.s['decks'][deck].remove(0);self.p(pid)['cards'].append(deck)

    def test_modes_validate_duration_and_default_classic(self):
        self.assertEqual(self.s['mode'],'classic')
        for minutes in [20,40,60]:
            s=e.new_state('a','A',f'timed{minutes}',minutes)
            self.assertEqual(s['duration_minutes'],minutes)
        for mode,duration in [('timed20',40),('classic',20),('friendly',20),('unknown',None)]:
            with self.subTest(mode=mode,duration=duration),self.assertRaises(HTTPException):e.new_state('a','A',mode,duration)

    def test_start_roll_tie_rerolls_leaders_only_no_movement(self):
        with patch.object(e,'randbelow',side_effect=[5,5,0,1,4]):e.start(self.s)
        self.assertEqual(self.s['turn'],'b')
        self.assertEqual(len(self.s['starter_rolls'][1]),2)
        self.assertEqual([p['pos'] for p in self.s['players']],[0,0,0])
        self.assertEqual([p['cash'] for p in self.s['players']],[1500]*3)

    def test_build_mortgage_redeem_foreign_turn_in_jail(self):
        self.own('b',[1,3]);e.jail(self.s,self.p('b'))
        self.act('build',pid='b',tile=1)
        self.act('sell',pid='b',tile=1)
        self.act('mortgage',pid='b',tile=1)
        self.act('redeem',pid='b',tile=1)
        self.assertEqual(self.s['turn'],'a')
        self.assertTrue(self.p('b')['jailed'])

    def test_trade_foreign_turn_does_not_freeze_current_player(self):
        self.own('b',[1]);self.act('trade',pid='b',target='c',give=[1],ask=30)
        with patch.object(e,'randbelow',side_effect=[0,1]):self.act('roll')
        self.act('accept_trade',pid='c')
        self.assertEqual(e.prop(self.s,1)['owner'],'c')
        self.assertEqual(self.s['turn'],'a')

    def test_trade_both_deck_cards_and_use_exact_received_card(self):
        self.card('a','chance');self.card('b','chest')
        self.act('trade',target='b',give_cards=['chance'],take_cards=['chest'])
        self.act('accept_trade',pid='b')
        self.assertEqual(self.p()['cards'],['chest']);self.assertEqual(self.p('b')['cards'],['chance'])
        e.jail(self.s,self.p());self.act('jail_card')
        self.assertIn(0,self.s['decks']['chest']);self.assertNotIn(0,self.s['decks']['chance'])

    def test_trade_card_stale_accept_rejected_without_mutation(self):
        self.card('a','chance');self.act('trade',target='b',give_cards=['chance'],ask=20)
        self.p()['cards']=[];self.s['decks']['chance'].append(0)
        self.reject('accept_trade',pid='b')

    def test_trade_stale_owner_or_new_building_rejected_atomically(self):
        self.own('a',[1,3]);self.act('trade',target='b',give=[1],ask=50)
        for mutate in [lambda:e.prop(self.s,1).update(owner='c'),lambda:e.prop(self.s,3).update(houses=1)]:
            original=deepcopy(self.s);mutate();self.reject('accept_trade',pid='b');self.s=original

    def test_trade_keep_mortgage_then_later_redemption_pays_extra_interest(self):
        self.own('a',[39],mortgaged=True)
        self.act('trade',target='b',give=[39]);self.act('accept_trade',pid='b')
        self.assertEqual(self.p('b')['cash'],1480)
        self.act('redeem',pid='b',tile=39)
        self.assertEqual(self.p('b')['cash'],1260)

    def test_trade_immediate_redemption_costs_principal_plus_interest_once(self):
        self.own('a',[39],mortgaged=True)
        self.act('trade',target='b',give=[39],redeem_give=[39]);self.act('accept_trade',pid='b')
        self.assertFalse(e.prop(self.s,39)['mortgaged']);self.assertEqual(self.p('b')['cash'],1280)

    def test_trade_mortgage_interest_affordability_rechecked_and_no_debt_overwrite(self):
        self.own('a',[39],mortgaged=True);self.act('trade',target='b',give=[39])
        self.p('b')['cash']=0
        self.s['debt']=dict(player='c',amount=50,creditor=None)
        self.reject('accept_trade',pid='b')
        self.assertEqual(self.s['debt'],dict(player='c',amount=50,creditor=None))

    def test_foreign_debtor_can_sell_jail_card_and_asset_to_third_player(self):
        self.own('b',[1]);self.card('b','chance');self.p('b')['cash']=0;e.jail(self.s,self.p('b'))
        e.charge(self.s,self.p('b'),70,'a')
        self.act('trade',pid='b',target='c',give=[1],give_cards=['chance'],ask=70)
        self.act('accept_trade',pid='c')
        self.assertIsNone(self.s['debt']);self.assertEqual(self.p()['cash'],1570)
        self.assertEqual(e.prop(self.s,1)['owner'],'c');self.assertEqual(self.p('c')['cards'],['chance'])
        self.assertEqual(self.s['turn'],'a')

    def test_sell_entire_group_when_hotels_cannot_downgrade(self):
        self.own('a',[1,3],5)
        for ids,group,cost in e.GROUPS[1:4]:self.own('b',ids,4)
        self.reject('sell',tile=1)
        self.act('sell_group',tile=1)
        self.assertEqual([e.prop(self.s,i)['houses'] for i in [1,3]],[0,0])
        self.assertEqual(self.p()['cash'],1750)

    def test_quit_foreign_turn_preserves_active_turn_and_auctions_assets(self):
        self.own('b',[39]);self.act('resign',pid='b',target='c')
        self.assertEqual(self.s['turn'],'a');self.assertTrue(self.p('b')['out'])
        self.assertIsNone(e.prop(self.s,39)['owner']);self.assertEqual(self.s['auction']['tile'],39)

    def test_quit_debtor_transfers_to_actual_creditor_not_target(self):
        self.own('b',[39]);self.p('b')['cash']=0;e.charge(self.s,self.p('b'),100,'a')
        self.act('resign',pid='b',target='c')
        self.assertEqual(e.prop(self.s,39)['owner'],'a');self.assertIsNone(self.s['debt'])
        self.assertEqual(self.s['turn'],'a')

    def test_quit_creditor_preserves_foreign_debt_as_bank_claim(self):
        self.p('c')['cash']=0;e.charge(self.s,self.p('c'),100,'b')
        self.act('resign',pid='b')
        self.assertEqual(self.s['debt'],dict(player='c',amount=100,creditor=None))
        self.assertFalse(self.p('c')['out'])

    def test_quit_current_auction_actor_advances_without_ending_other_turn(self):
        self.s['turn']='c';e.auction(self.s,1);self.act('resign')
        self.assertEqual(self.s['auction']['actor'],'b');self.assertEqual(self.s['turn'],'c')
        self.act('pass',pid='b');self.act('pass',pid='c');self.assertIsNone(self.s['auction'])

    def test_quit_high_bidder_cancels_bid_reopens_passed_players(self):
        e.auction(self.s,1);self.act('bid',amount=100);self.act('pass',pid='b')
        self.act('resign')
        self.assertEqual(self.s['auction']['bid'],0);self.assertIsNone(self.s['auction']['bidder'])
        self.assertEqual(self.s['auction']['actor'],'b')
        self.act('bid',pid='b',amount=10);self.act('pass',pid='c')
        self.assertEqual(e.prop(self.s,1)['owner'],'b');self.assertEqual(self.p('b')['cash'],1490)

    def test_quit_current_pending_property_enters_bank_auction_queue(self):
        self.s['pending']=39;self.act('resign')
        self.assertEqual(self.s['turn'],'b');self.assertEqual(self.s['auction']['tile'],39)

    def last_house(self):
        self.own('a',[1,3]);self.own('b',[6,8,9]);self.own('c',[11,13,14,16,18,19],4)
        self.own('c',[21,23,24],2);e.prop(self.s,21)['houses']=3
        self.assertEqual(e.building_stock(self.s,'house'),1)

    def test_last_house_requires_auction_not_first_click_win(self):
        self.last_house();self.reject('build',tile=1)
        self.act('start_build_auction',tile=1)
        self.assertEqual(self.s['auction']['kind'],'building')
        self.assertEqual(self.s['auction']['placements']['b'],[6,8,9])

    def test_building_auction_places_winners_choice_and_only_spends_winning_bid(self):
        self.last_house();self.act('start_build_auction',tile=1)
        self.act('bid',amount=10);self.act('bid',pid='b',amount=11,tile=9)
        self.act('pass',pid='c');self.act('pass')
        self.assertIsNone(self.s['auction']);self.assertEqual(e.prop(self.s,9)['houses'],1)
        self.assertEqual(self.p()['cash'],1500);self.assertEqual(self.p('b')['cash'],1489)
        self.assertEqual(e.building_stock(self.s,'house'),0)

    def test_building_auction_rejects_wrong_placement_and_cannot_spend_escrow(self):
        self.last_house();self.act('start_build_auction',tile=1)
        self.reject('bid',amount=10,tile=6)
        self.reject('mortgage',tile=1);self.reject('trade',target='b',cash=1500)
        self.reject('bid',amount=9,tile=1)

    def test_building_auction_all_pass_returns_stock_unchanged(self):
        self.last_house();self.act('start_build_auction',tile=1)
        for pid in ['a','b','c']:self.act('pass',pid=pid)
        self.assertIsNone(self.s['auction']);self.assertEqual(e.building_stock(self.s,'house'),1)

    def test_building_auction_high_bidder_can_surrender(self):
        self.last_house();self.act('start_build_auction',tile=1);self.act('bid',amount=10)
        self.act('resign')
        self.assertIsNone(self.s['auction']['bidder']);self.assertEqual(self.s['auction']['actor'],'b')
        self.act('bid',pid='b',amount=10);self.act('pass',pid='c')
        self.assertEqual(e.prop(self.s,6)['houses'],1)

    def test_timed_valuation_and_tie_no_arbitrary_winner(self):
        self.own('a',[1],2);self.own('a',[3],mortgaged=True)
        self.assertEqual(e.net_worth(self.s,'a'),1690)
        self.p('b')['cash']=1690;self.s['game_deadline']='2026-01-01T00:00:00+00:00'
        self.s['trade']={'unaccepted':'offer'};self.s['contract_offer']={'unaccepted':'offer'}
        self.assertTrue(e.finish_timed(self.s,datetime(2026,1,1,tzinfo=timezone.utc)))
        self.assertEqual(self.s['winners'],['a','b']);self.assertIsNone(self.s['winner'])
        self.assertIsNone(self.s['trade']);self.assertIsNone(self.s['contract_offer'])

    def test_timed_expiry_waits_for_every_unsettled_obligation(self):
        clock=datetime(2026,1,1,tzinfo=timezone.utc);self.s['game_deadline']=clock.isoformat()
        for key,value in [('debt',dict(player='a',amount=50,creditor=None)),('auction',{'tile':1}),('pending',1),('bank_queue',[1]),('payments',[{}]),('collections',['b']),('jail_move',3)]:
            with self.subTest(key=key):
                state=deepcopy(self.s);state[key]=value
                self.assertFalse(e.finish_timed(state,clock));self.assertEqual(state['phase'],'playing')
                self.assertFalse(any(p['out'] for p in state['players']))

    def test_friendly_agreement_integrates_rent_expiry_and_permanent_transfer_invalidation(self):
        self.s['mode']='friendly';self.own('a',[1]);self.act('propose_contract',target='b',contract_tiles=[1],contract_turns=2,contract_fee=10)
        self.act('accept_contract',pid='b');self.p('b')['pos']=1;e.land(self.s,self.p('b'))
        self.assertEqual(self.p('b')['cash'],1490)
        self.act('trade',target='c',give=[1]);self.act('accept_trade',pid='c')
        self.assertEqual(self.s['contracts'],[])
        self.act('trade',pid='c',target='a',give=[1]);self.act('accept_trade')
        e.land(self.s,self.p('b'));self.assertEqual(self.p('b')['cash'],1488)

    def test_turn_counter_doubles_do_not_expire_contract_early(self):
        self.s.update(rolled=True,extra=True);self.act('end')
        self.assertEqual(self.s['turn_number'],0)
        self.s.update(rolled=True,extra=False);self.act('end')
        self.assertEqual(self.s['turn_number'],1)

    def test_legacy_json_state_still_plays_without_mode_migration(self):
        for key in ['mode','duration_minutes','game_deadline','turn_number']:self.s.pop(key,None)
        self.own('b',[1,3]);self.act('build',pid='b',tile=1)
        self.s['rolled']=True;self.act('end')
        self.assertEqual(self.s['turn_number'],1)

    def test_quit_foreign_owner_keeps_current_unowned_purchase_pending(self):
        self.s['pending']=39;self.own('b',[1,3]);self.act('resign',pid='b')
        self.assertEqual(self.s['pending'],39)
        for _ in range(2):
            self.act('pass');self.act('pass',pid='c')
        self.assertIsNone(self.s['auction']);self.assertEqual(self.s['pending'],39)
        self.act('buy');self.assertEqual(e.prop(self.s,39)['owner'],'a')

    def test_bankruptcy_not_allowed_when_assets_cover_debt_but_surrender_is(self):
        self.own('a',[39]);self.p()['cash']=0;e.charge(self.s,self.p(),100)
        self.reject('bankrupt');self.act('resign')
        self.assertTrue(self.p()['out'])

    def test_last_hotel_auction_uses_four_house_slots_and_returns_houses(self):
        self.own('a',[1,3],4);self.own('b',[6,8,9],4)
        for ids,group,cost in e.GROUPS[2:6]:self.own('c',ids,5)
        e.prop(self.s,29)['houses']=4
        self.assertEqual(e.building_stock(self.s,'hotel'),1)
        stock=e.building_stock(self.s,'house')
        self.reject('build',tile=1);self.act('start_build_auction',tile=1)
        self.assertEqual(self.s['auction']['building'],'hotel')
        self.act('bid',amount=10,tile=3);self.act('pass',pid='b');self.act('pass',pid='c')
        self.assertEqual(e.prop(self.s,3)['houses'],5)
        self.assertEqual(e.building_stock(self.s,'hotel'),0)
        self.assertEqual(e.building_stock(self.s,'house'),stock+4)

    def test_friendly_two_turn_expiry_and_unanswered_offer_do_not_block_turn(self):
        self.s['mode']='friendly';self.own('a',[1]);self.own('c',[3])
        self.act('propose_contract',target='b',contract_tiles=[1],contract_turns=2)
        self.act('accept_contract',pid='b')
        self.s['rolled']=True;self.act('end')
        self.p('b')['pos']=1;e.land(self.s,self.p('b'))
        self.assertEqual(self.p('b')['cash'],1500)
        self.act('propose_contract',pid='c',target='a',contract_tiles=[3])
        self.s['rolled']=True;self.act('end',pid='b')
        self.assertEqual(self.s['turn_number'],2)
        self.assertEqual(self.s['contracts'],[])
        self.p('b')['pos']=1;e.land(self.s,self.p('b'))
        self.assertEqual(self.p('b')['cash'],1498)
        self.assertEqual(self.s['turn'],'c')
