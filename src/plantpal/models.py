"""Pydantic models: shared API request/response schemas and DB-row DTOs."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

# --- Auth ---


class LoginRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    invite_token: str = Field(min_length=8)
    email: EmailStr


class SessionUser(BaseModel):
    id: int
    email: str
    is_admin: bool


class GenericOk(BaseModel):
    ok: bool = True
    message: str | None = None


# --- Plants ---


class PlantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    interval_days: int = Field(ge=1, le=365)
    notes: str | None = Field(default=None, max_length=500)
    water_amount_ml: int | None = Field(default=None, ge=1, le=5000)


class PlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    interval_days: int | None = Field(default=None, ge=1, le=365)
    notes: str | None = Field(default=None, max_length=500)
    water_amount_ml: int | None = Field(default=None, ge=1, le=5000)


class PlantResponse(BaseModel):
    id: int
    name: str
    interval_days: int
    image_url: str | None
    last_watered_at: str
    created_at: str
    notes: str | None
    water_amount_ml: int | None
    is_thirsty: bool
    days_overdue: int


# --- Settings ---


class SettingsResponse(BaseModel):
    email: str
    email_reminders_enabled: bool
    reminder_channel: str


class SettingsUpdate(BaseModel):
    email_reminders_enabled: bool


# --- Admin ---


class InviteCreateRequest(BaseModel):
    email_hint: str | None = Field(default=None, max_length=200)


class InviteResponse(BaseModel):
    invite_url: str
    expires_at: str


# --- Stats ---


class StatsResponse(BaseModel):
    total_plants: int
    thirsty_count: int


# --- Health ---


class HealthResponse(BaseModel):
    status: str
    db_ok: bool
    scheduler_running: bool
