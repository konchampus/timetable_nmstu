"""Integer, deterministic shot replay. No client-reported score is accepted.

The same model runs in frontend arcade.ts; this validates legal input, not
that a human rather than a bot produced that input.
"""
from fractions import Fraction
from .engine import Outcome, DART_PAYOUTS, BOWLING_PAYOUTS

SPORTS = frozenset(("darts", "bowling", "basketball", "football"))
TICKS = 60

def trunc_div(value: int, divisor: int) -> int:
    return (1 if value >= 0 else -1) * (abs(value) // divisor)

def trajectory(challenge: dict, shot: dict) -> list[dict]:
    return [{"x": trunc_div(shot["aim_x"] * t, TICKS) + trunc_div(challenge["wind"] * t * t, TICKS * TICKS),
             "y": trunc_div(shot["aim_y"] * t, TICKS) + trunc_div((shot["power"] - 650) * t, 30) + trunc_div(2400 * t * (TICKS - t), TICKS * TICKS),
             "z": t} for t in range(TICKS + 1)]

def replay(game: str, challenge: dict, shot: dict) -> Outcome:
    if game not in SPORTS or challenge.get("gameplay_version") != 1:
        raise ValueError("Unsupported arcade protocol")
    point = trajectory(challenge, shot)[-1]
    dx, dy = point["x"] - challenge["target_x"], point["y"] - challenge["target_y"]
    distance_squared = dx * dx + dy * dy
    if game == "darts":
        value = next((score for radius, score in ((70, 50), (150, 25), (270, 20), (400, 10), (540, 5)) if distance_squared <= radius * radius), 0)
        multiplier = Fraction(DART_PAYOUTS[value])
        result = {"value": value}
    elif game == "bowling":
        pins = [(0, 0), (-65, 65), (65, 65), (-130, 130), (0, 130), (130, 130), (-195, 195), (-65, 195), (65, 195), (195, 195)]
        value = sum((dx - x) ** 2 + (dy - y) ** 2 <= (160 + shot["power"] // 10) ** 2 for x, y in pins)
        multiplier = Fraction(BOWLING_PAYOUTS[value])
        result = {"value": value}
    else:
        success = distance_squared <= 110 ** 2 if game == "basketball" else abs(dx) <= 260 and abs(dy) <= 180
        multiplier = (Fraction(9, 4) if game == "basketball" else Fraction(3, 2)) if success else Fraction(0)
        result = {"success": success}
    return Outcome({**result, "impact_x": point["x"], "impact_y": point["y"], "gameplay_version": 1}, multiplier)
