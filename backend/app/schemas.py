import re
from datetime import date as CalendarDate, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SettingsDTO(StrictModel):
    version: int = Field(ge=1)
    home_entity: str | None = Field(default=None, max_length=200)
    home_name: str | None = Field(default=None, max_length=200)
    notifications_enabled: bool = False
    before_minutes: list[int] = Field(default_factory=list, max_length=5)
    morning_enabled: bool = False
    morning_time: str = "07:00"
    evening_enabled: bool = False
    evening_time: str = "20:00"
    changes_enabled: bool = False
    end_enabled: bool = False
    quiet_start: str | None = None
    quiet_end: str | None = None
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), max_length=7)
    paused_until: datetime | None = None
    theme: Literal["auto", "light", "dark"] = "auto"
    sound: bool = False
    haptics: bool = False
    leaderboard_visible: bool = False
    nickname: str = Field(default="", max_length=40)

    @field_validator("morning_time", "evening_time", "quiet_start", "quiet_end")
    @classmethod
    def valid_time(cls, value):
        if value is not None and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Time must be HH:mm")
        return value

    @field_validator("before_minutes")
    @classmethod
    def valid_before(cls, value):
        if any(i not in (5, 10, 15, 30, 60) for i in value):
            raise ValueError("Intervals: 5,10,15,30,60")
        return sorted(set(value))

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls, value):
        if any(i < 0 or i > 6 for i in value):
            raise ValueError("Weekdays must be 0..6")
        return sorted(set(value))

    @field_validator("paused_until")
    @classmethod
    def aware_pause(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("Timezone required")
        return value

    @model_validator(mode="after")
    def consistent(self):
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ValueError("Both quiet hours required")
        if self.leaderboard_visible and not self.nickname.strip():
            raise ValueError("Nickname required for public leaderboard")
        self.nickname = self.nickname.strip()
        return self


class AuthInput(StrictModel):
    init_data: str = Field(min_length=10, max_length=10000)


class FavoriteInput(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["teacher", "group"]


class NoteInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(default="", max_length=5000)
    kind: Literal["note", "homework"] = "note"
    date: CalendarDate | None = None
    lesson_id: str | None = Field(default=None, max_length=64)
    source_entity: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)


class NoteCreate(NoteInput):
    request_id: UUID


class NoteUpdate(NoteInput):
    version: int = Field(ge=1)
    done: bool


class DeleteAccount(StrictModel):
    confirmation: Literal["DELETE"]


class AuthUserDTO(StrictModel):
    id: int
    name: str
    account_generation: str


class AuthResponse(StrictModel):
    token: str
    user: AuthUserDTO


class MeDTO(AuthUserDTO):
    settings: SettingsDTO


class EntityDTO(StrictModel):
    id: str
    name: str
    kind: Literal["group", "teacher"]
    url: str


class EntityList(StrictModel):
    items: list[EntityDTO]


class LessonDTO(StrictModel):
    id: str
    week: Literal[1, 2]
    weekday: int = Field(ge=0, le=6)
    number: int
    title: str
    kind: str
    start: str
    end: str
    room: str
    teachers: list[EntityDTO]
    groups: list[EntityDTO]


class ScheduleDTO(StrictModel):
    entity: EntityDTO
    fetched_at: datetime
    stale: bool
    template: Literal[True]
    lessons: list[LessonDTO]
    current_week: Literal[1, 2]
    timezone: str


class NoteDTO(NoteUpdate):
    id: str
    updated_at: datetime
    lesson_status: Literal["unlinked", "unknown", "current", "changed"] = "unknown"


class NoteList(StrictModel):
    items: list[NoteDTO]
