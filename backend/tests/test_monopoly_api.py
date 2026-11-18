"""Offline witnesses. Run alone; no .env, network or DB connection.
Fixed API, cleanup and frozen-schema regressions; fake sessions do not prove SQL concurrency.
"""
import importlib
import sys
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

settings_module = ModuleType("app.config")
settings_module.config = SimpleNamespace(database_url="postgresql+asyncpg://review:synthetic_only@127.0.0.1:1/review")
with patch.dict(sys.modules, {"app.config": settings_module}):
    api = importlib.import_module("app.games.monopoly_router")
    cleanup = importlib.import_module("app.games.monopoly_cleanup")


class FakeDB:
    def __init__(self, results=(), room=None):
        self.results = iter(results)
        self.room = room
        self.added = []

    @asynccontextmanager
    async def begin(self):
        yield

    async def execute(self, statement):
        return SimpleNamespace(scalar_one=lambda: next(self.results), scalar_one_or_none=lambda: self.room)

    def add(self, value):
        self.added.append(value)


class MonopolyAPIReview(unittest.IsolatedAsyncioTestCase):
    def fixture(self, playing=False):
        mid, other = uuid4(), uuid4()
        state = api.rules.new_state(str(mid), "Host")
        state["players"].append(api.rules.new_player(str(other), "Guest"))
        state["phase"] = "playing" if playing else "lobby"
        room = SimpleNamespace(id=uuid4(), code="a" * 20, title="Review", public=False,
                               capacity=4, status=state["phase"], version=1, event_version=1,
                               host=str(mid), state=state, deadline=None)
        return room, SimpleNamespace(id=mid), SimpleNamespace(id=100001, account_generation="review-generation")

    async def test_noop_cancel_cannot_extend_decision_deadline(self):
        room, member, user = self.fixture(playing=True)
        clock = datetime(2026, 1, 1, tzinfo=timezone.utc)
        room.deadline = clock + timedelta(seconds=1)
        deadline = room.deadline
        body = api.CommandBody(key=uuid4(), version=1, action="cancel_trade")
        with patch.object(api, "rate_limit", AsyncMock()), patch.object(api, "lock_authenticated_user", AsyncMock()), patch.object(api, "replay", AsyncMock(return_value=None)), patch.object(api, "authenticated_room", AsyncMock(return_value=(room, member))), patch.object(api, "now", return_value=clock):
            try:
                await api.command(room.id, body, user, FakeDB())
            except api.HTTPException as exc:
                self.assertEqual(409, exc.status_code)
        self.assertEqual(deadline, room.deadline, "No trade or actor changed; deadline must not restart")

    async def test_code_reconnect_allowed_when_already_in_eight_rooms(self):
        room, member, user = self.fixture()
        body = api.CommandBody(key=uuid4(), action="join", code=room.code)
        db = FakeDB([8], room=room)
        with patch.object(api, "rate_limit", AsyncMock()), patch.object(api, "lock_authenticated_user", AsyncMock()), patch.object(api, "replay", AsyncMock(return_value=None)), patch.object(api, "membership", AsyncMock(return_value=member)):
            result = await api.enter(body, user, db)
        self.assertEqual(str(member.id), result["you"])

    async def test_snapshot_excludes_code_from_public_summary_and_hidden_decks(self):
        room, member, _ = self.fixture()
        self.assertNotIn("code", api.summary(room))
        self.assertNotIn("decks", api.snapshot(room, member)["state"])
        self.assertIn("decks", room.state)

    async def test_replay_rejects_changed_payload(self):
        _, _, user = self.fixture()
        previous = SimpleNamespace(fingerprint="old", response={"private": "synthetic"})
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: previous)))
        with self.assertRaises(api.HTTPException) as caught:
            await api.replay(db, user, "new", uuid4())
        self.assertEqual(409, caught.exception.status_code)


class Rows:
    def __init__(self, values): self.values=values
    def scalars(self): return self
    def all(self): return self.values


class SequenceDB(FakeDB):
    def __init__(self, rows):
        super().__init__()
        self.rows=iter(rows)
        self.statements=[]
    async def execute(self, statement):
        self.statements.append(statement)
        return Rows(next(self.rows,[]))


class FixedRegressions(unittest.IsolatedAsyncioTestCase):
    fixture=MonopolyAPIReview.fixture
    async def test_classic_management_clears_legacy_forfeit_clock(self):
        room,member,user=self.fixture(True)
        clock=datetime(2026,1,1,tzinfo=timezone.utc)
        room.deadline=clock-timedelta(hours=1)
        room.state['turn_started_at']=(clock-timedelta(hours=2)).isoformat()
        room.state['properties']['1']['owner']=str(member.id)
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'authenticated_room',AsyncMock(return_value=(room,member))),patch.object(api,'now',return_value=clock):
            await api.command(room.id,api.CommandBody(key=uuid4(),version=1,action='mortgage',tile=1),user,FakeDB())
        self.assertIsNone(room.deadline)
        self.assertNotIn('turn_started_at',room.state)
        self.assertFalse(any(p['out'] for p in room.state['players']))
        self.assertEqual(room.version,2)
        self.assertEqual(room.event_version,2)

    async def test_classic_legacy_timeout_never_bankrupts_trade_or_auction_actor(self):
        for pending in ['turn','debt','auction','trade']:
            with self.subTest(pending=pending):
                room,member,user=self.fixture(True)
                clock=datetime(2026,1,1,tzinfo=timezone.utc)
                room.state.pop('mode',None)
                room.deadline=clock-timedelta(hours=1)
                if pending=='auction': api.rules.auction(room.state,1)
                if pending=='trade': room.state['trade']={'from':str(member.id),'target':room.state['players'][1]['id']}
                if pending=='debt': room.state['debt']={'player':str(member.id),'amount':100,'creditor':None}
                from copy import deepcopy
                before=deepcopy(room.state)
                with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'authenticated_room',AsyncMock(return_value=(room,member))),patch.object(api,'now',return_value=clock):
                    with self.assertRaises(api.HTTPException):
                        await api.command(room.id,api.CommandBody(key=uuid4(),version=1,action='timeout'),user,FakeDB())
                self.assertEqual(before,room.state)
                self.assertEqual(room.version,1)

    async def test_timed_deadline_survives_management_doubles_and_turn_changes(self):
        room,member,user=self.fixture(True)
        clock=datetime(2026,1,1,tzinfo=timezone.utc)
        due=clock+timedelta(minutes=20)
        room.state.update(mode='timed20',duration_minutes=20,game_deadline=due.isoformat())
        for extra in [True,False]:
            s=room.state;s.update(rolled=True,extra=extra)
            previous=s['turn']; before=api.decision_key(s)
            if not extra:s['turn']=s['players'][1]['id']
            api.update_deadlines(room,s,previous,before,clock+timedelta(minutes=14))
            self.assertEqual(due,room.deadline)
            self.assertEqual(due.isoformat(),s['game_deadline'])

    async def test_new_slot_rejected_at_eight(self):
        _, _, user=self.fixture()
        with self.assertRaises(api.HTTPException) as caught:
            await api.require_room_slot(FakeDB([8]),user)
        self.assertEqual(409,caught.exception.status_code)

    async def test_owned_rooms_not_bounded_by_discovery_limit(self):
        room, _, user=self.fixture()
        public=[]
        for _ in range(50):
            other, _, _=self.fixture();public.append(other)
        db=SequenceDB([[room.id],[room],public])
        with patch.object(api,'lock_authenticated_user',AsyncMock()):
            result=await api.rooms(user,db)
        self.assertEqual(51,len(result['items']))
        self.assertTrue(result['items'][0]['mine'])
        self.assertIsNone(db.statements[1]._limit_clause)
        self.assertEqual(50,db.statements[2]._limit_clause.value)

    async def test_decision_identity_ignores_assets_but_tracks_actor_and_offer(self):
        from copy import deepcopy
        room, _, _=self.fixture(True)
        s=room.state;k=api.decision_key(s)
        s['players'][0]['cash']-=100
        self.assertEqual(k,api.decision_key(s))
        s['rolled']=True
        self.assertNotEqual(k,api.decision_key(s))
        s['debt']={'player':s['turn'],'creditor':None,'amount':100}
        debt=api.decision_key(s);s['debt']['amount']=50
        self.assertEqual(debt,api.decision_key(s))
        s['auction']={'tile':1,'actor':s['turn'],'bid':10,'bidder':s['turn']}
        auction=api.decision_key(s);s['auction']['bid']=20
        self.assertNotEqual(auction,api.decision_key(s))
        s['auction']['actor']=s['players'][1]['id']
        self.assertNotEqual(auction,api.decision_key(s))

    async def cleanup_fixture(self, playing=False, historical=False):
        from copy import deepcopy
        room, member, user=self.fixture(playing)
        member.room_id=room.id
        private_name=room.state['players'][0]['name']
        response=api.snapshot(room,member)
        room.state['log']=[private_name+' secret history']
        response['state']['log']=[private_name+' secret history']
        own=SimpleNamespace(response=deepcopy(response))
        other=SimpleNamespace(response=deepcopy(response))
        if historical:
            room.state['players']=room.state['players'][1:]
            room.host=room.state['players'][0]['id'];room.state['turn']=room.host
        db=SequenceDB([[] if historical else [member],[own],[room],[other],[]])
        await cleanup.cleanup_account(db,user)
        self.assertEqual(2,room.event_version)
        self.assertNotIn(private_name,str(room.state))
        self.assertNotIn(private_name,str(other.response))
        self.assertIsNotNone(db.statements[2]._for_update_arg)
        self.assertIn('ORDER BY monopoly_rooms.id',str(db.statements[2]))
        self.assertIn('DELETE FROM monopoly_messages',str(db.statements[-1]))
        return room,member

    async def test_delete_lobby_host_transfers_host_and_removes_player(self):
        room,member=await self.cleanup_fixture()
        self.assertNotEqual(str(member.id),room.host)
        self.assertEqual(room.host,room.state['turn'])
        self.assertEqual(1,len(room.state['players']))
        self.assertEqual('lobby',room.status)

    async def test_delete_running_participant_finishes_without_winner(self):
        room,_=await self.cleanup_fixture(True)
        self.assertEqual('finished',room.status)
        self.assertIsNone(room.state['winner'])
        self.assertIsNone(room.deadline)
        self.assertIn('без победителя',room.state['log'][0])

    async def test_delete_scrubs_historical_left_room_snapshots(self):
        await self.cleanup_fixture(historical=True)

    async def test_frozen_migration_matches_orm_columns_and_constraints(self):
        from pathlib import Path
        from sqlalchemy import MetaData, Table
        from sqlalchemy.schema import CreateTable
        from sqlalchemy.dialects.postgresql import dialect
        path=Path(__file__).resolve().parents[1]/'alembic'/'versions'/'0005_monopoly.py'
        spec=importlib.util.spec_from_file_location('review_migration',path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        tables={};indexes=[];metadata=MetaData()
        def create_table(name,*columns):tables[name]=Table(name,metadata,*columns)
        with patch.object(migration.op,'create_table',side_effect=create_table),patch.object(migration.op,'create_index',side_effect=lambda *args:indexes.append(args)):
            migration.upgrade()
        for model in [api.Room,api.Member,api.Command,api.Message]:
            frozen=tables[model.__tablename__];live=model.__table__
            self.assertEqual(list(live.columns.keys()),list(frozen.columns.keys()))
            for a,b in zip(live.columns,frozen.columns):
                self.assertEqual(str(a.type),str(b.type));self.assertEqual(a.nullable,b.nullable)
            self.assertEqual({(fk.target_fullname,fk.ondelete) for fk in live.foreign_keys},{(fk.target_fullname,fk.ondelete) for fk in frozen.foreign_keys})
        self.assertEqual(3,len(indexes))


if __name__ == "__main__":
    unittest.main()
