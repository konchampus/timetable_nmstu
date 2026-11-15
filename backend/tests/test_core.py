"""Synthetic offline core regressions; no Telegram/source/DB connections."""
import hashlib
import hmac
import json
import time
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode
from uuid import uuid4
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.config import config, Config
from app.main import app
from app.notifications import day_lessons, permitted, quiet
from app.schemas import NoteCreate, NoteDTO, NoteUpdate, SettingsDTO
from app.security import lock_authenticated_user, verify_init_data
from app.timetable import TZ, canonical_slug, date_week, parse_schedule, week_at


def signed(values):
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", config.bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**values, "hash": signature})


class SecurityAndSchemas(unittest.TestCase):
    def fields(self):
        return {"auth_date": str(int(time.time())), "user": json.dumps({"id": 100001, "first_name": "Test"})}

    def test_signed_auth_and_canonical_replay_digest(self):
        fields = self.fields()
        first = verify_init_data(signed(fields))
        second = verify_init_data(signed(dict(reversed(list(fields.items())))))
        self.assertEqual(first[1], second[1])
        self.assertEqual(100001, first[0]["id"])

    def test_tampered_expired_future_and_duplicate_auth_rejected(self):
        for fields in ({**self.fields(), "auth_date": "1"}, {**self.fields(), "auth_date": str(int(time.time()) + 120)}):
            with self.assertRaises(ValueError):
                verify_init_data(signed(fields))
        value = signed(self.fields())
        with self.assertRaises(ValueError):
            verify_init_data(value + "&auth_date=1")
        with self.assertRaises(ValueError):
            verify_init_data(value.replace("Test", "Other"))

    def test_non_object_telegram_user_rejected(self):
        with self.assertRaises(ValueError):
            verify_init_data(signed({**self.fields(), "user": "[]"}))

    def test_settings_version_required_and_preferences_default_off(self):
        with self.assertRaises(ValidationError):
            SettingsDTO()
        settings = SettingsDTO(version=1)
        self.assertFalse(settings.notifications_enabled)
        self.assertFalse(settings.leaderboard_visible)
        self.assertFalse(settings.morning_enabled)
        self.assertEqual([], settings.before_minutes)

    def test_settings_validation_and_consent(self):
        for values in ({"before_minutes": [1]}, {"weekdays": [7]}, {"morning_time": "25:00"}, {"quiet_start": "23:00"}, {"paused_until": "2026-01-01T12:00:00"}, {"leaderboard_visible": True, "nickname": " "}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                SettingsDTO(version=1, **values)
        self.assertEqual([5, 10], SettingsDTO(version=1, before_minutes=[10, 5, 10]).before_minutes)

    def test_note_create_uuid_is_not_part_of_update_or_output(self):
        with self.assertRaises(ValidationError):
            NoteCreate(title="Draft")
        dto = NoteCreate(title="Draft", request_id=uuid4(), date="2026-11-16")
        self.assertEqual("2026-11-16", dto.model_dump(mode="json")["date"])
        self.assertNotIn("request_id", NoteDTO.model_fields)
        self.assertNotIn("request_id", NoteUpdate.model_fields)

    def test_config_hides_validation_inputs(self):
        marker = "SYNTHETIC_SECRET_NOT_FOR_OUTPUT"
        with self.assertRaises(ValidationError) as caught:
            Config(database_url=marker)
        self.assertNotIn(marker, str(caught.exception))

    def test_host_header_and_json_error_shape(self):
        with TestClient(app, base_url="https://test.invalid") as client:
            result = client.get("/api/health")
            self.assertEqual(200, result.status_code)
            self.assertEqual("no-store", result.headers["cache-control"])
            wrong = client.get("/api/health", headers={"host": "attacker.invalid"})
            self.assertEqual(400, wrong.status_code)
            self.assertIsInstance(wrong.json()["detail"], str)
            bad = client.post("/api/auth/telegram", json={"init_data": "tiny"})
            self.assertEqual(422, bad.status_code)
            self.assertNotIn("tiny", bad.text)
            huge = client.post("/api/auth/telegram", content=b"x" * 65537)
            self.assertEqual(413, huge.status_code)


class TimetableRules(unittest.TestCase):
    def test_slug_and_foreign_url_rejection(self):
        self.assertEqual("АВб-26-2_1", canonical_slug("АВб-26-2_1"))
        for slug in ("https://evil.invalid", "../secret", "/group", "group?x=1", "a%2fb", "a\\b"):
            with self.subTest(slug=slug), self.assertRaises(HTTPException):
                canonical_slug(slug)

    def test_source_week_anchor_boundary_not_iso(self):
        anchor = datetime(2024, 8, 19, tzinfo=timezone.utc)
        self.assertEqual(2, week_at(anchor))
        self.assertEqual(1, week_at(anchor.replace(second=1)))
        self.assertEqual(1, date_week(date(2024, 8, 19)))
        self.assertEqual(2, date_week(date(2024, 8, 26)))

    def test_overnight_quiet_hours_and_weekday_pause_priority(self):
        settings = SettingsDTO(version=1, notifications_enabled=True, quiet_start="23:00", quiet_end="07:00", weekdays=[0])
        self.assertTrue(quiet(settings, datetime(2026, 11, 16, 23, 30, tzinfo=TZ)))
        self.assertTrue(quiet(settings, datetime(2026, 11, 16, 6, 30, tzinfo=TZ)))
        self.assertTrue(permitted(settings, datetime(2026, 11, 16, 8, tzinfo=TZ)))
        self.assertFalse(permitted(settings, datetime(2026, 11, 17, 8, tzinfo=TZ)))


class ParserAndAuthorization(unittest.IsolatedAsyncioTestCase):
    entity = {"id": "Test_group", "name": "Synthetic group", "kind": "group", "url": "https://timetable.magtu.ru/Test_group"}

    def html(self, lesson):
        return '<div class="group-name">Synthetic</div><div class="main-table-wrap">' + ''.join(f'<div class="week" id="week-{week}"><div class="day" id="day-{week}-1">{lesson if week == 1 else ""}</div></div>' for week in (1, 2)) + '</div>'

    async def test_parser_both_weeks_empty_and_malformed_snapshot(self):
        self.assertEqual([], await parse_schedule(self.html(""), self.entity))
        with self.assertRaises(ValueError):
            await parse_schedule('<html>Maintenance</html>', self.entity)
        with self.assertRaises(ValueError):
            await parse_schedule(self.html('<div class="less"><div class="title">Missing timing</div></div>'), self.entity)

    async def test_parser_preserves_literal_room_and_parallel_variants(self):
        lesson = '<div class="less"><div class="title">Synthetic subject</div><div class="ad">Лекция</div><div class="aud">1-с/зал1</div><div class="time">08:30 – 10:00</div><div class="couple-number">1</div></div>'
        other = lesson.replace("Synthetic subject", "Parallel subject")
        records = await parse_schedule(self.html(lesson + other), self.entity)
        self.assertEqual(2, len(records))
        self.assertEqual({"1-с/зал1"}, {record["room"] for record in records})
        reversed_records = await parse_schedule(self.html(other + lesson), self.entity)
        self.assertEqual(records, reversed_records)

    async def test_generation_mismatch_and_revoked_token_fail_closed(self):
        original = SimpleNamespace(id=100001, auth_token_hash="digest", auth_account_generation="old")
        row = SimpleNamespace(id=100001, active=True, account_generation="new")
        session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: row)))
        with self.assertRaises(HTTPException) as caught:
            await lock_authenticated_user(session, original)
        self.assertEqual(401, caught.exception.status_code)
        self.assertEqual(1, session.execute.await_count)
        row.account_generation = "old"
        session.execute = AsyncMock(side_effect=[SimpleNamespace(scalar_one_or_none=lambda: row), SimpleNamespace(scalar_one_or_none=lambda: None)])
        with self.assertRaises(HTTPException) as caught:
            await lock_authenticated_user(session, original)
        self.assertEqual(401, caught.exception.status_code)

    async def test_authenticated_fence_uses_db_clock_after_owner_lock(self):
        original = SimpleNamespace(id=100001, auth_token_hash="digest", auth_account_generation="same")
        row = SimpleNamespace(id=100001, active=True, account_generation="same")
        session = SimpleNamespace(execute=AsyncMock(side_effect=[SimpleNamespace(scalar_one_or_none=lambda: row), SimpleNamespace(scalar_one_or_none=lambda: "digest")]))
        self.assertIs(row, await lock_authenticated_user(session, original))
        statements = [str(call.args[0]) for call in session.execute.await_args_list]
        self.assertIn("FOR UPDATE", statements[0])
        self.assertIn("clock_timestamp()", statements[1])
