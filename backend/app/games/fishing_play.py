"""20 Hz integer fishing simulation, mirrored by frontend fishing-play.ts."""
TICK_RATE = 20
MAX_TICKS = 600

def bite_tick(challenge: dict, cast_x: int) -> int:
    return challenge["bite_tick"] + abs(cast_x - challenge["shoal_x"]) // 100

def initial() -> dict:
    return {"tension": 45, "progress": 0, "slack": 0, "status": "fighting", "reason": ""}

def step(state: dict, challenge: dict, tick: int, held: bool) -> dict:
    if state["status"] != "fighting":
        return state
    wave = ((tick + challenge["surge"]) // 16) % 4
    pull = (2, 4, 1, 3)[wave]
    tension = max(0, state["tension"] + (2 + pull if held else -6))
    progress = max(0, state["progress"] + (10 + challenge["rod_level"] if held and 28 <= tension <= 78 else -3))
    slack = state["slack"] + 1 if tension < 8 else 0
    status, reason = "fighting", ""
    if tension >= 100:
        status, reason = "lost", "line_broke"
    elif slack >= 20:
        status, reason = "lost", "slack_line"
    elif progress >= 1000:
        status, reason = "caught", "landed"
    return {"tension": min(100, tension), "progress": min(1000, progress), "slack": slack, "status": status, "reason": reason}

def replay(challenge: dict, proof: dict) -> dict:
    bite = bite_tick(challenge, proof["cast_x"])
    hook = proof["hook_tick"]
    end = proof["end_tick"]
    if hook is None or hook < bite or hook > bite + 24:
        return {**initial(), "status": "lost", "reason": "missed_hook"}
    state, held, event_index = initial(), False, 0
    events = proof["events"]
    for tick in range(hook + 1, end + 1):
        while event_index < len(events) and events[event_index]["tick"] <= tick:
            held = events[event_index]["held"]
            event_index += 1
        state = step(state, challenge, tick - hook, held)
        if state["status"] != "fighting":
            if tick != end:
                raise ValueError("Input continues after terminal tick")
            return state
    if end != MAX_TICKS:
        raise ValueError("Fight is not finished")
    return {**state, "status": "lost", "reason": "fish_escaped"}
