# Evaluation results

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
