"""Local offline code checks. Always overwrites app configuration with synthetic values."""
import compileall
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.update(
    DATABASE_URL="postgresql+asyncpg://test_runner:synthetic_only@127.0.0.1:1/companion_test",
    BOT_TOKEN="100000:TEST_ONLY_NOT_A_REAL_TOKEN_1234567890123456789",
    MINI_APP_URL="https://test.invalid",
    ALLOWED_ORIGINS='["https://test.invalid"]',
    ALLOWED_HOSTS='["test.invalid"]',
)
if not compileall.compile_dir("app", quiet=1) or not compileall.compile_dir("alembic", quiet=1):
    raise SystemExit(1)
from app.main import app
from app.bot import router as bot_router
from app import worker
from app.db import Base
from sqlalchemy.orm import configure_mappers
configure_mappers()
print(f"Imported API/bot/worker; {len(app.routes)} routes, {len(Base.metadata.tables)} tables")
from io import StringIO
from alembic import command
from alembic.config import Config as AlembicConfig
output = StringIO()
migration = AlembicConfig("alembic.ini", output_buffer=output)
command.upgrade(migration, "head", sql=True)
assert "CREATE TABLE users" in output.getvalue()
assert "account_generation VARCHAR(36) NOT NULL" in output.getvalue()
assert "fk_game_catch_round_owner" in output.getvalue()
output.truncate(0)
output.seek(0)
command.downgrade(migration, "0001_initial:base", sql=True)
assert "DROP TABLE users" in output.getvalue()
print("Frozen Alembic upgrade/downgrade generated offline")
suite = unittest.TestSuite()
loader = unittest.TestLoader()
for pattern in ("test_engine.py", "test_core.py"):
    suite.addTests(loader.discover("tests", pattern=pattern))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
