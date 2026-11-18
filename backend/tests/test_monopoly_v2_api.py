"""API aggregate tests with fake persistence; deliberately not real PostgreSQL."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from test_monopoly_api import api, FakeDB, MonopolyAPIReview


class MonopolyV2API(unittest.IsolatedAsyncioTestCase):
    fixture=MonopolyAPIReview.fixture

    async def command(self,room,member,user,action,clock=None,version=None,**fields):
        clock=clock or datetime(2026,1,1,tzinfo=timezone.utc)
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'authenticated_room',AsyncMock(return_value=(room,member))),patch.object(api,'now',return_value=clock):
            return await api.command(room.id,api.CommandBody(key=uuid4(),version=room.version if version is None else version,action=action,**fields),user,FakeDB())

    async def test_board_metadata_marks_house_presets_and_explains_rules(self):
        result=await api.board(SimpleNamespace())
        modes={m['id']:m for m in result['modes']}
        self.assertEqual(set(modes),{'classic','friendly','timed20','timed40','timed60'})
        self.assertFalse(modes['classic']['house_rules'])
        self.assertTrue(all(modes[m]['house_rules'] for m in modes if m!='classic'))
        self.assertEqual(modes['timed20']['duration_minutes'],20)
        self.assertFalse(result['config']['forced_timeouts'])
        self.assertGreaterEqual(len(result['rules_synopsis']),10)

    async def test_create_timed_validates_mode_and_persists_json_no_migration(self):
        _,_,user=self.fixture()
        db=FakeDB([0]);db.flush=AsyncMock()
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)):
            result=await api.enter(api.CommandBody(key=uuid4(),action='create',mode='timed40',duration_minutes=40),user,db)
        self.assertEqual(result['state']['mode'],'timed40')
        self.assertEqual(result['state']['duration_minutes'],40)
        self.assertIsNone(result['state']['game_deadline'])
        self.assertEqual(result['event_version'],1)
        self.assertEqual(result['version'],1)

    async def test_create_mismatching_duration_rejects_without_added_room(self):
        _,_,user=self.fixture();db=FakeDB([0]);db.flush=AsyncMock()
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)):
            with self.assertRaises(api.HTTPException):
                await api.enter(api.CommandBody(key=uuid4(),action='create',mode='classic',duration_minutes=40),user,db)
        self.assertEqual(db.added,[])

    async def test_start_timed_clocks_begin_at_start_not_creation_and_show_initial_roll(self):
        room,member,user=self.fixture()
        room.state.update(mode='timed20',duration_minutes=20)
        for p in room.state['players']:p['ready']=True
        clock=datetime(2026,1,1,tzinfo=timezone.utc)
        with patch.object(api.rules,'randbelow',side_effect=[0,5]):
            result=await self.command(room,member,user,'start',clock=clock)
        self.assertEqual(result['state']['turn'],room.state['players'][1]['id'])
        self.assertEqual(result['state']['starter_rolls'][0][1]['die'],6)
        self.assertEqual(result['deadline'],(clock+timedelta(minutes=20)).isoformat())
        self.assertEqual([p['pos'] for p in room.state['players']],[0,0])

    async def test_old_json_snapshot_fallback_hides_legacy_forfeit_deadline(self):
        room,member,_=self.fixture(True)
        for key in ['mode','duration_minutes','game_deadline','turn_number']:room.state.pop(key,None)
        room.deadline=datetime(2020,1,1,tzinfo=timezone.utc)
        result=api.snapshot(room,member)
        self.assertEqual(result['state']['mode'],'classic')
        self.assertEqual(result['state']['turn_number'],0)
        self.assertIsNone(result['deadline'])
        self.assertNotIn('mode',room.state)

    async def test_timed_expired_debt_cannot_auto_bankrupt_or_end_before_settlement(self):
        room,member,user=self.fixture(True);clock=datetime(2026,1,1,tzinfo=timezone.utc)
        pid=str(member.id)
        room.state.update(mode='timed20',duration_minutes=20,game_deadline=clock.isoformat())
        room.state['properties']['39']['owner']=pid
        api.rules.player(room.state,pid)['cash']=0
        api.rules.charge(room.state,api.rules.player(room.state,pid),50)
        original=deepcopy(room.state)
        with self.assertRaises(api.HTTPException):await self.command(room,member,user,'timeout',clock=clock)
        self.assertEqual(original,room.state)
        result=await self.command(room,member,user,'mortgage',tile=39,clock=clock)
        self.assertEqual(result['status'],'finished')
        self.assertIsNone(result['state']['debt'])
        self.assertEqual(result['state']['scores'][pid],350)
        self.assertFalse(any(p['out'] for p in room.state['players']))

    async def test_expired_auction_finishes_only_after_last_bid_decision(self):
        room,member,user=self.fixture(True);clock=datetime(2026,1,1,tzinfo=timezone.utc)
        room.state.update(mode='timed20',duration_minutes=20,game_deadline=clock.isoformat())
        api.rules.auction(room.state,1)
        with self.assertRaises(api.HTTPException):await self.command(room,member,user,'timeout',clock=clock)
        await self.command(room,member,user,'pass',clock=clock)
        other=SimpleNamespace(id=room.state['players'][1]['id'])
        result=await self.command(room,other,user,'pass',clock=clock)
        self.assertEqual(result['status'],'finished')
        self.assertIsNone(result['state']['auction'])
        self.assertEqual(len(result['state']['winners']),2)
        self.assertIsNone(result['state']['winner'])

    async def test_host_surrender_foreign_turn_changes_host_not_active_turn(self):
        room,member,user=self.fixture(True)
        third=str(uuid4());room.state['players'].append(api.rules.new_player(third,'Third'))
        guest=room.state['players'][1]['id'];room.state['turn']=guest
        result=await self.command(room,member,user,'resign')
        self.assertEqual(result['host'],guest)
        self.assertEqual(result['state']['turn'],guest)
        self.assertTrue(api.rules.player(room.state,str(member.id))['out'])
        self.assertEqual((result['version'],result['event_version']),(2,2))

    async def test_game_version_not_event_cursor_controls_commands(self):
        room,member,user=self.fixture(True);room.event_version=15
        room.state['properties']['1']['owner']=str(member.id)
        result=await self.command(room,member,user,'mortgage',tile=1,version=1)
        self.assertEqual((result['version'],result['event_version']),(2,16))
        before=deepcopy(room.state)
        with self.assertRaises(api.HTTPException):await self.command(room,member,user,'redeem',tile=1,version=1)
        self.assertEqual(room.state,before)
        self.assertEqual((room.version,room.event_version),(2,16))

    async def test_journal_fingerprint_default_v2_fields_preserve_v1_replays(self):
        body=api.CommandBody(key=uuid4(),version=7,action='mortgage',tile=1)
        data=body.model_dump(mode='json')
        for key in ['use_telegram_name','mode','duration_minutes','give_cards','take_cards','redeem_give','redeem_take','contract_tiles','contract_turns','contract_fee']:data.pop(key)
        old=sha256(('path'+json.dumps(data,sort_keys=True,ensure_ascii=False)).encode()).hexdigest()
        self.assertEqual(api.fingerprint(body,'path'),old)
        self.assertNotEqual(api.fingerprint(body.model_copy(update={'give_cards':['chance']}),'path'),old)

    async def test_friendly_contract_command_is_atomic_and_versions_durable(self):
        room,member,user=self.fixture(True);room.state['mode']='friendly'
        host=str(member.id);guest=room.state['players'][1]['id'];room.state['properties']['1']['owner']=host
        await self.command(room,member,user,'propose_contract',target=guest,contract_tiles=[1],contract_turns=2,contract_fee=10)
        self.assertEqual(room.version,2)
        result=await self.command(room,SimpleNamespace(id=guest),user,'accept_contract')
        self.assertEqual(result['state']['contracts'][0]['expires_turn'],2)
        self.assertEqual(api.rules.player(room.state,host)['cash'],1510)
        self.assertEqual(api.rules.player(room.state,guest)['cash'],1490)
        self.assertEqual((room.version,room.event_version),(3,3))
        self.assertIsNone(result['deadline'])

    async def test_dto_rejects_coercive_contract_currency_and_tile_types(self):
        from pydantic import ValidationError
        for field in ['contract_turns','contract_fee','cash','ask','amount','tile','duration_minutes']:
            for bad in [True,1.0,'1']:
                with self.subTest(field=field,bad=bad),self.assertRaises(ValidationError):
                    api.CommandBody(key=uuid4(),action='propose_contract',**{field:bad})
        for field in ['contract_tiles','give','take','redeem_give','redeem_take']:
            for bad in [True,1.0,'1']:
                with self.subTest(field=field,bad=bad),self.assertRaises(ValidationError):
                    api.CommandBody(key=uuid4(),action='trade',**{field:[bad]})
