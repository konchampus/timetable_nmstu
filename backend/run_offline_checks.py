"""Run offline checks with synthetic settings; never read a real .env or connect to DB."""
import os
import unittest
os.environ.update(DATABASE_URL="postgresql+asyncpg://offline:synthetic_only@127.0.0.1:1/companion_offline_test", BOT_TOKEN="123456789:" + "x" * 35, MINI_APP_URL="https://test.invalid", ALLOWED_ORIGINS='["https://test.invalid"]', ALLOWED_HOSTS='["test.invalid"]')
from unittest.mock import patch
# Suppress dotenv before importing app.config (which constructs Config immediately).
patch("pydantic_settings.sources.DotEnvSettingsSource.__call__", return_value={}).start()
# Do not patch socket.connect: Windows asyncio uses it to build its local wakeup pipe.
patch("socket.create_connection", side_effect=AssertionError("Offline checks forbid network connections")).start()
patch("asyncpg.connect", side_effect=AssertionError("Offline checks forbid database connections")).start()
suite = unittest.TestSuite()
for pattern in ("test_engine.py", "test_arcade.py", "test_fishing_play.py", "test_fishing_progression.py", "test_core.py"):
    suite.addTests(unittest.defaultTestLoader.discover("tests", pattern=pattern))
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
