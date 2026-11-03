"""Travel tools: a Pydantic argument schema + a safe implementation for each tool.

Schemas only check *format* (types, codes, ids). Business rules (future dates,
capacity, booking exists) are checked inside the tools and raise ToolError,
so they are reported to the user instead of being "fixed" by the model.
"""
import json
import re
import time
from datetime import date
from pathlib import Path

import requests
from pydantic import BaseModel, Field, field_validator

DATA = Path(__file__).parent / "data"
HOTELS_PATH = DATA / "hotels.json"
BOOKINGS_PATH = DATA / "bookings.json"  # runtime file (git-ignored), created from SEED_BOOKINGS
TIMEOUT = 6
SIMULATE_OUTAGE = False  # demo switch: points the currency API at a dead address

SEED_BOOKINGS = [{
    "booking_id": "BK1001", "hotel_id": "H01", "hotel_name": "Palm Shore Resort", "city": "Goa",
    "guest_name": "Asha", "check_in": "2026-12-10", "check_out": "2026-12-12", "guests": 2,
    "nights": 2, "total_inr": 10400, "status": "confirmed",
}]

# Approximate rates per 1 EUR, used only when the live API fails.
CACHED_EUR_RATES = {"EUR": 1.0, "USD": 1.08, "INR": 90.5, "GBP": 0.85, "JPY": 163.0, "AED": 3.97,
                    "SGD": 1.46, "AUD": 1.65, "CAD": 1.49, "THB": 38.5, "CHF": 0.94}
CURRENCY_ALIASES = {"RUPEE": "INR", "RUPEES": "INR", "RS": "INR", "DOLLAR": "USD", "DOLLARS": "USD",
                    "EURO": "EUR", "EUROS": "EUR", "POUND": "GBP", "POUNDS": "GBP", "YEN": "JPY", "DIRHAM": "AED"}

WEATHER_CODES = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
                 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
                 65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
                 81: "rain showers", 82: "violent showers", 95: "thunderstorm", 96: "thunderstorm", 99: "thunderstorm"}


class ToolError(Exception):
    """A readable error that is shown to the user (not a crash)."""


# ---------- argument schemas ----------
class WeatherArgs(BaseModel):
    city: str = Field(min_length=2, max_length=60)


class CurrencyArgs(BaseModel):
    amount: float = Field(gt=0, le=1e9)
    from_currency: str
    to_currency: str

    @field_validator("from_currency", "to_currency")
    @classmethod
    def currency_code(cls, v: str) -> str:
        v = CURRENCY_ALIASES.get(v.strip().upper(), v.strip().upper())
        if not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError("must be a 3-letter currency code like USD or INR")
        return v


class HotelSearchArgs(BaseModel):
    city: str = Field(min_length=2, max_length=60)
    max_price_per_night: float | None = Field(default=None, gt=0)
    guests: int = Field(default=1, ge=1, le=10)


class BookArgs(BaseModel):
    hotel_id: str
    guest_name: str = Field(min_length=2, max_length=60)
    check_in: date
    check_out: date
    guests: int = Field(default=1, ge=1, le=10)

    @field_validator("hotel_id")
    @classmethod
    def hotel_id_format(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"H\d{2}", v):
            raise ValueError("must look like H05")
        return v


class CancelArgs(BaseModel):
    booking_id: str

    @field_validator("booking_id")
    @classmethod
    def booking_id_format(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"BK\d{4}", v):
            raise ValueError("must look like BK1001")
        return v


class ListArgs(BaseModel):
    pass


# ---------- helpers ----------
def _get_json(url: str, params: dict) -> dict:
    """GET with timeout and 1 retry; raises ToolError on failure."""
    last = None
    for _ in range(2):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            last = e
            time.sleep(0.3)
    raise ToolError(f"service unavailable after 1 retry ({type(last).__name__})")


def _hotels() -> list[dict]:
    return json.loads(HOTELS_PATH.read_text(encoding="utf-8"))["hotels"]


def _load_bookings() -> list[dict]:
    if not BOOKINGS_PATH.exists():
        _save_bookings(SEED_BOOKINGS)
    return json.loads(BOOKINGS_PATH.read_text(encoding="utf-8"))


def _save_bookings(bookings: list[dict]) -> None:
    BOOKINGS_PATH.write_text(json.dumps(bookings, indent=2), encoding="utf-8")


# ---------- tools ----------
def get_weather(a: WeatherArgs) -> dict:
    geo = _get_json("https://geocoding-api.open-meteo.com/v1/search",
                    {"name": a.city, "count": 5, "language": "en", "format": "json"})
    if not geo.get("results"):
        raise ToolError(f"city '{a.city}' was not found - check the spelling")
    # India travel app: prefer an Indian match for ambiguous names (e.g. Kochi, Japan vs Kochi, India)
    place = next((p for p in geo["results"] if p.get("country_code") == "IN"), geo["results"][0])
    fc = _get_json("https://api.open-meteo.com/v1/forecast", {
        "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto", "forecast_days": 3,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"})
    cur, d = fc["current"], fc["daily"]
    return {
        "city": place["name"], "country": place.get("country", ""),
        "temperature_c": cur["temperature_2m"], "condition": WEATHER_CODES.get(cur["weather_code"], "unknown"),
        "humidity_pct": cur["relative_humidity_2m"], "wind_kmh": cur["wind_speed_10m"],
        "forecast": [{"date": d["time"][i], "min_c": d["temperature_2m_min"][i], "max_c": d["temperature_2m_max"][i],
                      "rain_chance_pct": d["precipitation_probability_max"][i],
                      "condition": WEATHER_CODES.get(d["weather_code"][i], "unknown")} for i in range(len(d["time"]))],
        "source": "Open-Meteo (live)",
    }


def convert_currency(a: CurrencyArgs) -> dict:
    url = "http://127.0.0.1:9/latest" if SIMULATE_OUTAGE else "https://api.frankfurter.dev/v1/latest"
    note = None
    if a.from_currency == a.to_currency:
        rate, source = 1.0, "same currency"
    else:
        try:
            data = _get_json(url, {"base": a.from_currency, "symbols": a.to_currency})
            rate, source = data["rates"][a.to_currency], f"Frankfurter (live, {data.get('date', 'today')})"
        except (ToolError, KeyError) as e:
            # Fallback: small cached table, clearly labelled.
            if a.from_currency not in CACHED_EUR_RATES or a.to_currency not in CACHED_EUR_RATES:
                raise ToolError(f"live rates failed and {a.from_currency}/{a.to_currency} is not in the cached table")
            rate = CACHED_EUR_RATES[a.to_currency] / CACHED_EUR_RATES[a.from_currency]
            source = "cached table (approximate)"
            note = f"Live rate API failed ({e}); used cached approximate rates."
    return {"amount": a.amount, "from": a.from_currency, "to": a.to_currency, "rate": round(rate, 4),
            "converted": round(a.amount * rate, 2), "source": source, "note": note}


def search_hotels(a: HotelSearchArgs) -> dict:
    hotels = _hotels()
    in_city = [h for h in hotels if h["city"].lower() == a.city.strip().lower()]
    if not in_city:
        cities = sorted({h["city"] for h in hotels})
        raise ToolError(f"no sample hotels in '{a.city}'. Available cities: {', '.join(cities)}")
    match = [h for h in in_city if h["max_guests"] >= a.guests
             and (a.max_price_per_night is None or h["price_per_night"] <= a.max_price_per_night)]
    match.sort(key=lambda h: h["price_per_night"])
    return {"city": in_city[0]["city"], "count": len(match), "hotels": match[:5], "data": "sample data",
            "note": None if match else f"nothing matches; cheapest here is INR {min(h['price_per_night'] for h in in_city)}"}


def preview_booking(a: BookArgs) -> dict:
    """Check business rules and build the confirmation summary (nothing is saved)."""
    hotel = next((h for h in _hotels() if h["id"] == a.hotel_id), None)
    if not hotel:
        raise ToolError(f"hotel {a.hotel_id} does not exist (ids are H01-H20)")
    if a.check_in <= date.today():
        raise ToolError(f"check-in {a.check_in} must be in the future")
    if a.check_out <= a.check_in:
        raise ToolError(f"check-out {a.check_out} must be after check-in {a.check_in}")
    nights = (a.check_out - a.check_in).days
    if nights > 30:
        raise ToolError("stays longer than 30 nights are not supported")
    if a.guests > hotel["max_guests"]:
        raise ToolError(f"{hotel['name']} fits max {hotel['max_guests']} guests, you asked for {a.guests}")
    return {"hotel_id": hotel["id"], "hotel_name": hotel["name"], "city": hotel["city"], "guest_name": a.guest_name,
            "check_in": str(a.check_in), "check_out": str(a.check_out), "guests": a.guests,
            "nights": nights, "total_inr": nights * hotel["price_per_night"]}


def book_hotel(a: BookArgs) -> dict:
    booking = preview_booking(a)  # re-check rules at execution time
    bookings = _load_bookings()
    next_id = max([int(b["booking_id"][2:]) for b in bookings] + [1000]) + 1
    booking = {"booking_id": f"BK{next_id}", **booking, "status": "confirmed"}
    _save_bookings(bookings + [booking])
    return booking


def preview_cancel(a: CancelArgs) -> dict:
    b = next((b for b in _load_bookings() if b["booking_id"] == a.booking_id), None)
    if not b:
        raise ToolError(f"booking {a.booking_id} was not found")
    if b["status"] == "cancelled":
        raise ToolError(f"booking {a.booking_id} is already cancelled")
    return b


def cancel_booking(a: CancelArgs) -> dict:
    preview_cancel(a)
    bookings = _load_bookings()
    for b in bookings:
        if b["booking_id"] == a.booking_id:
            b["status"] = "cancelled"
            _save_bookings(bookings)
            return b


def list_bookings(a: ListArgs) -> dict:
    bookings = _load_bookings()
    return {"count": len(bookings), "bookings": bookings}


# Whitelist: only these tools can ever run. "confirm" = preview function for important actions.
TOOLS = {
    "get_weather": {"schema": WeatherArgs, "fn": get_weather, "confirm": None},
    "convert_currency": {"schema": CurrencyArgs, "fn": convert_currency, "confirm": None},
    "search_hotels": {"schema": HotelSearchArgs, "fn": search_hotels, "confirm": None},
    "book_hotel": {"schema": BookArgs, "fn": book_hotel, "confirm": preview_booking},
    "cancel_booking": {"schema": CancelArgs, "fn": cancel_booking, "confirm": preview_cancel},
    "list_bookings": {"schema": ListArgs, "fn": list_bookings, "confirm": None},
}
