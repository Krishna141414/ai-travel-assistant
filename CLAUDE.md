# Task 10: AI Travel Assistant with Tool Calling (VoidMain Internship)

## Goal
Brief: "Develop an AI assistant capable of interacting with application functions and external services. Implement multiple meaningful tools/functions. Allow the model to select appropriate tools and arguments, execute them safely and use results in the final response. Include validation, error handling and confirmation for important actions."
**Keep it SIMPLE and clean: small Python modules + one simple local chat page + README. Runs locally only, no deployment, no API keys, no test suite.**

## Setup
- Windows, Python 3.14, project in OneDrive. Keep `.venv` and model cache out of git. Empty `screenshots/.gitkeep`.
- Install the **CPU-only PyTorch build** (`pip install torch --index-url https://download.pytorch.org/whl/cpu`) - NOT CUDA. Plus `transformers`, `pydantic`, `requests`, `flask`. Pin `requirements.txt`.
- LLM: reuse the small instruct model already in `%USERPROFILE%\.cache\huggingface\hub` (e.g. Qwen2.5-0.5B-Instruct). **Do not download any other LLM.**
- Make tool selection reliable for a small model: the prompt lists the tools with their arguments, asks for ONLY a JSON object `{"tool": ..., "args": {...}}` (or `{"tool": "none", "answer": ...}`), and includes one short example per tool. Low temperature.
- **Fallback router:** if the model's choice is still invalid after 1 retry, a simple keyword-based router picks the tool (weather/currency/hotel/book/cancel/list) and extracts basic args with regex; mark these results as "fallback" so it's visible.

## Tools (`tools.py`, each with a Pydantic argument schema)
1. `get_weather(city)` - real data from Open-Meteo (geocoding + forecast, free, no key). Timeout + 1 retry; clear error if city not found.
2. `convert_currency(amount, from_currency, to_currency)` - real rates from a free no-key API (e.g. Frankfurter); fallback to a small cached rates table if the API fails, and say so in the result.
3. `search_hotels(city, max_price_per_night, guests)` - from a small local `data/hotels.json` (~20 sample hotels in Indian cities, marked as sample data).
4. `book_hotel(hotel_id, guest_name, check_in, check_out, guests)` - **important action: requires user confirmation**; validates dates (future, check_out after check_in) and capacity; saves to `data/bookings.json`.
5. `cancel_booking(booking_id)` - **important action: requires confirmation**.
6. `list_bookings()`.

## Assistant loop (`assistant.py`)
- Send user message + tool definitions to the model -> parse the tool call (name + JSON args).
- **Validation:** unknown tool, malformed JSON or invalid args -> error sent back to the model, 1 retry; then a polite failure message.
- **Safe execution:** only whitelisted tools; max 3 tool calls per user message; catch all exceptions and return readable errors.
- **Confirmation:** for book/cancel, don't execute - return a "pending confirmation" with a summary; execute only after the user clicks Confirm.
- Model uses tool results to write the final answer.

## Web app (`app.py` Flask + `templates/index.html`, inline CSS/JS)
- Simple chat UI with example prompt chips (weather, currency, hotel search, booking, cancel, one invalid request).
- Each tool call shown as a small card: tool name, arguments, result or error.
- Booking/cancel shows a confirmation card with **Confirm / Cancel** buttons.
- Look: dark navy `#0B1020`, gradient header (electric blue `#4F7CFF` -> neon pink `#FF3D81`), marigold `#FFB020` and mint `#22D3B6` accents, rounded cards, responsive.

## Quick check (`evaluate.py`)
- ~12 test requests -> record: correct tool chosen (by model vs by fallback), args valid, error handled, confirmation triggered when needed. Save `results.md` with a small table.

## README
Use case, tools list, how the model selects tools, validation/error handling/confirmation flow (text diagram), results table, limitations (small local model, sample hotel data), how to run.

## Rules
- Do everything in one go without asking. Keep code short and commented.
- Run `evaluate.py`, start the app and try a weather question and a booking with confirmation, then commit and push.
- Finish with a SHORT summary: results table + how to run. Then stop.


## Web page: follow SHOWCASE.md
- SHOWCASE.md (in this folder) defines the web page. It overrides any web-page details above (keep the same features, presented as SHOWCASE.md describes).
