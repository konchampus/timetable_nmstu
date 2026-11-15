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

    @model_validator(mode="after")
    def game_parameters(self) -> "StartRound":
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
        return self


class RoundAction(Mutation):
    action: Literal["hit", "stand", "reveal", "cashout", "collect"]
    cell: int | None = Field(default=None, strict=True, ge=0, le=24)
    version: int = Field(strict=True, ge=1, le=2147483647)

    @model_validator(mode="after")
    def cell_parameter(self) -> "RoundAction":
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


class InventoryResponse(BaseModel):
    items: list[InventoryItem]
    rod_level: int
    upgrade_cost: int | None
    max_rod_level: int = 5
    collection: list[str]
    record_weight: float


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
