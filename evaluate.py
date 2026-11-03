"""Quick check: 12 requests -> tool chosen (model vs fallback), args valid, errors handled, confirmations.
Writes results.md and web/results.json. Uses a temporary bookings file so data/ is untouched."""
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import assistant
import tools

# (request, expected tool, expect confirmation, expect a handled error/fallback, simulate API outage)
CASES = [
    ("What's the weather in Jaipur today?", "get_weather", False, False, False),
    ("Is it going to rain in Mumbai this week?", "get_weather", False, False, False),
    ("Convert 250 USD to INR", "convert_currency", False, False, False),
    ("How much is 50 euros in rupees?", "convert_currency", False, False, False),
    ("Find hotels in Goa under 6000 per night for 2 guests", "search_hotels", False, False, False),
    ("Show my bookings", "list_bookings", False, False, False),
    ("Book hotel H05 for Krishna from 2026-12-20 to 2026-12-23 for 2 guests", "book_hotel", True, False, False),
    ("Cancel booking BK1001", "cancel_booking", True, False, False),
    ("What's the weather in Qwertyville?", "get_weather", False, True, False),
    ("Book hotel H05 for Ravi from 2026-12-25 to 2026-12-20 for 2 guests", "book_hotel", False, True, False),
    ("Convert 100 EUR to INR", "convert_currency", False, True, True),
    ("Book me a flight to Mars", "none", False, True, False),
]


def main():
    tools.BOOKINGS_PATH = Path(tempfile.mkdtemp()) / "bookings.json"
    rows = []
    for msg, expected, want_confirm, want_error, outage in CASES:
        r = assistant.handle(msg, simulate_outage=outage)
        c = r["calls"][0] if r["calls"] else None
        tool = c["tool"] if c else "none"
        source = c["source"] if c else ("polite failure" if r["answered_by"] == "polite failure" else "model")
        confirmed = r["pending"] is not None
        handled = bool((c and c["status"] == "error") or (c and (c.get("result") or {}).get("note"))
                       or r["answered_by"] == "polite failure" or (not c and r["answer"]))
        saved = ""
        if confirmed:  # nothing saved yet -> Confirm -> now saved
            before = json.dumps(tools.list_bookings(tools.ListArgs()))
            done = assistant.confirm(r["pending"]["id"], True)
            saved = "saved after Confirm" if done["status"] == "done" and json.dumps(
                tools.list_bookings(tools.ListArgs())) != before else "NOT saved"
        rows.append({
            "request": msg, "expected": expected, "chosen": tool, "source": source,
            "tool_ok": tool == expected, "args_valid": bool(c) or expected == "none",
            "error_expected": want_error, "error_handled": handled if want_error else None,
            "confirm_expected": want_confirm, "confirm_ok": confirmed == want_confirm, "saved": saved,
            "error": (c or {}).get("error") or (c and (c.get("result") or {}).get("note")) or "",
            "answer": r["answer"], "seconds": r["elapsed_s"],
        })
        print(f"{tool:16} {source:14} ok={tool == expected} {r['elapsed_s']:>5}s  {msg}")

    n = len(rows)
    summary = {
        "total": n, "tool_correct": sum(r["tool_ok"] for r in rows),
        "by_model": sum(r["source"].startswith("model") for r in rows),
        "by_model_retry": sum(r["source"] == "model (retry)" for r in rows),
        "by_fallback": sum(r["source"] == "fallback" for r in rows),
        "polite_failure": sum(r["source"] == "polite failure" for r in rows),
        "args_valid": sum(r["args_valid"] for r in rows),
        "errors_expected": sum(r["error_expected"] for r in rows),
        "errors_handled": sum(bool(r["error_handled"]) for r in rows),
        "confirm_expected": sum(r["confirm_expected"] for r in rows),
        "confirm_triggered": sum(r["confirm_expected"] and r["confirm_ok"] for r in rows),
        "confirm_ok_all": sum(r["confirm_ok"] for r in rows),
        "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 1),
    }
    Path("web").mkdir(exist_ok=True)
    Path("web/results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")

    yes = lambda b: "yes" if b else "**no**"
    lines = ["# Evaluation results", "", f"Model: `{assistant.MODEL_ID}` (CPU, greedy). Run `python evaluate.py` to reproduce.", "",
             "| # | Request | Expected | Chosen | Picked by | Tool ok | Args valid | Error handled | Confirmation |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        err = "-" if r["error_handled"] is None else yes(r["error_handled"])
        conf = (f"yes, {r['saved']}" if r["confirm_expected"] and r["confirm_ok"] else
                "-" if r["confirm_ok"] else "**wrong**")
        lines.append(f"| {i} | {r['request']} | {r['expected']} | {r['chosen']} | {r['source']} | {yes(r['tool_ok'])} | "
                     f"{yes(r['args_valid'])} | {err} | {conf} |")
    s = summary
    lines += ["", f"- Correct tool: **{s['tool_correct']}/{n}**",
              f"- Picked by model: {s['by_model']} (of which after retry: {s['by_model_retry']}), by fallback router: {s['by_fallback']}, polite failure: {s['polite_failure']}",
              f"- Errors handled: {s['errors_handled']}/{s['errors_expected']}",
              f"- Confirmations triggered: {s['confirm_triggered']}/{s['confirm_expected']} (no confirmation on any other request: {s['confirm_ok_all'] == n})",
              f"- Average time per request: {s['avg_seconds']} s"]
    Path("results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-5:]))


if __name__ == "__main__":
    main()
