from __future__ import annotations
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)

class Credentials(StrictModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=False)
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)
    invite_code: str = Field(default="", max_length=200)

class PasswordChange(StrictModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=False)
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

class Location(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float = Field(default=0, ge=-500, le=9000)
    min_elevation_deg: float = Field(default=5, ge=0, le=60)
    timezone: str = Field(default="America/New_York", max_length=80)
    alerts: bool = True
    horizon_profile: list[float] = Field(default_factory=list, max_length=8)
    @field_validator("horizon_profile")
    @classmethod
    def horizon_values(cls, v):
        from .horizon import validate_profile
        return validate_profile(v)
    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, v):
        try: ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError): raise ValueError("Use an IANA timezone, e.g. America/New_York")
        return v

class Preferences(StrictModel):
    enabled: bool = False
    lead_minutes: list[int] = Field(default_factory=lambda: [60, 15], max_length=5)
    include_candidates: bool = False
    include_estimates: bool = False
    jellyfish_only: bool = False
    schedule_changes: bool = True
    quiet_start: int | None = Field(default=None, ge=0, le=23)
    quiet_end: int | None = Field(default=None, ge=0, le=23)
    @field_validator("lead_minutes")
    @classmethod
    def leads(cls, v):
        if not v or any(x < 1 or x > 1440 for x in v): raise ValueError("Choose 1–1440 minutes, at least one lead time")
        return sorted(set(v), reverse=True)
    @model_validator(mode="after")
    def quiet_pair(self):
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ValueError("Provide both quiet-hour boundaries or neither")
        return self

class TrackPoint(StrictModel):
    t_s: float = Field(ge=0, le=3600)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude_km: float = Field(ge=0, le=2000)
    powered: bool = False
    plume: bool = False

class Trajectory(StrictModel):
    source: str = Field(min_length=5, max_length=500)
    source_url: str = Field(default="", max_length=1000)
    kind: Literal["estimated", "mission-specific"] = "estimated"
    notes: str = Field(default="", max_length=2000)
    points: list[TrackPoint] = Field(min_length=2, max_length=1500)
    @field_validator("source_url")
    @classmethod
    def source_scheme(cls, v):
        if v and not v.startswith("https://"): raise ValueError("Source URL must be HTTPS")
        return v
    @model_validator(mode="after")
    def monotonic(self):
        times = [p.t_s for p in self.points]
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("Track times must be strictly increasing")
        if any(b-a > 120 for a,b in zip(times,times[1:])):
            raise ValueError("Track sample gaps must be at most 120 seconds")
        return self

class Scenario(StrictModel):
    heading_deg: float = Field(ge=0, lt=360)
    source: str = Field(default="User-entered direction; illustrative ascent, not flight telemetry", min_length=5, max_length=500)

class PushKeys(StrictModel):
    p256dh: str = Field(min_length=80, max_length=200, pattern=r"^[A-Za-z0-9_=-]+$")
    auth: str = Field(min_length=20, max_length=80, pattern=r"^[A-Za-z0-9_=-]+$")

class PushSubscription(StrictModel):
    endpoint: str = Field(min_length=20, max_length=2000)
    keys: PushKeys
    expirationTime: float | None = None
