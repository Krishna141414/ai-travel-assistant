# AI Travel Assistant with Tool Calling (Task 10)

A local AI travel assistant. A small instruct model (**Qwen2.5-0.5B-Instruct**, CPU, offline) reads a request,
picks a tool and its arguments as JSON, the app validates and runs the tool safely, and the model writes the
answer from the real result. Booking and cancelling **always ask for confirmation first**.

## Use case
"What's the weather in Jaipur?", "Convert 250 USD to INR", "Find hotels in Goa under 6000 for 2 guests",
"Book hotel H05 for Krishna from 2026-12-20 to 2026-12-23", "Cancel booking BK1001", "Show my bookings".

## Tools (`tools.py`, each with a Pydantic argument schema)
| Tool | Args | Source |
|---|---|---|
| `get_weather` | city | Open-Meteo geocoding + forecast (live, no key), timeout + 1 retry, clear "city not found" error |
| `convert_currency` | amount, from_currency, to_currency | Frankfurter (live, no key); falls back to a small cached table and says so |
| `search_hotels` | city, max_price_per_night, guests | `data/hotels.json` (20 **sample** hotels in Indian cities) |
| `book_hotel` | hotel_id, guest_name, check_in, check_out, guests | **needs confirmation**; checks future dates, order, max 30 nights, capacity; saves to `data/bookings.json` |
| `cancel_booking` | booking_id | **needs confirmation**; booking must exist and not be cancelled |
| `list_bookings` | - | `data/bookings.json` (created on first use with one sample booking, BK1001) |

## How the model selects tools
The system prompt (`assistant.py`) lists the 6 tools with their arguments, asks for **ONLY** one JSON object
`{"tool": ..., "args": {...}}` (or `{"tool": "none", "answer": ...}`) and gives one short example per tool.
Generation is greedy (temperature 0). The first `{...}` in the output is parsed.

If the reply is still invalid after 1 retry, a **keyword + regex fallback router** (`router.py`) picks the tool
and extracts basic args. Such calls are marked `"source": "fallback"` everywhere (trace, results table).

## Validation, error handling and confirmation
```
user message
   |
   v
LLM -> JSON {tool, args}
   |
   v
parse JSON + tool in whitelist + Pydantic schema --invalid--> error sent back to LLM, 1 retry
   |                                                             |  still invalid
   |                                                             v
   |                                                   fallback router ("fallback")
   |                                                             |  nothing fits
   |                                                             v
   |                                                   polite failure message
   v
important action (book / cancel)? --yes--> preview + business rules --> "pending confirmation" card
   | no                                                                     |
   v                                                          Confirm -> execute + save
execute safely: whitelist, timeout + 1 retry,                 Cancel  -> nothing saved
try/except -> readable error, max 3 tool calls/message
   |
   v
LLM writes the final answer from the tool results
(errors: fixed template with the exact error; fallback notes always appended)
```
- Schemas check **format** (types, `H05`, `BK1001`, 3-letter codes). **Business rules** (dates in the future,
  check-out after check-in, capacity, booking exists) are checked in the tool and reported to the user -
  so the model can't silently "fix" a user's bad dates on retry.
- If the request clearly needs a tool but the model answers `"none"`, that is treated as invalid (no answering
  weather from memory).
- A `simulate_outage` switch points the currency tool at a dead address to demo the cached-rates fallback.

## Results (`python evaluate.py` -> `results.md`)
Model: `Qwen/Qwen2.5-0.5B-Instruct` (CPU, greedy). Run `python evaluate.py` to reproduce.

| # | Request | Expected | Chosen | Picked by | Tool ok | Args valid | Error handled | Confirmation |
|---|---|---|---|---|---|---|---|---|
| 1 | What's the weather in Jaipur today? | get_weather | get_weather | model | yes | yes | - | - |
| 2 | Is it going to rain in Mumbai this week? | get_weather | get_weather | model | yes | yes | - | - |
| 3 | Convert 250 USD to INR | convert_currency | convert_currency | model | yes | yes | - | - |
| 4 | How much is 50 euros in rupees? | convert_currency | convert_currency | model | yes | yes | - | - |
| 5 | Find hotels in Goa under 6000 per night for 2 guests | search_hotels | search_hotels | model | yes | yes | - | - |
| 6 | Show my bookings | list_bookings | list_bookings | model | yes | yes | - | - |
| 7 | Book hotel H05 for Krishna from 2026-12-20 to 2026-12-23 for 2 guests | book_hotel | book_hotel | model | yes | yes | - | yes, saved after Confirm |
| 8 | Cancel booking BK1001 | cancel_booking | cancel_booking | model | yes | yes | - | yes, saved after Confirm |
| 9 | What's the weather in Qwertyville? | get_weather | get_weather | model | yes | yes | yes | - |
| 10 | Book hotel H05 for Ravi from 2026-12-25 to 2026-12-20 for 2 guests | book_hotel | book_hotel | model | yes | yes | yes | - |
| 11 | Convert 100 EUR to INR | convert_currency | convert_currency | model | yes | yes | yes | - |
| 12 | Book me a flight to Mars | none | none | polite failure | yes | yes | yes | - |

- Correct tool: **12/12**
- Picked by model: 11 (of which after retry: 0), by fallback router: 0, polite failure: 1
- Errors handled: 4/4
- Confirmations triggered: 2/2 (no confirmation on any other request: True)
- Average time per request: 9.5 s

## Showcase page
`templates/index.html` is a single animated page (Task 10 "Agent Console" theme) that walks through the brief:
requirement cards with check marks, the 6 tools, a live demo (chat on the left, agent trace on the right:
tool picked -> args validated -> API called -> result -> answer, Confirm/Cancel modal for book/cancel),
results with stat tiles + charts + table, a flow diagram with key code, and limitations.

- **Instant replay (default):** `build_demo.py` records the real pipeline's outputs for 10 examples into
  `web/demo_data.json`, so the page works instantly without the model.
- **Run live:** when `python app.py` is running, a "Run live" toggle appears and sends your own requests to the
  local model (~10-30 s on CPU). Bookings confirmed live are saved to `data/bookings.json`.

Open it at http://127.0.0.1:5000 after starting `python app.py`.

## How to run
```powershell
python -m venv .venv
.\.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python app.py          # http://127.0.0.1:5000
.\.venv\Scripts\python evaluate.py     # writes results.md + web/results.json
.\.venv\Scripts\python build_demo.py   # refreshes web/demo_data.json
```
The model must already be in the Hugging Face cache (`Qwen/Qwen2.5-0.5B-Instruct`); it is loaded with
`local_files_only=True` and `HF_HUB_OFFLINE=1`, nothing is downloaded.

## Limitations
- Tiny CPU model: ~5-15 s per request, and it can pick wrong args - hence validation, retry and the fallback router.
- Hotels are fictional **sample data**; bookings are a local JSON file, no payments.
- The fallback router only understands plainly worded requests.
- Successful answers are written by the small model and can word things loosely (the result card shows the
  exact data). Errors use a fixed template because the model once described a rejected booking as "confirmed".
- Cached currency rates are approximate and only used (and labelled) when the live API fails.
- Example dates (Dec 2026) must stay in the future for the booking examples to pass.
