"""Offline quota/protocol regressions: no database, network, or production configuration.

Service tests substitute transaction/session boundaries, not PostgreSQL locking.
Run under synthetic environment configuration (same as other backend core tests).
"""
import ast
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from app.games import engine, fishing_play, fishing_world, limits
from app.games.schemas import FishingLimits, InventoryResponse, StartRound


def quota(**values):
    return SimpleNamespace(**({"regular_attempts": 0, "regular_catches": 0, "boss_attempts": 0,
                              "sport_rounds": 0, "claimed_bosses": []} | values))


class ProgressionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 16, 18, 59, 50, tzinfo=timezone.utc)

    def assert_rejected(self, code, callback, *args, **kwargs):
        with self.assertRaises(HTTPException) as caught:
            callback(*args, **kwargs)
        self.assertEqual(429, caught.exception.status_code)
        self.assertEqual(code, caught.exception.detail["code"])

    def test_quotas_have_independent_attempt_and_success_caps(self):
        for values, code in (({"regular_attempts": 25}, "fishing_attempt_daily_limit"),
                             ({"regular_catches": 10}, "fishing_catch_daily_limit")):
            self.assert_rejected(code, limits.check_cast, quota(**values), self.now, None, None)
            limits.check_cast(quota(**values), self.now, None, "old_carp")
        self.assert_rejected("boss_daily_limit", limits.check_cast, quota(boss_attempts=3), self.now, None, "old_carp")
        limits.check_cast(quota(boss_attempts=3), self.now, None, None)
        limits.check_cast(quota(regular_attempts=24, regular_catches=9), self.now, None, None)

    def test_all_bosses_share_attempt_cap_and_claim_once_per_id(self):
        q = quota(boss_attempts=3)
        for boss in fishing_world.BOSSES.values():
            self.assert_rejected("boss_daily_limit", limits.check_cast, q, self.now, None, boss["id"])
        q = quota()
        limits.claim_catch(q, "old_carp")
        self.assertEqual(["old_carp"], q.claimed_bosses)
        self.assertEqual(0, q.regular_catches)
        self.assert_rejected("boss_claimed", limits.claim_catch, q, "old_carp")
        self.assert_rejected("boss_claimed", limits.check_cast, q, self.now, None, "old_carp")
        limits.check_cast(q, self.now, None, "loop_guardian")

    def test_success_claim_only_and_old_active_round_exception(self):
        q = quota(regular_attempts=24, regular_catches=9)
        limits.claim_catch(q, None)
        self.assertEqual(10, q.regular_catches)
        self.assertEqual(24, q.regular_attempts)
        self.assert_rejected("fishing_catch_daily_limit", limits.claim_catch, q, None)
        limits.claim_catch(q, None, grandfathered=True)
        self.assertEqual(11, q.regular_catches)
        self.assertEqual(0, limits.public_limits(q, self.now, None)["regular_catches_remaining"])

    def test_cast_cooldown_exact_boundary_and_across_midnight(self):
        last = self.now - timedelta(seconds=44, microseconds=999999)
        for boss_id in (None, "old_carp", "loop_guardian"):
            self.assert_rejected("fishing_cooldown", limits.check_cast, quota(), self.now, last, boss_id)
            limits.check_cast(quota(), self.now, self.now - timedelta(seconds=45), boss_id)
        after_midnight = self.now + timedelta(seconds=20)
        self.assert_rejected("fishing_cooldown", limits.check_cast, quota(), after_midnight, self.now, None)

    def test_local_day_and_public_schema_are_server_time_based(self):
        start, end = limits.day_bounds(self.now)
        self.assertEqual("2026-11-16T00:00:00+05:00", start.isoformat())
        self.assertEqual("2026-11-17T00:00:00+05:00", end.isoformat())
        self.assertEqual(17, limits.day_bounds(self.now + timedelta(seconds=10))[0].day)
        result = limits.public_limits(quota(), self.now, self.now - timedelta(seconds=5))
        dto = FishingLimits(**result)
        self.assertEqual(25, dto.regular_attempts_remaining)
        self.assertEqual(10, dto.regular_catches_remaining)
        self.assertEqual(3, dto.boss_attempts_remaining)
        self.assertEqual(40, dto.sport_rounds_remaining)
        self.assertEqual(self.now.isoformat(), dto.server_now)
        self.assertEqual((self.now + timedelta(seconds=40)).isoformat(), dto.next_cast_at)
        self.assertIsNone(limits.public_limits(quota(), self.now, self.now - timedelta(seconds=45))["next_cast_at"])
        self.assertIsNone(limits.public_limits(quota(), self.now, None)["next_cast_at"])

    def test_sports_cap_is_shared_not_per_game(self):
        q = quota(sport_rounds=39)
        limits.check_sport(q)
        q.sport_rounds += 1
        self.assert_rejected("sports_daily_limit", limits.check_sport, q)

    def test_carp_pool_boss_contract_and_seven_species(self):
        loc = fishing_world.LOCATIONS["carp"]
        self.assertEqual((15, 25, 38, 10, 8, 3, 1), loc["weights"])
        self.assertEqual(Fraction(5, 4), loc["value_multiplier"])
        self.assertEqual(("Пруд Карпа", 2, "carp"), (loc["title"], loc["min_rod_level"], loc["theme"]))
        expected = {
            "carp": ("old_carp", "Старый Карп", 1, 2, "Карп", 500),
            "river": ("loop_guardian", "Страж петли", 1, 3, "Щука", 750),
            "mountain": ("deep_host", "Хозяин глубины", 2, 4, "Сом", 1200),
            "golden": ("commit_keeper", "Хранитель коммита", 3, 5, "Золотой карп", 1800),
        }
        for location, values in expected.items():
            boss = fishing_world.BOSSES[location]
            self.assertEqual(values, tuple(boss[key] for key in ("id", "title", "tier", "min_rod_level", "reward_species", "reward_value")))
        world = fishing_world.public_world(2, engine.FISH, engine.FISH_WEIGHTS, "carp", "angler")
        dto = InventoryResponse(items=[], rod_level=2, upgrade_cost=750, collection=[], record_weight=0,
                                limits=limits.public_limits(quota(), self.now, None), **world)
        self.assertEqual(7, len(dto.species))
        self.assertEqual(5, len(dto.locations))
        self.assertIsNone(next(loc for loc in dto.locations if loc.id == "shore").boss)
        carp = next(loc for loc in dto.locations if loc.id == "carp")
        self.assertEqual("old_carp", carp.boss.id)
        self.assertEqual(0.38, next(fish.probability for fish in carp.fish if fish.species == "Карп"))
        self.assertNotIn("Старый Карп", [item.name for item in dto.species])
        self.assertAlmostEqual(1, sum(fish.probability for fish in carp.fish))

    def test_new_mode_is_opt_in_and_client_cannot_supply_rewards(self):
        StartRound(key="legacy", game="fishing", bet=0)
        for mode in (None, "regular", "boss"):
            StartRound(key="v1", game="fishing", bet=0, gameplay_version=1, location="carp", fishing_mode=mode)
        for invalid in ({"game": "fishing", "bet": 0, "fishing_mode": "boss"},
                        {"game": "darts", "bet": 10, "gameplay_version": 1, "fishing_mode": "regular"},
                        {"game": "fishing", "bet": 0, "gameplay_version": 1, "boss_id": "old_carp"},
                        {"game": "fishing", "bet": 0, "gameplay_version": 1, "boss_tier": 0},
                        {"game": "fishing", "bet": 0, "gameplay_version": 1, "reward_value": 99999},
                        {"game": "fishing", "bet": 0, "gameplay_version": 1, "fishing_mode": "other"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                StartRound(key="invalid", **invalid)

    def test_boss_tiers_change_only_pull_and_progress_formula(self):
        for tier in range(4):
            for wave in range(4):
                for held in (True, False):
                    for level in range(1, 6):
                        c = {"rod_level": level, "surge": wave * 16, "boss_tier": tier}
                        old = {"tension": 45, "progress": 100, "slack": 0, "status": "fighting", "reason": ""}
                        result = fishing_play.step(old, c, 1, held)
                        self.assertEqual(45 + (2 + (2, 4, 1, 3)[wave] + tier if held else -6), result["tension"])
                        self.assertEqual(100 + (10 + level - 2 * tier if held else -3), result["progress"])
                        zero = fishing_play.step(old, {"rod_level": level, "surge": wave * 16}, 1, held)
                        if tier == 0:
                            self.assertEqual(zero, result)
        self.assertEqual(600, fishing_play.MAX_TICKS)

    def test_each_boss_is_winnable_with_existing_tick_event_bounds(self):
        for boss in fishing_world.BOSSES.values():
            challenge = {"rod_level": boss["min_rod_level"], "surge": 0, "bite_tick": 90, "shoal_x": 0,
                         "boss_tier": boss["tier"]}
            state, held, events = fishing_play.initial(), False, []
            hook = fishing_play.bite_tick(challenge, 0)
            for tick in range(hook + 1, 601):
                new_held = True if state["tension"] <= 35 or tick == hook + 1 else False if state["tension"] >= 65 else held
                if held != new_held:
                    events.append({"tick": tick, "held": new_held})
                    held = new_held
                state = fishing_play.step(state, challenge, tick - hook, held)
                if state["status"] != "fighting":
                    break
            self.assertEqual("caught", state["status"], boss["id"])
            self.assertLessEqual(len(events), 128)
            proof = {"cast_x": 0, "cast_tick": 0, "hook_tick": hook, "end_tick": tick, "events": events}
            self.assertEqual(state, fishing_play.replay(challenge, proof))


class ProgressionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Import lazily so pure policy tests have no app/config dependencies.
        from app.games.service import Context, GamesService
        self.now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
        self.wallet = SimpleNamespace(balance=1000, rod_level=5, fishing_location="shore", fishing_skin="angler",
                                      collected_species=[], record_grams=0, last_mutation_at=None)
        self.context = Context(self.wallet, self.now)
        self.session = MagicMock()
        self.session.scalar = AsyncMock(return_value=None)
        self.session.flush = AsyncMock()
        self.service = GamesService(self.session, SimpleNamespace(id=100001))
        self.q = quota()
        self.service._quota = AsyncMock(return_value=self.q)
        self.service._last_cast = AsyncMock(return_value=None)
        self.service._expire_due = AsyncMock()
        async def transaction(work):
            return await work(self.context)
        self.service._transaction = AsyncMock(side_effect=transaction)

    def use_create_callback(self):
        async def mutate(operation, body, work):
            return await work(self.context)
        self.service._mutate = AsyncMock(side_effect=mutate)

    async def test_legacy_and_regular_starts_consume_same_quota(self):
        self.use_create_callback()
        await self.service.start(StartRound(key="old", game="fishing", bet=0))
        self.assertEqual(1, self.q.regular_attempts)
        legacy = next(call.args[0] for call in self.session.add.call_args_list if hasattr(call.args[0], "public_state"))
        self.assertEqual(1, legacy.public_state["quota_policy_version"])
        self.assertNotIn("gameplay_version", legacy.public_state)
        await self.service.start(StartRound(key="new", game="fishing", bet=0, gameplay_version=1, location="carp"))
        self.assertEqual(2, self.q.regular_attempts)
        self.assertEqual(0, self.q.regular_catches)
        self.assertEqual(0, self.q.boss_attempts)

    async def test_global_legacy_cap_rejects_before_round_is_added(self):
        self.use_create_callback()
        self.q.regular_attempts = 25
        for version in (None, 1):
            with self.assertRaises(HTTPException) as caught:
                await self.service.start(StartRound(key="cap", game="fishing", bet=0, gameplay_version=version))
            self.assertEqual("fishing_attempt_daily_limit", caught.exception.detail["code"])
        self.session.add.assert_not_called()

    async def test_boss_reward_is_server_derived_one_catch_no_wallet_payout(self):
        from app.games.models import FishingCatch, GameRound, WalletLedger
        self.use_create_callback()
        start = await self.service.start(StartRound(key="boss", game="fishing", bet=0, gameplay_version=1,
                                                   fishing_mode="boss", location="carp"))
        self.assertEqual(("old_carp", "Старый Карп", 1, "boss"), tuple(start["state"][key] for key in ("boss_id", "boss_title", "boss_tier", "fishing_mode")))
        self.assertIsNone(start["result"])
        self.assertNotIn("species", start["state"])
        row = next(call.args[0] for call in self.session.add.call_args_list if isinstance(call.args[0], GameRound))
        self.assertEqual(1, self.q.boss_attempts)
        self.assertEqual(0, self.q.regular_attempts)
        await self.service._collect(self.context, row, gameplay_verified=True)
        catches = [call.args[0] for call in self.session.add.call_args_list if isinstance(call.args[0], FishingCatch)]
        self.assertEqual(1, len(catches))
        self.assertEqual(("Карп", 500), (catches[0].species, catches[0].value))
        self.assertEqual(["Карп"], self.wallet.collected_species)
        self.assertEqual(["old_carp"], self.q.claimed_bosses)
        self.assertEqual(0, self.q.regular_catches)
        self.assertEqual(1000, self.wallet.balance)
        self.assertFalse(any(isinstance(call.args[0], WalletLedger) for call in self.session.add.call_args_list))

    async def test_boss_levels_and_location_validated_by_server(self):
        self.use_create_callback()
        for location, level, code in (("carp", 1, "boss_locked"), ("river", 2, "boss_locked"),
                                      ("mountain", 3, "boss_locked"), ("golden", 4, "boss_locked"),
                                      ("shore", 5, "boss_unavailable")):
            self.wallet.rod_level = level
            with self.assertRaises(HTTPException) as caught:
                await self.service.start(StartRound(key="locked", game="fishing", bet=0, gameplay_version=1,
                                                   location=location, fishing_mode="boss"))
            self.assertEqual(code, caught.exception.detail["code"])
        self.assertEqual(0, self.q.boss_attempts)
        self.session.add.assert_not_called()

    async def test_all_four_skill_games_share_counter_but_legacy_sports_do_not(self):
        self.use_create_callback()
        for game in ("darts", "bowling", "basketball", "football"):
            await self.service.start(StartRound(key=game, game=game, bet=10, gameplay_version=1))
        self.assertEqual(4, self.q.sport_rounds)
        self.q.sport_rounds = 40
        for game in ("darts", "bowling", "basketball", "football"):
            with self.assertRaises(HTTPException) as caught:
                await self.service.start(StartRound(key=game, game=game, bet=10, gameplay_version=1))
            self.assertEqual("sports_daily_limit", caught.exception.detail["code"])
        await self.service.start(StartRound(key="legacy-sport", game="darts", bet=10))
        self.assertEqual(40, self.q.sport_rounds)

    async def test_null_new_fields_preserve_old_fingerprint_and_replay_skips_counters(self):
        from app.games.models import GameAction
        old_body = {"key": "original", "game": "fishing", "bet": 0, "choice": None, "mines": None}
        fingerprint = hashlib.sha256(json.dumps({"operation": "rounds", "parameters": {key: value for key, value in old_body.items() if key != "key"}}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        previous = GameAction(operation="rounds", fingerprint=fingerprint, response={"id": "persisted", "balance": 1000})
        self.session.scalar.return_value = previous
        work = AsyncMock()
        current = StartRound(**old_body).model_dump()
        self.assertIn("fishing_mode", current)
        self.assertIsNone(current["fishing_mode"])
        response = await self.service._mutate("rounds", current, work)
        self.assertEqual(previous.response, response)
        work.assert_not_called()
        self.service._quota.assert_not_called()
        self.service._expire_due.assert_not_called()
        self.session.add.assert_not_called()
        self.wallet.last_mutation_at = self.now  # even mutation cooldown cannot reject a retry
        self.assertEqual(response, await self.service._mutate("rounds", current, work))
        with self.assertRaises(HTTPException) as caught:
            await self.service._mutate("rounds", {**current, "fishing_mode": "regular"}, work)
        self.assertEqual("idempotency_mismatch", caught.exception.detail["code"])

    async def test_successful_collect_only_and_pre_policy_round_preserved(self):
        from app.games.models import GameRound
        row = GameRound(id=uuid4(), user_id=100001, game="fishing", status="active", bet=0,
                        payout=0, available_at=self.now - timedelta(seconds=1), public_state={"quota_policy_version": 1},
                        secret_state={"species": "Плотва", "rarity": "common", "value": 10, "weight_grams": 100})
        self.q.regular_catches = 10
        with self.assertRaises(HTTPException):
            await self.service._collect(self.context, row)
        self.session.add.assert_not_called()
        self.assertEqual("active", row.status)
        self.assertEqual(1000, self.wallet.balance)
        row.public_state = {"rod_level": 1}  # old active round, not a new legacy start
        await self.service._collect(self.context, row)
        self.assertEqual("caught", row.status)
        self.assertEqual(11, self.q.regular_catches)
        self.assertEqual({}, row.secret_state)

    async def test_lost_fishing_action_keeps_attempt_but_never_claims_or_adds_catch(self):
        from app.games.models import FishingCatch, GameRound
        from app.games.schemas import RoundAction
        self.use_create_callback()
        self.q.regular_attempts = 1
        row = GameRound(id=uuid4(), user_id=100001, game="fishing", status="active", bet=0,
                        payout=0, version=1, rules_version=1, created_at=self.now - timedelta(seconds=60),
                        public_state={"gameplay_version": 1, "rod_level": 1, "quota_policy_version": 1,
                                      "bite_tick": 90, "shoal_x": 0, "surge": 0},
                        secret_state={"species": "Карп", "rarity": "rare", "value": 60, "weight_grams": 1000})
        self.service._owned_round = AsyncMock(return_value=row)
        response = await self.service.action(row.id, RoundAction(key="lost", action="finish_fishing", version=1,
            fishing={"cast_x": 0, "cast_tick": 0, "hook_tick": None, "end_tick": 600, "events": []}))
        self.assertEqual("lost", response["status"])
        self.assertTrue(response["result"]["escaped"])
        self.assertEqual((1, 0), (self.q.regular_attempts, self.q.regular_catches))
        self.service._quota.assert_not_called()
        self.assertFalse(any(isinstance(call.args[0], FishingCatch) for call in self.session.add.call_args_list))
        self.assertEqual(1000, self.wallet.balance)

    async def test_successful_action_retry_at_cap_is_exactly_one_claim_and_one_catch(self):
        from app.games.models import FishingCatch, GameAction, GameRound
        from app.games.schemas import RoundAction
        vector = json.loads((Path(__file__).parent / "fishing_play_vectors.json").read_text(encoding="utf-8"))[0]
        self.q.regular_catches = 9
        row = GameRound(id=uuid4(), user_id=100001, game="fishing", status="active", bet=0,
                        payout=0, version=1, rules_version=1, created_at=self.now - timedelta(seconds=120),
                        public_state={**vector["challenge"], "gameplay_version": 1, "quota_policy_version": 1},
                        secret_state={"species": "Карп", "rarity": "rare", "value": 60, "weight_grams": 1000})
        self.service._owned_round = AsyncMock(return_value=row)
        body = RoundAction(key="collect-once", action="finish_fishing", version=1, fishing=vector["proof"])
        first = await self.service.action(row.id, body)
        self.assertEqual("caught", first["status"])
        self.assertEqual(10, self.q.regular_catches)
        previous = next(call.args[0] for call in self.session.add.call_args_list if isinstance(call.args[0], GameAction))
        self.session.scalar.return_value = previous
        again = await self.service.action(row.id, body)
        self.assertEqual(first, again)
        self.assertEqual(10, self.q.regular_catches)
        self.assertEqual(1, sum(isinstance(call.args[0], FishingCatch) for call in self.session.add.call_args_list))
        self.assertEqual(1, self.service._owned_round.await_count)
        self.session.scalar.return_value = None
        self.wallet.last_mutation_at = None
        with self.assertRaises(HTTPException) as caught:
            await self.service.action(row.id, body.model_copy(update={"key": "different-key", "version": 2}))
        self.assertEqual("round_closed", caught.exception.detail["code"])
        self.assertEqual(10, self.q.regular_catches)

    async def test_lazy_backfill_retains_today_history_and_context_cache(self):
        from app.games.service import GamesService
        self.session.get = AsyncMock(return_value=None)
        self.session.execute = AsyncMock(return_value=SimpleNamespace(one=lambda: SimpleNamespace(regular=25, boss=2, sports=40)))
        self.session.scalar.return_value = 10
        self.session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: ["old_carp"]))
        result = await GamesService._quota(self.service, self.context)
        self.assertEqual((25, 10, 2, 40, ["old_carp"]), (result.regular_attempts, result.regular_catches, result.boss_attempts, result.sport_rounds, result.claimed_bosses))
        self.assertIs(result, await GamesService._quota(self.service, self.context))
        self.assertEqual(1, self.session.get.await_count)
        self.assertEqual(1, self.session.execute.await_count)

    async def test_quota_metadata_fk_cascade_and_migration_scope(self):
        from app.games.models import GameDailyQuota, Wallet
        table = GameDailyQuota.__table__
        self.assertEqual(["user_id", "day"], [column.name for column in table.primary_key])
        self.assertEqual("CASCADE", next(iter(table.c.user_id.foreign_keys)).ondelete)
        self.assertEqual("users.id", next(iter(table.c.user_id.foreign_keys)).target_fullname)
        self.assertIn("carp", str(next(c.sqltext for c in Wallet.__table__.constraints if c.name == "ck_game_fishing_location")))
        migration = Path(__file__).parents[1] / "alembic/versions/0004_fishing_progression.py"
        tree = ast.parse(migration.read_text(encoding="utf-8"))
        revision = next(node for node in tree.body if isinstance(node, ast.Assign) and node.targets[0].id == "down_revision")
        self.assertEqual("0003_fishing_world", ast.literal_eval(revision.value))
        upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
        calls = [node.value for node in upgrade.body if isinstance(node, ast.Expr)]
        self.assertEqual(["drop_constraint", "create_check_constraint", "create_table"], [call.func.attr for call in calls])
        self.assertEqual("ck_game_fishing_location", ast.literal_eval(calls[0].args[0]))
        self.assertEqual("game_daily_quotas", ast.literal_eval(calls[2].args[0]))
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.schema import CreateTable
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        self.assertIn("ON DELETE CASCADE", ddl)
        self.assertIn("PRIMARY KEY (user_id, day)", ddl)


if __name__ == "__main__":
    unittest.main()
