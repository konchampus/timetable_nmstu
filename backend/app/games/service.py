"""All economy changes share one DB transaction and one lock order.

No network or process-local synchronization occurs inside these transactions.
User -> Wallet -> Round -> Catch ordering also serializes account deletion.
"""
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import TypeVar
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import BigInteger, cast, func, literal, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Settings, User
from app.security import lock_authenticated_user
from . import engine
from .models import DailyClaim, FishingCatch, GameAction, GameRound, Wallet, WalletLedger
from .schemas import RoundAction, StartRound

LOCAL_ZONE = ZoneInfo("Asia/Yekaterinburg")
T = TypeVar("T")


def fail(status: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


@dataclass
class Context:
    wallet: Wallet
    now: datetime
    expired: set[UUID] = field(default_factory=set)


class GamesService:
    def __init__(self, session: AsyncSession, principal: User):
        self.session = session
        self.principal = principal
        self.user_id = principal.id

    async def _transaction(self, work: Callable[[Context], Awaitable[T]]) -> T:
        for attempt in range(3):
            try:
                # The service owns the transaction, not the request/auth dependency.
                async with self.session.begin():
                    await self.session.execute(text("SET LOCAL lock_timeout = '3s'"))
                    await self.session.execute(text("SET LOCAL statement_timeout = '10s'"))
                    # Revalidate the original token and account generation under the
                    # User lock: a deleted/recreated Telegram ID is not the old account.
                    await lock_authenticated_user(self.session, self.principal)
                    # PostgreSQL's clock is authoritative, not client or API-worker time.
                    now = await self.session.scalar(select(func.clock_timestamp()))
                    wallet = await self.session.scalar(select(Wallet).where(Wallet.user_id == self.user_id).with_for_update())
                    if wallet is None:
                        wallet = Wallet(user_id=self.user_id, balance=0, rod_level=1, collected_species=[], record_grams=0)
                        self.session.add(wallet)
                        await self.session.flush()
                        self._money(wallet, 1000, "start_bonus", now)
                    result = await work(Context(wallet, now))
                    await self.session.flush()
                    # Explicit service commit: response and journal are durable together.
                    await self.session.commit()
                return result
            except DBAPIError as error:
                code = getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)
                if code in ("40001", "40P01"):
                    if attempt < 2:
                        await asyncio.sleep(.025 * (attempt + 1))
                        continue
                    fail(503, "transaction_retry", "Повторите запрос с прежним ключом")
                if code == "55P03":
                    fail(409, "busy", "Операция занята; повторите запрос с прежним ключом")
                if code == "57014":
                    fail(503, "transaction_timeout", "Время операции истекло; повторите запрос с прежним ключом")
                raise
        raise RuntimeError("Unreachable transaction retry state")

    def _money(self, wallet: Wallet, amount: int, event: str, now: datetime, round_id: UUID | None = None) -> None:
        if not amount:
            return
        if wallet.balance + amount < 0:
            fail(409, "insufficient_balance", "Недостаточно игровых очков")
        wallet.balance += amount
        self.session.add(WalletLedger(user_id=self.user_id, round_id=round_id, event=event, amount=amount, balance_after=wallet.balance, created_at=now))

    async def _mutate(self, operation: str, body: dict, work: Callable[[Context], Awaitable[dict]]) -> dict:
        parameters = {k: v for k, v in body.items() if k != "key"}
        fingerprint = sha256(json.dumps({"operation": operation, "parameters": parameters}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

        async def execute(context: Context) -> dict:
            previous = await self.session.scalar(select(GameAction).where(GameAction.user_id == self.user_id, GameAction.key == body["key"]))
            if previous is not None:
                if previous.operation != operation or previous.fingerprint != fingerprint:
                    fail(409, "idempotency_mismatch", "Ключ уже использован с другими параметрами")
                return previous.response
            last = context.wallet.last_mutation_at
            if last is not None and context.now - last < timedelta(milliseconds=250):
                fail(429, "mutation_cooldown", "Подождите перед следующим действием")
            await self._expire_due(context)
            result = await work(context)
            context.wallet.last_mutation_at = context.now
            self.session.add(GameAction(user_id=self.user_id, key=body["key"], operation=operation,
                                        fingerprint=fingerprint, response=result, created_at=context.now))
            return result

        return await self._transaction(execute)

    @staticmethod
    def _round_response(round_: GameRound, wallet: Wallet) -> dict:
        # Explicit allowlist: never serialize an ORM object or secret_state.
        return {"id": str(round_.id), "game": round_.game, "status": round_.status, "bet": round_.bet,
                "payout": round_.payout, "balance": wallet.balance, "version": round_.version, "rules_version": round_.rules_version,
                "created_at": round_.created_at.isoformat(),
                "available_at": round_.available_at.isoformat() if round_.available_at else None,
                "state": round_.public_state, "result": round_.result if round_.status != "active" else None}

    def _settle(self, context: Context, round_: GameRound, amount: int, result: dict, *, expired: bool = False) -> None:
        if round_.status != "active":
            fail(409, "round_closed", "Раунд уже завершён")
        round_.payout = amount
        round_.status = "expired" if expired else "won" if amount > round_.bet else "push" if amount == round_.bet else "lost"
        round_.result = {**result, "timeout": True} if expired else result
        self._money(context.wallet, amount, f"round:{round_.id}:payout", context.now, round_.id)
        # A terminal result no longer needs the hidden deck / future catch.
        round_.secret_state = {}

    def _stand(self, context: Context, round_: GameRound, *, expired: bool = False) -> None:
        # JSONB mutations must replace the outer object to be tracked by SQLAlchemy.
        secret = {"player": list(round_.secret_state["player"]), "dealer": list(round_.secret_state["dealer"]), "deck": list(round_.secret_state["deck"])}
        outcome = engine.blackjack_finish(secret)
        round_.public_state = engine.blackjack_public(secret, True)
        self._settle(context, round_, engine.payout(round_.bet, outcome.multiplier), outcome.result, expired=expired)

    def _cashout(self, context: Context, round_: GameRound, *, expired: bool = False) -> None:
        state = round_.public_state
        multiplier = engine.mines_multiplier(state["mines_count"], len(state["cells"]))
        self._settle(context, round_, engine.payout(round_.bet, multiplier), {"mines": list(round_.secret_state["mines"])}, expired=expired)

    async def _expire_due(self, context: Context) -> None:
        rounds = (await self.session.scalars(select(GameRound).where(GameRound.user_id == self.user_id, GameRound.status == "active", GameRound.expires_at <= context.now).order_by(GameRound.id).with_for_update())).all()
        for round_ in rounds:
            if round_.game == "blackjack":
                self._stand(context, round_, expired=True)
            elif round_.game == "mines":
                self._cashout(context, round_, expired=True)
            else:
                raise RuntimeError("Unexpected expiring game")
            round_.version += 1
            context.expired.add(round_.id)
        # Release the partial unique active slot before a new round is inserted.
        if rounds:
            await self.session.flush()

    async def _inventory_value(self) -> int:
        return int(await self.session.scalar(select(func.coalesce(func.sum(FishingCatch.value), 0)).where(FishingCatch.user_id == self.user_id, FishingCatch.sold_at.is_(None))) or 0)

    async def wallet(self) -> dict:
        async def read(context: Context) -> dict:
            await self._expire_due(context)
            day = context.now.astimezone(LOCAL_ZONE).date()
            claim = await self.session.get(DailyClaim, (self.user_id, day))
            return {"balance": context.wallet.balance, "inventory_value": await self._inventory_value(),
                    "daily_available": claim is None, "rod_level": context.wallet.rod_level}
        return await self._transaction(read)

    async def ledger(self, *, limit: int = 50, offset: int = 0) -> dict:
        async def read(context: Context) -> dict:
            await self._expire_due(context)
            rows = (await self.session.scalars(select(WalletLedger).where(
                WalletLedger.user_id == self.user_id,
            ).order_by(WalletLedger.created_at.desc(), WalletLedger.id.desc()).offset(offset).limit(limit))).all()
            def kind(event: str) -> str:
                if event == "start_bonus":
                    return "start_bonus"
                if event.startswith("daily:"):
                    return "daily"
                if event.startswith("fishing:sale:"):
                    return "fishing_sale"
                if event.startswith("rod:level:"):
                    return "rod_upgrade"
                return "bet" if event.endswith(":bet") else "payout"
            # Exclude raw event strings: sale events contain private idempotency keys.
            return {"items": [{"id": str(row.id), "round_id": str(row.round_id) if row.round_id else None,
                               "kind": kind(row.event), "amount": row.amount,
                               "balance_after": row.balance_after, "created_at": row.created_at.isoformat()} for row in rows]}
        return await self._transaction(read)

    async def daily(self, key: str) -> dict:
        async def claim(context: Context) -> dict:
            day = context.now.astimezone(LOCAL_ZONE).date()
            if await self.session.get(DailyClaim, (self.user_id, day)) is not None:
                fail(409, "daily_claimed", "Бонус за этот день уже получен")
            self.session.add(DailyClaim(user_id=self.user_id, day=day, created_at=context.now))
            self._money(context.wallet, 200, f"daily:{day.isoformat()}", context.now)
            return {"balance": context.wallet.balance, "reward": 200}
        return await self._mutate("daily", {"key": key}, claim)

    async def upgrade(self, key: str) -> dict:
        async def improve(context: Context) -> dict:
            level = context.wallet.rod_level
            if level >= 5:
                fail(409, "rod_maximum", "Удочка уже максимального уровня")
            self._money(context.wallet, -engine.ROD_COST[level - 1], f"rod:level:{level + 1}", context.now)
            context.wallet.rod_level += 1
            return {"balance": context.wallet.balance, "rod_level": context.wallet.rod_level}
        return await self._mutate("fishing/upgrade", {"key": key}, improve)

    async def sell(self, key: str) -> dict:
        async def sale(context: Context) -> dict:
            # One SQL statement updates the entire inventory, not N ORM rows.
            sold = update(FishingCatch).where(FishingCatch.user_id == self.user_id, FishingCatch.sold_at.is_(None)).values(sold_at=context.now).returning(FishingCatch.value).cte("sold_fish")
            totals = (await self.session.execute(select(func.count().label("quantity"), func.coalesce(func.sum(sold.c.value), 0).label("total")).select_from(sold))).one()
            self._money(context.wallet, int(totals.total), f"fishing:sale:{key}", context.now)
            return {"balance": context.wallet.balance, "sold": totals.quantity}
        return await self._mutate("fishing/sell", {"key": key}, sale)

    async def inventory(self) -> dict:
        async def read(context: Context) -> dict:
            await self._expire_due(context)
            statement = select(FishingCatch.species, FishingCatch.rarity, FishingCatch.value,
                               func.count().label("count"), func.sum(FishingCatch.weight_grams).label("grams")).where(FishingCatch.user_id == self.user_id, FishingCatch.sold_at.is_(None)).group_by(FishingCatch.species, FishingCatch.rarity, FishingCatch.value).order_by(FishingCatch.value)
            rows = (await self.session.execute(statement)).mappings().all()
            level = context.wallet.rod_level
            return {"items": [{"species": r["species"], "rarity": r["rarity"], "count": r["count"], "value": r["value"], "weight": r["grams"] / 1000} for r in rows],
                    "rod_level": level, "upgrade_cost": engine.ROD_COST[level - 1] if level < 5 else None,
                    "max_rod_level": 5, "collection": list(context.wallet.collected_species), "record_weight": context.wallet.record_grams / 1000}
        return await self._transaction(read)

    async def start(self, body: StartRound) -> dict:
        async def create(context: Context) -> dict:
            active = await self.session.scalar(select(GameRound.id).where(GameRound.user_id == self.user_id, GameRound.game == body.game, GameRound.status == "active"))
            if active is not None:
                fail(409, "active_round", "Сначала завершите активный раунд этой игры")
            round_ = GameRound(id=uuid4(), user_id=self.user_id, game=body.game, status="active", bet=body.bet,
                               payout=0, version=1, rules_version=engine.RULES_VERSION, created_at=context.now,
                               public_state={}, secret_state={})
            self.session.add(round_)
            # Ensure the round exists before inserting its ledger foreign key.
            await self.session.flush()
            self._money(context.wallet, -body.bet, f"round:{round_.id}:bet", context.now, round_.id)
            if body.game == "fishing":
                level = context.wallet.rod_level
                round_.public_state = {"rod_level": level}
                round_.secret_state = engine.fishing_result(level)
                round_.available_at = context.now + timedelta(seconds=engine.ROD_WAIT[level - 1])
            elif body.game == "mines":
                count = body.mines if body.mines is not None else 5
                round_.public_state = {"cells": [], "values": {}, "mines_count": count, "multiplier": 1.0}
                round_.secret_state = {"mines": sorted(engine.RNG.sample(range(25), count))}
                round_.expires_at = context.now + timedelta(hours=24)
            elif body.game == "blackjack":
                secret = engine.blackjack_start()
                round_.secret_state = secret
                round_.public_state = engine.blackjack_public(secret, False)
                round_.expires_at = context.now + timedelta(hours=24)
                if engine.blackjack_natural(secret):
                    self._stand(context, round_)
            else:
                round_.public_state = {"choice": body.choice} if body.choice is not None else {}
                outcome = engine.instant(body.game, body.choice)
                self._settle(context, round_, engine.payout(body.bet, outcome.multiplier), outcome.result)
            return self._round_response(round_, context.wallet)
        return await self._mutate("rounds", body.model_dump(), create)

    async def _owned_round(self, round_id: UUID) -> GameRound:
        round_ = await self.session.scalar(select(GameRound).where(GameRound.id == round_id, GameRound.user_id == self.user_id).with_for_update())
        if round_ is None:
            fail(404, "round_missing", "Раунд не найден")
        return round_

    async def action(self, round_id: UUID, body: RoundAction) -> dict:
        async def act(context: Context) -> dict:
            round_ = await self._owned_round(round_id)
            if round_id in context.expired:
                return self._round_response(round_, context.wallet)
            if round_.version != body.version:
                fail(409, "version_conflict", "Раунд изменился; обновите состояние")
            if round_.status != "active":
                fail(409, "round_closed", "Раунд уже завершён")
            allowed = {"blackjack": {"hit", "stand"}, "mines": {"reveal", "cashout"}, "fishing": {"collect"}}
            if body.action not in allowed.get(round_.game, set()):
                fail(422, "invalid_action", "Действие недоступно для этой игры")
            if round_.game == "blackjack":
                if body.action == "hit":
                    secret = {k: list(v) for k, v in round_.secret_state.items()}
                    secret["player"].append(secret["deck"].pop())
                    round_.secret_state = secret
                    round_.public_state = engine.blackjack_public(secret, False)
                    if engine.hand_total(secret["player"]) >= 21:
                        self._stand(context, round_)
                else:
                    self._stand(context, round_)
            elif round_.game == "mines":
                if body.action == "cashout":
                    self._cashout(context, round_)
                else:
                    self._reveal(context, round_, body.cell)
            else:
                self._collect(context, round_)
            round_.version += 1
            return self._round_response(round_, context.wallet)
        return await self._mutate(f"rounds/{round_id}/actions", body.model_dump(), act)

    def _reveal(self, context: Context, round_: GameRound, cell: int | None) -> None:
        if cell is None:
            fail(422, "cell_required", "Укажите клетку")
        old = round_.public_state
        if cell in old["cells"]:
            fail(409, "cell_revealed", "Клетка уже открыта")
        positions = list(round_.secret_state["mines"])
        if cell in positions:
            self._settle(context, round_, 0, {"mines": positions, "hit": cell})
            return
        cells = [*old["cells"], cell]
        values = {**old["values"], str(cell): engine.adjacent_mines(cell, positions)}
        multiplier = engine.mines_multiplier(old["mines_count"], len(cells))
        round_.public_state = {"cells": cells, "values": values, "mines_count": old["mines_count"], "multiplier": float(multiplier)}
        if len(cells) == 25 - old["mines_count"]:
            self._cashout(context, round_)

    def _collect(self, context: Context, round_: GameRound) -> None:
        if round_.available_at is None or context.now < round_.available_at:
            fail(409, "fishing_not_ready", "Улов ещё не готов")
        fish = round_.secret_state
        self.session.add(FishingCatch(user_id=self.user_id, round_id=round_.id, species=fish["species"], rarity=fish["rarity"], value=fish["value"], weight_grams=fish["weight_grams"], caught_at=context.now))
        wallet = context.wallet
        wallet.collected_species = sorted(set(wallet.collected_species) | {fish["species"]})
        wallet.record_grams = max(wallet.record_grams, fish["weight_grams"])
        round_.status = "caught"
        round_.result = {"species": fish["species"], "rarity": fish["rarity"], "weight": fish["weight_grams"] / 1000, "value": fish["value"]}
        round_.secret_state = {}

    async def round(self, round_id: UUID) -> dict:
        async def read(context: Context) -> dict:
            await self._expire_due(context)
            return self._round_response(await self._owned_round(round_id), context.wallet)
        return await self._transaction(read)

    async def rounds(self, *, active: bool = False, limit: int = 50, offset: int = 0) -> dict:
        async def read(context: Context) -> dict:
            await self._expire_due(context)
            statement = select(GameRound).where(GameRound.user_id == self.user_id)
            if active:
                statement = statement.where(GameRound.status == "active")
            statement = statement.order_by(GameRound.created_at.desc(), GameRound.id.desc()).offset(offset).limit(limit)
            rows = (await self.session.scalars(statement)).all()
            return {"items": [self._round_response(row, context.wallet) for row in rows]}
        return await self._transaction(read)

    async def leaderboard(self, kind: str) -> dict:
        async def read(context: Context) -> dict:
            await self._expire_due(context)
            await self.session.flush()
            inventory = select(FishingCatch.user_id, func.sum(FishingCatch.value).label("value")).where(FishingCatch.sold_at.is_(None)).group_by(FishingCatch.user_id).subquery()
            if kind == "wealth":
                score = Wallet.balance + func.coalesce(inventory.c.value, 0)
                personal_score = context.wallet.balance + await self._inventory_value()
            else:
                score = cast(func.jsonb_array_length(Wallet.collected_species), BigInteger) * 100000 + Wallet.record_grams
                personal_score = len(context.wallet.collected_species) * 100000 + context.wallet.record_grams
            # Rank only consented users; SQL window avoids loading all user rows.
            ranked = select(Wallet.user_id.label("owner"), Settings.nickname.label("nickname"), score.label("score"),
                            func.dense_rank().over(order_by=score.desc()).label("rank")).join(User, User.id == Wallet.user_id).join(Settings, Settings.user_id == Wallet.user_id).outerjoin(inventory, inventory.c.user_id == Wallet.user_id).where(User.active.is_(True), Settings.leaderboard_visible.is_(True), func.length(func.trim(Settings.nickname)) > 0).subquery()
            # Bound even enormous tie groups; both branches use one MVCC snapshot.
            top = select(ranked).order_by(ranked.c.rank, ranked.c.owner).limit(100).cte("game_top")
            public_rows = select(top.c.owner, top.c.nickname, top.c.score, top.c.rank, literal(False).label("is_self"))
            personal = select(ranked.c.owner, ranked.c.nickname, ranked.c.score, ranked.c.rank, literal(True).label("is_self")).where(ranked.c.owner == self.user_id)
            rows = (await self.session.execute(public_rows.union_all(personal))).all()
            own_rank = next((r.rank for r in rows if r.is_self), None)
            return {"items": [{"rank": r.rank, "nickname": r.nickname, "score": int(r.score)} for r in rows if not r.is_self],
                    "self": {"rank": own_rank, "score": personal_score}}
        return await self._transaction(read)
