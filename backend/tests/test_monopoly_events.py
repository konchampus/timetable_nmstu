"""Deterministic offline event witnesses; no DB/network/.env. Not a PG race proof."""
import asyncio
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
# Reuse the existing offline bootstrap (synthetic settings, never production env).
from test_monopoly_api import api, FakeDB, MonopolyAPIReview
import importlib
import sys
from test_monopoly_api import settings_module
with patch.dict(sys.modules, {"app.config": settings_module}):
    events = importlib.import_module("app.games.monopoly_events")


class EventTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=123, auth_token_hash='synthetic', auth_account_generation='old')
        self.request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        self.rid = uuid4()

    async def test_changed_is_tiny_and_final_auth_checked(self):
        read = AsyncMock(side_effect=[8, 9])
        with patch.object(events, 'read_event_version', read):
            result = await events.wait_for_events(self.rid, self.user, 7, self.request)
        self.assertEqual({'event_version': 9, 'changed': True}, result)
        self.assertEqual(2, read.await_count)

    async def test_timeout_fake_clock_and_no_sleeping_session(self):
        clock = [0.0]
        async def sleep(delay): clock[0] += delay
        with patch.object(events, 'monotonic', lambda: clock[0]), patch.object(events.asyncio, 'sleep', sleep), patch.object(events, 'read_event_version', AsyncMock(return_value=4)) as read:
            result = await events.wait_for_events(self.rid, self.user, 4, self.request)
        self.assertEqual({'event_version': 4, 'changed': False}, result)
        self.assertAlmostEqual(18, clock[0])
        self.assertGreaterEqual(read.await_count, 61)

    async def test_change_detected_after_one_300ms_tick(self):
        clock = [0.0]
        async def sleep(delay): clock[0] += delay
        with patch.object(events, 'monotonic', lambda: clock[0]), patch.object(events.asyncio, 'sleep', sleep), patch.object(events, 'read_event_version', AsyncMock(side_effect=[1,2,2])):
            result = await events.wait_for_events(self.rid, self.user, 1, self.request)
        self.assertTrue(result['changed'])
        self.assertEqual(0.3, clock[0])

    async def test_revocation_at_final_check_never_emits_changed_payload(self):
        for status in [401,403]:
            with patch.object(events, 'read_event_version', AsyncMock(side_effect=[2, events.HTTPException(status, 'revoked')])):
                with self.assertRaises(events.HTTPException) as caught:
                    await events.wait_for_events(self.rid, self.user, 1, self.request)
                self.assertEqual(status, caught.exception.status_code)

    async def test_timeout_final_check_also_rejects_revoked_membership(self):
        with patch.object(events, 'monotonic', side_effect=[0,18]), patch.object(events, 'read_event_version', AsyncMock(side_effect=[1, events.HTTPException(403)])):
            with self.assertRaises(events.HTTPException):
                await events.wait_for_events(self.rid, self.user, 1, self.request)

    async def test_disconnect_does_not_query(self):
        self.request.is_disconnected.return_value = True
        with patch.object(events, 'read_event_version', AsyncMock()) as read:
            with self.assertRaises(events.HTTPException) as caught:
                await events.wait_for_events(self.rid, self.user, 1, self.request)
        self.assertEqual(499, caught.exception.status_code)
        read.assert_not_awaited()

    async def test_real_task_cancellation_releases_admission_slot(self):
        started = asyncio.Event()
        async def waiting(*args):
            started.set()
            await asyncio.Future()
        with patch.object(events, 'rate_limit', AsyncMock()), patch.object(events, 'wait_for_events', waiting):
            task = asyncio.create_task(events.poll_events(self.rid,self.user,1,self.request))
            await started.wait()
            self.assertEqual(1, events._users[self.user.id])
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(0, events._active)
        self.assertEqual({}, events._users)

    async def test_admission_limits_are_fail_fast_and_release(self):
        cfg = SimpleNamespace(monopoly_event_max_polls=2, monopoly_event_user_polls=1)
        with patch.object(events, 'config', cfg):
            with events.poll_slot(1):
                with self.assertRaises(events.HTTPException):
                    with events.poll_slot(1): pass
                with events.poll_slot(2):
                    with self.assertRaises(events.HTTPException):
                        with events.poll_slot(3): pass
        self.assertEqual(0,events._active)

    async def test_sql_is_scalar_unlocked_live_generation_and_session_closes(self):
        active = [0]; statements = []
        @asynccontextmanager
        async def factory():
            active[0] += 1
            async def execute(statement):
                statements.append(statement)
                return SimpleNamespace(one_or_none=lambda: (123,7))
            try: yield SimpleNamespace(execute=execute)
            finally: active[0] -= 1
        with patch.object(events, 'async_session_factory', factory):
            self.assertEqual(7,await events.read_event_version(self.rid,self.user))
            self.assertEqual(7,await events.read_event_version(self.rid,self.user))
        self.assertEqual(0,active[0])
        sql = str(statements[0])
        self.assertNotIn('FOR UPDATE',sql)
        self.assertNotIn('monopoly_rooms.state',sql)
        self.assertIn('monopoly_members.generation = users.account_generation',sql)
        self.assertIn('users.account_generation =',sql)
        self.assertIn('auth_sessions.expires_at > clock_timestamp()',sql)

    async def test_sql_rejects_deleted_user_and_missing_membership(self):
        for row, status in [(None,401),((123,None),403)]:
            @asynccontextmanager
            async def factory():
                yield SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(one_or_none=lambda: row)))
            with patch.object(events,'async_session_factory',factory):
                with self.assertRaises(events.HTTPException) as caught:
                    await events.read_event_version(self.rid,self.user)
                self.assertEqual(status,caught.exception.status_code)

    async def test_wait_reopens_session_and_sleeps_without_transaction(self):
        active=[0]; rows=iter([1,2,2]); clock=[0.0]; opened=[]
        @asynccontextmanager
        async def factory():
            active[0]+=1;opened.append(True)
            try:
                row=(123,next(rows))
                yield SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(one_or_none=lambda:row)))
            finally: active[0]-=1
        async def sleep(delay):
            self.assertEqual(0,active[0])
            clock[0]+=delay
        with patch.object(events,'async_session_factory',factory),patch.object(events,'monotonic',lambda:clock[0]),patch.object(events.asyncio,'sleep',sleep):
            result=await events.wait_for_events(self.rid,self.user,1,self.request)
        self.assertEqual({'event_version':2,'changed':True},result)
        self.assertEqual(3,len(opened))
        self.assertEqual(0,active[0])

    async def test_missing_auth_context_does_not_open_session(self):
        with patch.object(events,'async_session_factory') as factory:
            with self.assertRaises(events.HTTPException) as caught:
                await events.read_event_version(self.rid,SimpleNamespace(id=123))
        self.assertEqual(401,caught.exception.status_code)
        factory.assert_not_called()

    async def test_route_requires_nonnegative_cursor(self):
        route=next(r for r in api.router.routes if r.path=='/monopoly/rooms/{rid}/events')
        self.assertEqual({'GET'},route.methods)
        cursor=next(p for p in route.dependant.query_params if p.name=='cursor')
        self.assertTrue(cursor.required)
        self.assertTrue(any(getattr(m,'ge',None)==0 for m in cursor.field_info.metadata))

    async def test_cancellation_closes_session_in_read(self):
        closed=[]
        @asynccontextmanager
        async def factory():
            try:
                yield SimpleNamespace(execute=AsyncMock(side_effect=asyncio.CancelledError))
            finally: closed.append(True)
        with patch.object(events,'async_session_factory',factory):
            with self.assertRaises(asyncio.CancelledError):
                await events.read_event_version(self.rid,self.user)
        self.assertEqual([True],closed)


class EventMutationTests(unittest.IsolatedAsyncioTestCase):
    fixture = MonopolyAPIReview.fixture

    async def test_chat_advances_only_event_cursor_and_replay_does_not_mutate(self):
        room,member,user=self.fixture()
        db=FakeDB()
        body=api.CommandBody(key=uuid4(),action='chat',text='hello')
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'authenticated_room',AsyncMock(return_value=(room,member))):
            result=await api.command(room.id,body,user,db)
        self.assertEqual(1,room.version)
        self.assertEqual(2,room.event_version)
        self.assertEqual(2,result['event_version'])
        self.assertEqual(2,len(db.added)) # message + UUID command journal in same transaction
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=result)),patch.object(api,'authenticated_room',AsyncMock()) as locked:
            self.assertEqual(result,await api.command(room.id,body,user,db))
        locked.assert_not_awaited()
        self.assertEqual(2,room.event_version)

    async def test_gameplay_advances_both_versions_once(self):
        room,member,user=self.fixture()
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'authenticated_room',AsyncMock(return_value=(room,member))):
            result=await api.command(room.id,api.CommandBody(key=uuid4(),action='ready'),user,FakeDB())
        self.assertEqual((2,2),(room.version,room.event_version))
        self.assertEqual(2,result['event_version'])

    async def test_new_join_advances_versions_but_reconnect_does_not(self):
        room,member,user=self.fixture();room.public=True
        for existing in [None,member]:
            before=(room.version,room.event_version)
            with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'require_room_slot',AsyncMock()),patch.object(api,'authenticated_room',AsyncMock(return_value=(room,existing))):
                result=await api.join_public(room.id,api.CommandBody(key=uuid4(),action='join'),user,FakeDB())
            bump=0 if existing else 1
            self.assertEqual((before[0]+bump,before[1]+bump),(room.version,room.event_version))
            self.assertEqual(room.event_version,result['event_version'])

    async def test_stale_action_changes_neither_state_nor_cursor(self):
        room,member,user=self.fixture()
        from copy import deepcopy
        before=deepcopy(vars(room)); db=FakeDB()
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'authenticated_room',AsyncMock(return_value=(room,member))):
            with self.assertRaises(api.HTTPException):
                await api.command(room.id,api.CommandBody(key=uuid4(),action='ready',version=99),user,db)
        self.assertEqual(before,vars(room))
        self.assertEqual([],db.added)

    async def test_journal_failure_rolls_back_mutation_and_event_in_same_boundary(self):
        room,member,user=self.fixture()
        from copy import deepcopy
        class RollbackDB(FakeDB):
            @asynccontextmanager
            async def begin(self):
                before=deepcopy(vars(room))
                try: yield
                except BaseException:
                    room.__dict__.clear();room.__dict__.update(before);self.added.clear()
                    raise
        db=RollbackDB(); before=deepcopy(vars(room))
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock()),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'authenticated_room',AsyncMock(return_value=(room,member))),patch.object(api,'journal',side_effect=RuntimeError('synthetic commit failure')):
            with self.assertRaises(RuntimeError):
                await api.command(room.id,api.CommandBody(key=uuid4(),action='chat',text='rollback'),user,db)
        self.assertEqual(before,vars(room))
        self.assertEqual([],db.added)


if __name__ == '__main__': unittest.main()
