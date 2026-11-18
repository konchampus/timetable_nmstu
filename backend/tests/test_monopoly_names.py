"""Verified Telegram names at room entry; synthetic sessions, no DB or .env."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from pydantic import ValidationError
from test_monopoly_api import api, FakeDB

class TelegramNames(unittest.IsolatedAsyncioTestCase):
    def user(self, name='Анна Петрова'):
        return SimpleNamespace(id=123, account_generation='names-test', name=name)

    def test_server_uses_verified_profile_not_submitted_name(self):
        body=api.CommandBody(key=uuid4(),action='create',nickname='Подмена',use_telegram_name=True)
        self.assertEqual(api.entry_name(body,self.user()),'Анна Петрова')

    def test_custom_nickname_is_explicit_and_scoped_to_room(self):
        user=self.user()
        body=api.CommandBody(key=uuid4(),action='create',nickname='  Капитан  ',use_telegram_name=False)
        self.assertEqual(api.entry_name(body,user),'Капитан')
        self.assertEqual(user.name,'Анна Петрова')

    def test_unicode_whitespace_long_empty_and_missing_profile(self):
        body=api.CommandBody(key=uuid4(),action='create',use_telegram_name=True)
        self.assertEqual(api.entry_name(body,self.user('  Анна\n  Петрова  ')),'Анна Петрова')
        self.assertEqual(len(api.entry_name(body,self.user('я'*60))),30)
        for user in [self.user('  '),SimpleNamespace(),self.user(None)]:
            self.assertEqual(api.entry_name(body,user),'Игрок')

    def test_new_flag_is_strict_and_changes_fingerprint(self):
        for value in [1,'true',None]:
            with self.assertRaises(ValidationError):api.CommandBody(key=uuid4(),action='create',use_telegram_name=value)
        body=api.CommandBody(key=uuid4(),action='create')
        self.assertNotEqual(api.fingerprint(body,'rooms'),api.fingerprint(body.model_copy(update={'use_telegram_name':True}),'rooms'))
        self.assertEqual(api.fingerprint(body,'rooms'),api.fingerprint(api.CommandBody(**body.model_dump(),), 'rooms'))

    async def test_create_uses_authenticated_name_without_client_nickname(self):
        user=self.user();db=FakeDB((0,));db.flush=AsyncMock()
        with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock(return_value=user)),patch.object(api,'replay',AsyncMock(return_value=None)):
            result=await api.enter(api.CommandBody(key=uuid4(),action='create',use_telegram_name=True),user,db)
        self.assertEqual(result['state']['players'][0]['name'],user.name)

    async def test_private_and_public_join_resolve_each_own_profile(self):
        for private in [True,False]:
            user=self.user('Борис Сидоров');host=str(uuid4())
            state=api.rules.new_state(host,'Чужое имя')
            room=SimpleNamespace(id=uuid4(),code='a'*20,title='Names',public=True,capacity=4,status='lobby',version=1,event_version=1,host=host,state=state,deadline=None)
            db=FakeDB((0,),room=room)
            body=api.CommandBody(key=uuid4(),action='join',code='a'*20,use_telegram_name=True)
            with patch.object(api,'rate_limit',AsyncMock()),patch.object(api,'lock_authenticated_user',AsyncMock(return_value=user)),patch.object(api,'replay',AsyncMock(return_value=None)),patch.object(api,'membership',AsyncMock(return_value=None)):
                result=await api.enter(body,user,db) if private else await api.join_public(room.id,body,user,db)
            self.assertEqual(result['state']['players'][-1]['name'],'Борис Сидоров')
            self.assertEqual(result['state']['players'][0]['name'],'Чужое имя')
