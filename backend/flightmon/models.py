"""Domain models for searches and results.

Pydantic v2 models — they validate the JSONB blobs stored in Supabase and
serialize cleanly for inserts back into the DB.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# --- destinations ----------------------------------------------------------


class DestinationsInclude(BaseModel):
    mode: Literal["include"]
    iatas: list[str] = Field(min_length=1)


class DestinationsExclude(BaseModel):
    mode: Literal["exclude"]
    iatas: list[str] = Field(default_factory=list)


class DestinationsAny(BaseModel):
    mode: Literal["any"]
    region: str | None = None  # e.g. "EUROPE" — informational, not used by Amadeus


Destinations = DestinationsInclude | DestinationsExclude | DestinationsAny


# --- filters ---------------------------------------------------------------


class PriceRange(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str = "EUR"


class Filters(BaseModel):
    max_stops: int | None = None
    max_duration_minutes: int | None = None
    excluded_airlines: list[str] = Field(default_factory=list)


class NotifyOn(BaseModel):
    price_under: float | None = None
    new_lowest: bool = False


# --- search ---------------------------------------------------------------


class DateWindow(BaseModel):
    start: date
    end: date

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: date, info):
        start = info.data.get("start")
        if start and v < start:
            raise ValueError("end must be on or after start")
        return v


class DurationRange(BaseModel):
    min: int = Field(ge=1)
    max: int = Field(ge=1)

    @field_validator("max")
    @classmethod
    def max_ge_min(cls, v: int, info):
        mn = info.data.get("min")
        if mn is not None and v < mn:
            raise ValueError("max must be >= min")
        return v


class Search(BaseModel):
    id: str
    name: str
    active: bool = True
    origin_iata: str = Field(min_length=3, max_length=3)
    trip_type: Literal["round_trip", "one_way"] = "round_trip"
    outbound_window: DateWindow
    duration_days: DurationRange | None = None  # required iff round_trip
    destinations: Destinations
    price_range: PriceRange | None = None
    filters: Filters = Field(default_factory=Filters)
    notify_on: NotifyOn = Field(default_factory=NotifyOn)


# --- result ----------------------------------------------------------------


class FlightResult(BaseModel):
    search_id: str
    origin_iata: str
    destination_iata: str
    departure_date: date
    return_date: date | None = None
    price_eur: float
    airline: str | None = None
    stops: int | None = None
    duration_minutes: int | None = None
    deep_link: str | None = None
    raw_offer: dict | None = None
