"""Keyword + regex fallback router, used only when the model's choice stays invalid after 1 retry."""
import re

INTENTS = {  # tool -> keyword pattern (checked in this order)
    "cancel_booking": r"\bcancel\b",
    "list_bookings": r"\b(my|list|show|all)\b.*\bbookings?\b",
    "book_hotel": r"\b(book|reserve)\b.*\b(hotel|H\d{2})\b",
    "search_hotels": r"\b(hotels?|stay|rooms?|accommodation)\b",
    "convert_currency": r"\b(convert|currency|exchange|rate)\b|\d+\s*[a-z]{3,7}\s+(to|in|into)\s+[a-z]{3,7}",
    "get_weather": r"\b(weather|temperature|forecast|rain|sunny|hot|cold)\b",
}
CITY = r"(?:in|at|for|of)\s+([a-z][a-z ]{1,30}?)(?=\s+(?:under|below|for|today|tomorrow|this|now|with|from|next|please|right)\b|[?.!,]|$)"


def intents(msg: str) -> list[str]:
    """Which tools does the message clearly ask for?"""
    found = [t for t, p in INTENTS.items() if re.search(p, msg, re.I)]
    if "book_hotel" in found and "search_hotels" in found:
        found.remove("search_hotels")  # "book hotel H05" is a booking, not a search
    return found


def _city(msg: str) -> str | None:
    m = re.search(CITY, msg, re.I)
    return m.group(1).strip().title() if m else None


def route(msg: str, only: str | None = None) -> tuple[str, dict] | None:
    """Pick a tool by keywords and extract basic args with regex. Returns None if nothing fits."""
    for tool in ([only] if only else intents(msg)):
        if tool == "cancel_booking" and (m := re.search(r"\bBK\d{4}\b", msg, re.I)):
            return tool, {"booking_id": m.group(0)}
        if tool == "list_bookings":
            return tool, {}
        if tool == "book_hotel":
            hid, dates = re.search(r"\bH\d{2}\b", msg, re.I), re.findall(r"\d{4}-\d{2}-\d{2}", msg)
            name = re.search(r"\bfor\s+([A-Z][a-z]+)", msg)
            guests = re.search(r"(\d+)\s+(?:guests?|people|persons|adults)", msg, re.I)
            if hid and len(dates) >= 2 and name:
                return tool, {"hotel_id": hid.group(0), "guest_name": name.group(1), "check_in": dates[0],
                              "check_out": dates[1], "guests": int(guests.group(1)) if guests else 1}
        if tool == "search_hotels" and (city := _city(msg)):
            price = re.search(r"(?:under|below|less than|max)\s*(?:rs\.?|inr|₹)?\s*(\d+)", msg, re.I)
            guests = re.search(r"(\d+)\s+(?:guests?|people|persons|adults)", msg, re.I)
            return tool, {"city": city, "max_price_per_night": int(price.group(1)) if price else None,
                          "guests": int(guests.group(1)) if guests else 1}
        if tool == "convert_currency" and (m := re.search(r"(\d+(?:\.\d+)?)\s*([a-z]{3,7})\s+(?:to|in|into)\s+([a-z]{3,7})", msg, re.I)):
            return tool, {"amount": float(m.group(1)), "from_currency": m.group(2), "to_currency": m.group(3)}
        if tool == "get_weather" and (city := _city(msg)):
            return tool, {"city": city}
    return None
