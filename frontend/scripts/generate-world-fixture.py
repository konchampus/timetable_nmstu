"""Generate public, dev-only visual fixtures from the actual fishing rules.

No DB, authentication, randomness or real wallet operations are involved.
Run from the project root: python frontend/scripts/generate-world-fixture.py
"""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "backend"))
from app.games import engine, fishing_world, limits
from datetime import datetime, timezone
from types import SimpleNamespace
quota = SimpleNamespace(regular_attempts=0, regular_catches=0, boss_attempts=0, sport_rounds=0, claimed_bosses=[])
# Fixed synthetic time keeps fixtures reproducible; use no user or database data.
fixture_limits = limits.public_limits(quota, datetime(2026, 11, 17, 3, tzinfo=timezone.utc), None)

payload = {
    "fixture": True,
    "catalog": engine.catalog(),
    "levels": [{"items": [], "rod_level": level,
                "upgrade_cost": engine.ROD_COST[level - 1] if level < 5 else None,
                "max_rod_level": 5, "collection": [], "record_weight": 0, "limits": fixture_limits,
                **fishing_world.public_world(level, engine.FISH, engine.FISH_WEIGHTS, "shore", "angler")}
               for level in range(1, 6)],
}
target = root / "frontend/src/games/fishing-world.fixture.json"
target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("Generated dev-only fishing world fixture from public rules.")
