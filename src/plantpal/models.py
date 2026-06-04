"""Pydantic models: shared API request/response schemas and DB-row DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

# --- Auth ---


class LoginRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    invite_token: str = Field(min_length=8)
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class SessionUser(BaseModel):
    id: int
    email: str
    is_admin: bool


class GenericOk(BaseModel):
    ok: bool = True
    message: str | None = None


# --- Invites (v3: user-created multi-use links) ---


class InviteCreateRequest(BaseModel):
    email_hint: str | None = Field(default=None, max_length=200)
    max_uses: int = Field(default=1, ge=1, le=20)
    expires_in_days: int | None = Field(default=None, ge=1, le=90)


class InviteResponse(BaseModel):
    invite_url: str
    expires_at: str
    max_uses: int
    used_count: int
    remaining_quota: int | None = None


class InviteListItem(BaseModel):
    id: int
    max_uses: int
    used_count: int
    expires_at: str
    revoked_at: str | None
    created_at: str
    status: str  # active | exhausted | expired | revoked


# --- Email change (v3) ---


class EmailChangeRequestBody(BaseModel):
    new_email: EmailStr


class EmailChangeConfirm(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


# --- Plants ---


class PlantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    interval_days: int = Field(ge=1, le=365)
    notes: str | None = Field(default=None, max_length=500)
    water_amount_ml: int | None = Field(default=None, ge=1, le=5000)
    location_room: str | None = Field(default=None, max_length=80)


class PlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    interval_days: int | None = Field(default=None, ge=1, le=365)
    notes: str | None = Field(default=None, max_length=500)
    water_amount_ml: int | None = Field(default=None, ge=1, le=5000)
    location_room: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _reject_null_required(self) -> PlantUpdate:
        # name/interval_days are NOT NULL in the DB — an explicit null in the PATCH body must be
        # a 422, not a SQLite constraint crash. (notes/room/ml are intentionally nullable.)
        for field in ("name", "interval_days"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class PlantResponse(BaseModel):
    id: int
    name: str
    interval_days: int
    image_url: str | None
    last_watered_at: str
    created_at: str
    notes: str | None
    water_amount_ml: int | None
    location_room: str | None
    is_thirsty: bool
    days_overdue: int


class WateringResponse(BaseModel):
    id: int
    watered_at: str
    created_at: str


class PlantGroup(BaseModel):
    location_room: str | None
    plant_ids: list[int]


# --- Settings ---


class SettingsResponse(BaseModel):
    email: str
    email_reminders_enabled: bool
    reminder_channel: str
    locale: str
    reminder_hour: int
    theme: str
    invite_quota: int
    is_admin: bool


class SettingsUpdate(BaseModel):
    email_reminders_enabled: bool | None = None
    locale: Literal["de", "en"] | None = None
    reminder_hour: int | None = Field(default=None, ge=0, le=23)
    theme: Literal["dark", "light"] | None = None


# --- Stats ---


class LongestOverdue(BaseModel):
    plant_id: int
    name: str
    days_overdue: int


class RoomStats(BaseModel):
    location_room: str | None
    total_plants: int
    thirsty_count: int


class StatsResponse(BaseModel):
    total_plants: int
    thirsty_count: int
    watering_streak_days: int
    watering_consistency_pct: int
    longest_overdue: LongestOverdue | None
    avg_interval_days: float | None
    avg_configured_interval_days: float | None
    rooms: list[RoomStats] | None = None


# --- Health ---


class HealthResponse(BaseModel):
    status: str
    db_ok: bool
    scheduler_running: bool
    db_writable: bool = True
    wal_mode: bool = True
    version: str = "3.0.0"
    jobs: dict[str, bool] | None = None
    reminder_last_run: str | None = None
