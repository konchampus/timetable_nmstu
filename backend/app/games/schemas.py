from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

GameId = Literal["slots", "fishing", "dice", "darts", "bowling", "basketball", "football", "coin", "roulette", "blackjack", "mines", "wheel"]
RoundStatus = Literal["active", "won", "lost", "push", "caught", "expired"]
Key = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]


class Mutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Key


class StartRound(Mutation):
    game: GameId
    bet: int = Field(strict=True, ge=0, le=500)
    choice: str | None = Field(default=None, max_length=30)
    mines: int | None = Field(default=None, strict=True, ge=1, le=10)
    gameplay_version: Literal[1] | None = None
    location: Literal["shore", "river", "mountain", "golden", "carp"] | None = None
    skin: Literal["angler", "bear"] | None = None
    fishing_mode: Literal["regular", "boss"] | None = None

    @model_validator(mode="after")
    def game_parameters(self) -> "StartRound":
        if self.gameplay_version is not None and self.game not in {"darts", "bowling", "basketball", "football", "fishing"}:
            raise ValueError("Локальная механика недоступна для этой игры")
        if self.game == "fishing":
            if self.bet != 0:
                raise ValueError("Рыбалка бесплатная: bet=0")
        elif self.bet < 10:
            raise ValueError("Ставка от 10 до 500")
        choices = {"dice": {"low", "high"}, "coin": {"heads", "tails"},
                   "roulette": {"red", "black", "even", "odd"} | {f"number:{n}" for n in range(37)}}
        if self.game in choices:
            if self.choice not in choices[self.game]:
                raise ValueError("Недопустимый выбор для этой игры")
        elif self.choice is not None:
            raise ValueError("В этой игре choice не используется")
        if self.game != "mines" and self.mines is not None:
            raise ValueError("mines используется только в сапёре")
        if (self.location is not None or self.skin is not None or self.fishing_mode is not None) and (self.game != "fishing" or self.gameplay_version != 1):
            raise ValueError("Локация, скин и режим доступны только в рыбалке с локальной механикой")
        return self


class ShotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aim_x: int = Field(strict=True, ge=-1000, le=1000)
    aim_y: int = Field(strict=True, ge=-1000, le=1000)
    power: int = Field(strict=True, ge=100, le=1000)
    ticks: int = Field(strict=True, ge=120, le=18000)


class FishingEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tick: int = Field(strict=True, ge=1, le=600)
    held: bool = Field(strict=True)


class FishingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cast_x: int = Field(strict=True, ge=-1000, le=1000)
    cast_tick: int = Field(strict=True, ge=0, le=5400)
    hook_tick: int | None = Field(default=None, strict=True, ge=0, le=600)
    end_tick: int = Field(strict=True, ge=1, le=600)
    events: list[FishingEvent] = Field(max_length=128)

    @model_validator(mode="after")
    def ordered_events(self) -> "FishingInput":
        if self.hook_tick is None:
            if self.events:
                raise ValueError("Вываживание невозможно без подсечки")
        elif self.hook_tick > self.end_tick:
            raise ValueError("Подсечка позже конца раунда")
        previous = self.hook_tick or 0
        for event in self.events:
            if event.tick <= previous or event.tick > self.end_tick:
                raise ValueError("События должны строго возрастать между подсечкой и концом")
            previous = event.tick
        return self


class RoundAction(Mutation):
    action: Literal["hit", "stand", "reveal", "cashout", "collect", "finish", "finish_fishing"]
    fishing: FishingInput | None = None
    shot: ShotInput | None = None
    cell: int | None = Field(default=None, strict=True, ge=0, le=24)
    version: int = Field(strict=True, ge=1, le=2147483647)

    @model_validator(mode="after")
    def cell_parameter(self) -> "RoundAction":
        if (self.action == "finish_fishing") != (self.fishing is not None):
            raise ValueError("Журнал рыбалки обязателен только для finish_fishing")
        if (self.action == "finish") != (self.shot is not None):
            raise ValueError("Параметры броска обязательны только для finish")
        if (self.action == "reveal") != (self.cell is not None):
            raise ValueError("cell обязателен только для reveal")
        return self


class RoundResponse(BaseModel):
    id: str
    game: GameId
    status: RoundStatus
    bet: int
    payout: int
    balance: int
    version: int
    rules_version: int = 1
    created_at: str
    available_at: str | None = None
    state: dict[str, JsonValue]
    result: dict[str, JsonValue] | None


class RoundsResponse(BaseModel):
    items: list[RoundResponse]


class GameInfo(BaseModel):
    id: GameId
    fishing_world_version: Literal[1] | None = None
    gameplay_version: Literal[1] | None = None
    rules_version: int = 1
    title: str
    description: str
    rules: list[str]
    min_bet: int
    max_bet: int
    payouts: dict[str, float]
    probabilities: dict[str, float]


class CatalogResponse(BaseModel):
    items: list[GameInfo]


class WalletResponse(BaseModel):
    balance: int
    inventory_value: int
    daily_available: bool
    rod_level: int


class LedgerItem(BaseModel):
    id: str
    round_id: str | None
    kind: Literal["start_bonus", "daily", "bet", "payout", "fishing_sale", "rod_upgrade"]
    amount: int
    balance_after: int
    created_at: str


class LedgerResponse(BaseModel):
    items: list[LedgerItem]


class DailyResponse(BaseModel):
    balance: int
    reward: int


class UpgradeResponse(BaseModel):
    balance: int
    rod_level: int


class SaleResponse(BaseModel):
    balance: int
    sold: int


class InventoryItem(BaseModel):
    species: str
    rarity: str
    count: int
    value: int
    weight: float


class FishingSpecies(BaseModel):
    name: str
    rarity: str


class LocationFish(BaseModel):
    species: str
    rarity: str
    value: int
    min_weight: float
    max_weight: float
    probability: float


class FishingBoss(BaseModel):
    id: str
    title: str
    description: str
    tier: int = Field(ge=1, le=3)
    min_rod_level: int = Field(ge=1, le=5)
    reward_species: str
    reward_value: int = Field(gt=0)


class FishingLimits(BaseModel):
    policy_version: Literal[1] = 1
    regular_attempts_remaining: int = Field(ge=0)
    regular_catches_remaining: int = Field(ge=0)
    boss_attempts_remaining: int = Field(ge=0)
    sport_rounds_remaining: int = Field(ge=0)
    claimed_bosses: list[str]
    next_cast_at: str | None
    resets_at: str
    server_now: str
    regular_daily_limit: Literal[10] = 10
    regular_attempt_daily_limit: Literal[25] = 25
    boss_daily_limit: Literal[3] = 3
    sports_daily_limit: Literal[40] = 40
    cast_cooldown_seconds: Literal[45] = 45


class FishingLocation(BaseModel):
    id: str
    title: str
    description: str
    tagline: str = ""
    story_title: str = ""
    story: str = ""
    landmark: str = ""
    featured_species: list[str] = Field(default_factory=list)
    min_rod_level: int
    unlocked: bool
    value_multiplier: float
    theme: str
    preview_rod_level: int
    fish: list[LocationFish]
    boss: FishingBoss | None = None


class FishingSkin(BaseModel):
    id: str
    title: str
    description: str
    min_rod_level: int
    unlocked: bool


class InventoryResponse(BaseModel):
    items: list[InventoryItem]
    rod_level: int
    upgrade_cost: int | None
    max_rod_level: int = 5
    collection: list[str]
    record_weight: float
    world_version: Literal[1] = 1
    selected_location: str = "shore"
    selected_skin: str = "angler"
    locations: list[FishingLocation]
    skins: list[FishingSkin]
    species: list[FishingSpecies]
    limits: FishingLimits


class LeaderboardItem(BaseModel):
    rank: int
    nickname: str
    score: int


class LeaderboardSelf(BaseModel):
    rank: int | None
    score: int


class LeaderboardResponse(BaseModel):
    items: list[LeaderboardItem]
    self: LeaderboardSelf
