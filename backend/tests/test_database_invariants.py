"""Opt-in regressions. Never points at DATABASE_URL or a populated database.

Requires COMPANION_ENABLE_DB_TESTS=1 AND COMPANION_TEST_DATABASE_URL referencing
an EMPTY local PostgreSQL database ending in _test. Creates/drops application
metadata only in that deliberately disposable database. Not run in this session.
"""
import asyncio
import hashlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ENABLED = os.environ.get("COMPANION_ENABLE_DB_TESTS") == "1"


@unittest.skipUnless(ENABLED, "Explicit opt-in and empty isolated test DB required")
class DatabaseInvariants(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        url = os.environ.get("COMPANION_TEST_DATABASE_URL", "")
        parts = urlsplit(url)
        if parts.scheme != "postgresql+asyncpg" or parts.hostname not in ("127.0.0.1", "localhost", "postgres-test") or not parts.path.endswith("_test"):
            raise RuntimeError("Refusing database tests without a dedicated local *_test database")
        # Deliberately override possible production configuration before any app import.
        os.environ.update(DATABASE_URL=url, BOT_TOKEN="100000:TEST_ONLY_NOT_A_REAL_TOKEN_1234567890123456789", MINI_APP_URL="https://test.invalid", ALLOWED_ORIGINS='["https://test.invalid"]', ALLOWED_HOSTS='["test.invalid"]')
        from sqlalchemy import text
        from app.db import Base, async_session_factory, engine
        from app.models import AuthSession, Settings, User
        import app.games.models
        from app.games.service import GamesService
        from sqlalchemy.engine import make_url
        if engine.url != make_url(url):
            raise RuntimeError("Refusing test: application engine was initialized with a different database")
        self.Base, self.factory, self.engine = Base, async_session_factory, engine
        self.User, self.Settings, self.AuthSession, self.Service = User, Settings, AuthSession, GamesService
        self.created = False
        self.addAsyncCleanup(self.cleanup_database)
        async with engine.begin() as connection:
            if await connection.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")):
                raise RuntimeError("Refusing to alter a nonempty test database")
            await connection.run_sync(Base.metadata.create_all)
        self.created = True
        self.principal = await self.make_principal(100001)

    async def cleanup_database(self):
        if self.created:
            async with self.engine.begin() as connection:
                await connection.run_sync(self.Base.metadata.drop_all)
        await self.engine.dispose()

    async def make_principal(self, user_id):
        digest = hashlib.sha256(uuid4().bytes).hexdigest()
        async with self.factory() as session:
            row = self.User(id=user_id, name="Test user", active=True)
            session.add(row)
            await session.flush()
            session.add(self.Settings(user_id=user_id))
            session.add(self.AuthSession(digest=digest, user_id=user_id, expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
            await session.commit()
            row.auth_token_hash = digest
            row.auth_account_generation = row.account_generation
            session.expunge(row)
            return row

    async def service_call(self, method, *args, principal=None):
        async with self.factory() as session:
            return await getattr(self.Service(session, principal or self.principal), method)(*args)

    async def test_parallel_same_key_daily_is_exactly_one_credit(self):
        from sqlalchemy import func, select
        from app.games.models import DailyClaim, GameAction, Wallet, WalletLedger
        results = await asyncio.gather(*(self.service_call("daily", "same-daily-key") for _ in range(12)))
        self.assertTrue(all(result == results[0] for result in results))
        async with self.factory() as session:
            self.assertEqual(1200, (await session.get(Wallet, self.principal.id)).balance)
            self.assertEqual(1, await session.scalar(select(func.count()).select_from(DailyClaim)))
            self.assertEqual(1, await session.scalar(select(func.count()).select_from(GameAction)))
            self.assertEqual(1200, await session.scalar(select(func.sum(WalletLedger.amount))))

    async def test_parallel_same_key_start_one_round_and_debit(self):
        from sqlalchemy import func, select
        from app.games.models import GameRound, Wallet, WalletLedger
        from app.games.schemas import StartRound
        body = StartRound(game="mines", bet=100, mines=3, key="same-round-key")
        results = await asyncio.gather(*(self.service_call("start", body) for _ in range(12)))
        self.assertEqual(1, len({result["id"] for result in results}))
        self.assertNotIn("mines", results[0]["state"])
        self.assertIsNone(results[0]["result"])
        async with self.factory() as session:
            self.assertEqual(1, await session.scalar(select(func.count()).select_from(GameRound)))
            self.assertEqual(900, (await session.get(Wallet, self.principal.id)).balance)
            self.assertEqual(900, await session.scalar(select(func.sum(WalletLedger.amount))))

    async def test_changed_payload_same_key_conflicts(self):
        from fastapi import HTTPException
        from app.games.schemas import StartRound
        await self.service_call("start", StartRound(game="mines", bet=10, mines=3, key="fingerprint"))
        with self.assertRaises(HTTPException) as caught:
            await self.service_call("start", StartRound(game="mines", bet=20, mines=3, key="fingerprint"))
        self.assertEqual(409, caught.exception.status_code)
        self.assertEqual("idempotency_mismatch", caught.exception.detail["code"])

    async def test_foreign_round_is_not_disclosed(self):
        from fastapi import HTTPException
        from app.games.schemas import StartRound
        result = await self.service_call("start", StartRound(game="mines", bet=10, key="owner-round"))
        other = await self.make_principal(100002)
        with self.assertRaises(HTTPException) as caught:
            await self.service_call("round", UUID(result["id"]), principal=other)
        self.assertEqual(404, caught.exception.status_code)

    async def test_deleted_recreated_id_cannot_reuse_old_principal(self):
        from fastapi import HTTPException
        from sqlalchemy import delete
        await self.service_call("wallet")
        old = self.principal
        async with self.factory() as session:
            await session.execute(delete(self.User).where(self.User.id == old.id))
            await session.commit()
        new = await self.make_principal(old.id)
        self.assertNotEqual(old.account_generation, new.account_generation)
        with self.assertRaises(HTTPException) as caught:
            await self.service_call("daily", "revoked-intent", principal=old)
        self.assertEqual(401, caught.exception.status_code)
        self.assertEqual(1000, (await self.service_call("wallet", principal=new))["balance"])

    async def test_database_rejects_negative_balance(self):
        from sqlalchemy.exc import IntegrityError
        from app.games.models import Wallet
        await self.service_call("wallet")
        async with self.factory() as session:
            wallet = await session.get(Wallet, self.principal.id)
            wallet.balance = -1
            with self.assertRaises(IntegrityError):
                await session.commit()
            await session.rollback()
        self.assertEqual(1000, (await self.service_call("wallet"))["balance"])


if __name__ == "__main__":
    unittest.main()
