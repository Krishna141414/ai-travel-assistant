"""Assistant loop: model picks a tool as JSON -> validate (1 retry) -> fallback router -> safe execution
-> confirmation for important actions -> model writes the final answer from the tool results."""
import json
import re
import threading
import time
import uuid
from datetime import date

from pydantic import ValidationError

import router
import tools

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"  # already in the local HF cache, loaded offline
MAX_TOOL_CALLS = 3
PENDING: dict[str, dict] = {}  # confirmation id -> {"tool", "args"}

SYSTEM = """You are a travel assistant that chooses a tool. Today is {today}.
Tools:
- get_weather(city): current weather and 3-day forecast.
- convert_currency(amount, from_currency, to_currency): convert money; currencies are 3-letter codes (USD, INR, EUR).
- search_hotels(city, max_price_per_night, guests): find hotels; price in INR or null.
- book_hotel(hotel_id, guest_name, check_in, check_out, guests): book a hotel; hotel_id like "H05", dates YYYY-MM-DD.
- cancel_booking(booking_id): cancel a booking; booking_id like "BK1001".
- list_bookings(): show all bookings.
Reply with ONLY one JSON object and nothing else: {{"tool": "<name>", "args": {{...}}}}
If no tool fits, reply: {{"tool": "none", "answer": "<one short sentence>"}}
Examples:
User: What's the weather like in London?
{{"tool": "get_weather", "args": {{"city": "London"}}}}
User: Convert 40 GBP to USD
{{"tool": "convert_currency", "args": {{"amount": 40, "from_currency": "GBP", "to_currency": "USD"}}}}
User: Hotels in Delhi under 5000 for 3 guests
{{"tool": "search_hotels", "args": {{"city": "Delhi", "max_price_per_night": 5000, "guests": 3}}}}
User: Book hotel H12 for Meera from 2027-01-05 to 2027-01-08 for 1 guest
{{"tool": "book_hotel", "args": {{"hotel_id": "H12", "guest_name": "Meera", "check_in": "2027-01-05", "check_out": "2027-01-08", "guests": 1}}}}
User: Please cancel BK1234
{{"tool": "cancel_booking", "args": {{"booking_id": "BK1234"}}}}
User: What bookings do I have?
{{"tool": "list_bookings", "args": {{}}}}
User: Tell me a joke
{{"tool": "none", "answer": "I can only help with weather, currency and hotels."}}"""

ANSWER_SYSTEM = """You are a friendly travel assistant. Answer the user in 2-3 short sentences using ONLY the tool
results given. Copy numbers exactly from the results. If a tool returned an error, explain it simply and suggest
a fix. If a result has a "note", mention it. Do not output JSON."""

_tok = _model = None
_lock = threading.Lock()


def load():
    """Load the local model once (CPU, offline)."""
    global _tok, _model
    if _model is None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(MODEL_ID, local_files_only=True)
        _model = AutoModelForCausalLM.from_pretrained(MODEL_ID, local_files_only=True, dtype=torch.float32)
        _model.eval()


def generate(messages: list[dict], max_new_tokens: int = 120) -> str:
    """Greedy (temperature 0) generation for stable tool choices."""
    import torch
    load()
    with _lock:
        text = _tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        ids = _tok(text, return_tensors="pt")
        with torch.no_grad():
            out = _model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False, temperature=None,
                                  top_p=None, top_k=None, pad_token_id=_tok.eos_token_id)
        return _tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def parse_call(text: str) -> dict:
    """Extract the first {...} JSON object from the model output."""
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if depth == 0:
            try:
                obj = json.loads(text[start:i + 1])
            except json.JSONDecodeError as e:
                raise ValueError(f"malformed JSON ({e.msg})")
            if not isinstance(obj, dict) or "tool" not in obj:
                raise ValueError('JSON must have a "tool" key')
            return obj
    raise ValueError("malformed JSON (unbalanced braces)")


def validate(obj: dict, message: str, needed: list[str]) -> tuple[str, object]:
    """Check tool name against the whitelist and args against its Pydantic schema."""
    tool = obj.get("tool")
    if tool == "none":
        if needed:  # the request clearly needs a tool - don't let the model answer from memory
            raise ValueError(f"this request needs a tool ({', '.join(needed)})")
        return "none", str(obj.get("answer") or "Sorry, I can't help with that.")
    if tool not in tools.TOOLS:
        raise ValueError(f"unknown tool '{tool}'. Allowed: {', '.join(tools.TOOLS)}, none")
    args = obj.get("args") or {}
    if not isinstance(args, dict):
        raise ValueError('"args" must be an object')
    try:
        return tool, tools.TOOLS[tool]["schema"](**args)
    except ValidationError as e:
        raise ValueError("invalid args: " + "; ".join(f"{'.'.join(map(str, x['loc'])) or 'args'}: {x['msg']}"
                                                      for x in e.errors()))


def choose_tool(message: str, history: list[dict], needed: list[str], only: str | None = None) -> dict:
    """Ask the model (1 retry with the error), then fall back to the keyword router."""
    msgs = [{"role": "system", "content": SYSTEM.format(today=date.today())},
            {"role": "user", "content": message}] + history
    attempts = []
    for attempt in range(2):
        t = time.time()
        raw = generate(msgs)
        try:
            tool, args = validate(parse_call(raw), message, needed)
            if only and tool != only:
                raise ValueError(f"the next step should be {only}")
            attempts.append({"by": "model", "raw": raw, "ok": True, "ms": int((time.time() - t) * 1000)})
            return {"tool": tool, "args": args, "source": "model" if attempt == 0 else "model (retry)", "attempts": attempts}
        except ValueError as e:
            attempts.append({"by": "model", "raw": raw, "ok": False, "error": str(e), "ms": int((time.time() - t) * 1000)})
            msgs += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": f"Error: {e}. Reply with ONLY the corrected JSON object."}]
    routed = router.route(message, only)
    if routed:
        try:
            tool, args = validate({"tool": routed[0], "args": routed[1]}, message, needed)
            attempts.append({"by": "fallback", "raw": json.dumps({"tool": routed[0], "args": routed[1]}), "ok": True})
            return {"tool": tool, "args": args, "source": "fallback", "attempts": attempts}
        except ValueError as e:
            attempts.append({"by": "fallback", "raw": json.dumps({"tool": routed[0], "args": routed[1]}), "ok": False, "error": str(e)})
    return {"tool": None, "args": None, "source": None, "attempts": attempts}


def run_tool(tool: str, args, fn_key: str = "fn") -> dict:
    """Safe execution: whitelist check + catch every exception as a readable error."""
    if tool not in tools.TOOLS:
        return {"ok": False, "error": f"tool '{tool}' is not whitelisted", "ms": 0}
    t = time.time()
    try:
        result = tools.TOOLS[tool][fn_key](args)
        return {"ok": True, "result": result, "ms": int((time.time() - t) * 1000)}
    except tools.ToolError as e:
        return {"ok": False, "error": str(e), "ms": int((time.time() - t) * 1000)}
    except Exception as e:  # never crash the chat
        return {"ok": False, "error": f"internal error: {type(e).__name__}: {e}", "ms": int((time.time() - t) * 1000)}


def final_answer(message: str, calls: list[dict]) -> str:
    """Model writes the reply from the tool results."""
    results = [{"tool": c["tool"], **({"result": {k: v for k, v in c["result"].items() if v is not None}}
                if c["status"] == "ok" else {"error": c["error"]})} for c in calls]
    text = generate([{"role": "system", "content": ANSWER_SYSTEM},
                     {"role": "user", "content": f"User request: {message}\nTool results:\n{json.dumps(results, default=str)}"}],
                    max_new_tokens=140)
    return text or "Here are the results from the tools."


def handle(message: str, simulate_outage: bool = False) -> dict:
    """One user message -> up to MAX_TOOL_CALLS tool calls -> answer (or a pending confirmation)."""
    t0 = time.time()
    message = message.strip()[:500]
    needed, calls, history, pending, answer, answered_by = router.intents(message), [], [], None, None, "model"
    failed = []  # model attempts when no tool call happened (shown in the trace)
    tools.SIMULATE_OUTAGE = simulate_outage
    try:
        while len(calls) < MAX_TOOL_CALLS:
            remaining = [t for t in needed if t not in {c["tool"] for c in calls}]
            if calls and not remaining:
                break
            choice = choose_tool(message, history, remaining, only=remaining[0] if calls else None)
            if choice["tool"] is None:  # still invalid after retry + fallback
                if not calls:
                    failed = choice["attempts"]
                    answer, answered_by = ("Sorry, I can't do that. I can check weather, convert currency, and "
                                           "search, book, list or cancel hotel bookings."), "polite failure"
                break
            if choice["tool"] == "none":
                failed, answer = choice["attempts"], choice["args"]
                break
            tool, args = choice["tool"], choice["args"]
            call = {"tool": tool, "args": args.model_dump(mode="json"), "source": choice["source"],
                    "attempts": choice["attempts"], "whitelisted": tool in tools.TOOLS}
            if tools.TOOLS[tool]["confirm"]:  # important action: preview only, never execute here
                r = run_tool(tool, args, "confirm")
                if r["ok"]:
                    pid = uuid.uuid4().hex[:8]
                    PENDING[pid] = {"tool": tool, "args": args}
                    pending = {"id": pid, "tool": tool, "summary": r["result"]}
                    call.update(status="pending", result=r["result"], stage="confirm", ms=r["ms"])
                else:
                    call.update(status="error", error=r["error"], stage="validate", ms=r["ms"])
            else:
                r = run_tool(tool, args)
                call.update(status="ok" if r["ok"] else "error", result=r.get("result"), error=r.get("error"),
                            stage="execute", ms=r["ms"])
            calls.append(call)
            if call["status"] != "ok":
                break  # stop on errors and pending confirmations
            history += [{"role": "assistant", "content": json.dumps({"tool": tool, "args": call["args"]})},
                        {"role": "user", "content": "Tool result received. Reply with the JSON for the next tool."}]
    finally:
        tools.SIMULATE_OUTAGE = False
    if pending:
        s = pending["summary"]
        answer, answered_by = (f"Please confirm: book {s['hotel_name']} ({s['city']}) for {s['guest_name']}, "
                               f"{s['check_in']} -> {s['check_out']}, {s['guests']} guest(s), {s['nights']} nights, "
                               f"total INR {s['total_inr']:,}." if pending["tool"] == "book_hotel" else
                               f"Please confirm: cancel booking {s['booking_id']} at {s['hotel_name']} for "
                               f"{s['guest_name']} ({s['check_in']} -> {s['check_out']})."), "template"
    elif calls and calls[-1]["status"] == "error":
        # Errors are reported verbatim - a small model can misreport a failure as a success.
        answer, answered_by = f"Sorry, I couldn't do that: {calls[-1]['error']}.", "template (error)"
    elif calls:
        answer = final_answer(message, calls)
        notes = [c["result"]["note"] for c in calls if c["result"].get("note")]
        if notes:  # always surface fallbacks (e.g. cached rates), whatever the model wrote
            answer += " Note: " + " ".join(notes)
    return {"message": message, "calls": calls, "pending": pending, "answer": answer, "answered_by": answered_by,
            "choice_attempts": failed, "elapsed_s": round(time.time() - t0, 2)}


def confirm(pid: str, approve: bool) -> dict:
    """Execute (or drop) a pending important action. Nothing is saved before this."""
    p = PENDING.pop(pid, None)
    if not p:
        return {"status": "error", "error": "this confirmation expired or was already used", "answer": "Nothing was changed."}
    if not approve:
        return {"status": "cancelled", "answer": "Okay, cancelled - nothing was saved."}
    r = run_tool(p["tool"], p["args"])
    if not r["ok"]:
        return {"status": "error", "error": r["error"], "answer": f"Could not complete it: {r['error']}."}
    b = r["result"]
    answer = (f"Booked! Your booking id is {b['booking_id']}: {b['hotel_name']}, {b['check_in']} -> {b['check_out']}, "
              f"total INR {b['total_inr']:,}." if p["tool"] == "book_hotel" else
              f"Done - booking {b['booking_id']} is now cancelled.")
    return {"status": "done", "tool": p["tool"], "result": b, "ms": r["ms"], "answer": answer}
