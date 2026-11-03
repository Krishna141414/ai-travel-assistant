"""Precompute the showcase examples with the real pipeline -> web/demo_data.json (instant demo mode).
Uses a temporary bookings file so data/ is untouched."""
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import assistant
import tools

EXAMPLES = [  # (id, group, button label, request, simulate outage)
    ("weather", "tools", "Weather -> real API", "What's the weather in Jaipur today?", False),
    ("currency", "tools", "Currency -> live rates", "Convert 250 USD to INR", False),
    ("hotels", "tools", "Hotel search -> local data", "Find hotels in Goa under 6000 per night for 2 guests", False),
    ("list", "tools", "List bookings", "Show my bookings", False),
    ("book", "tools", "Booking -> needs Confirm", "Book hotel H05 for Krishna from 2026-12-20 to 2026-12-23 for 2 guests", False),
    ("cancel", "tools", "Cancel -> needs Confirm", "Cancel booking BK1001", False),
    ("badcity", "errors", "Unknown city -> clear error", "What's the weather in Qwertyville?", False),
    ("baddates", "errors", "Bad dates -> rejected", "Book hotel H05 for Ravi from 2026-12-25 to 2026-12-20 for 2 guests", False),
    ("outage", "errors", "API down -> cached rates", "Convert 100 EUR to INR", True),
    ("invalid", "errors", "Invalid request -> polite refusal", "Book me a flight to Mars", False),
]


def main():
    tools.BOOKINGS_PATH = Path(tempfile.mkdtemp()) / "bookings.json"
    out = []
    for ex_id, group, label, msg, outage in EXAMPLES:
        r = assistant.handle(msg, simulate_outage=outage)
        if r["pending"]:  # precompute what Confirm would return
            r["confirmed"] = assistant.confirm(r["pending"]["id"], True)
        out.append({"id": ex_id, "group": group, "label": label, "simulate_outage": outage, **r})
        print(f"{ex_id:9} {r['elapsed_s']:>5}s  {r['answer'][:80]}")
    Path("web").mkdir(exist_ok=True)
    Path("web/demo_data.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
