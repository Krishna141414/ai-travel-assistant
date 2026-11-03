# SHOWCASE.md - Showcase web page spec (follow exactly)

Goal: ONE polished, animated web page that walks a viewer through **what this task asks and how this project does each part**. It's for a video demo, so it must look good and explain itself. Read this project's CLAUDE.md for the task brief.

## Sections (top to bottom)
1. **Hero:** animated gradient background (electric blue `#4F7CFF` -> neon pink `#FF3D81`), a "Task N - <task name>" badge, the project title, ONE plain-English sentence about what it does, and a "Start demo" button that scrolls down.
2. **"What this task asks" - requirement cards:** split the task brief into its requirements (one card each, with an icon + one line on how this project does it). Clicking a card smooth-scrolls to the demo step that covers it. Each card gets an animated check mark once the demo has shown that step.
3. **Live demo - animated pipeline:**
   - 3-6 labelled example buttons, each saying what it demonstrates (e.g. "Clean input -> success", "Unanswerable -> refused", "Broken output -> retry").
   - A horizontal step bar of the pipeline (e.g. Input -> Process -> Validate -> Output). On run, the steps light up **one after another** (glow + flowing progress line), and each step reveals its intermediate result under it with a fade/slide (e.g. tokens, chunks, scores as animated bars, chosen tool, validation errors, final answer). Use a short delay between steps so a viewer can follow, even when the result is instant.
   - LLM text appears with a typing effect.
   - The final result is shown as a clean, readable card. Raw JSON / prompts / model output go in a collapsed "Show technical details" panel.
4. **Results:** the project's evaluation numbers as count-up stat tiles + 1-2 animated Chart.js charts + the comparison table, plus 3-5 short "key findings" bullets.
5. **How it works:** a simple flow diagram (HTML/CSS boxes and arrows) + 2-4 short key code snippets (the most important functions, with file names) in styled code blocks.
6. **Limitations:** 3-5 honest bullets. Footer: author Krishna, GitHub link.

## Behaviour
- **Instant demo mode (default):** precompute the outputs for every example button into `web/demo_data.json` (or similar) with a script, so the page works instantly and without the model. This also lets the page be deployed as a free static site.
- **"Run live" toggle:** only when the local backend is running (`python app.py`), send the user's own input to the real pipeline/model. Show "Working... (CPU model, ~10-30 s)" with a spinner. If the backend isn't available, hide the toggle gracefully.
- For tasks with no model (e.g. a static classifier demo), keep whatever already runs in the browser and just apply this layout and the animations.

## Unique identity per task (every page must look different)
Use THIS project's row below for the palette, hero animation and signature demo visual. Never reuse another task's look.

| Task | Theme / palette | Hero animation | Signature demo visual |
|---|---|---|---|
| 5 Prompt engineering | "Prompt Lab" - deep purple `#120A24`, violet `#8B5CF6`, hot pink `#F472B6`, lime `#A3E635` | floating token chips | prompt strategies as side-by-side cards; tokens highlighted as colored chips; temperature slider morphing the output |
| 6 Structured extraction | "Data Refinery" - charcoal `#0F1115`, amber `#F59E0B`, emerald `#10B981`, red `#EF4444` | messy text "assembling" into a JSON card | email text scanned by a highlight line, fields flying into a form card; validation as pass/fail stamps; retry/fallback as a conveyor loop |
| 7 Semantic search | "Vector Space" - space black `#05070F`, cyan `#22D3EE`, indigo `#6366F1`, gold `#FBBF24` | drifting starfield of dots (embeddings) | query appears as a star, nearest chunks light up and connect; semantic vs keyword results race side by side |
| 8 RAG | "Travel Library" - warm dark teal `#0A1F1E`, turquoise `#14B8A6`, saffron `#F97316`, cream `#FDE68A` | map-like route lines connecting places | question -> retrieved source cards slide in -> prompt built from numbered chunks -> answer types out with clickable [1] [2] citations |
| 9 Advanced RAG | "Optimizer" - midnight `#0B1020`, electric blue `#4F7CFF`, neon pink `#FF3D81`, mint `#22D3B6` | animated before/after split | baseline vs advanced lanes; results reorder visually during reranking; filter chips narrowing the pool; before/after metric bars |
| 10 Tool calling | "Agent Console" - graphite `#111827`, green `#22C55E`, sky `#38BDF8`, orange `#FB923C` | blinking terminal cursor + tool icons orbiting | chat on the left, live "agent trace" on the right: tool picked -> args validated -> API called -> result; confirmation as a modal with Confirm/Cancel |

## Look and feel
- Use the palette from your task's row (dark background, 3 accents; red/pink for errors/failed states).
- Google Font Inter (or similar), glassy rounded cards, soft neon glow on active elements, generous spacing.
- Animations: fade/slide-in on scroll (IntersectionObserver), animated bars, count-up numbers, step-by-step pipeline glow, typing effect. Smooth, never noisy. Respect `prefers-reduced-motion`.
- Responsive (looks fine at phone width). Plain HTML/CSS/JS + Chart.js from CDN. No frameworks, no build step.

## Done means
- Start the page yourself and actually load it with real requests (and the live backend if it exists). Click/trigger every example. No errors in the server log. Don't say it works unless you saw real responses.
- README gets a "Showcase page" section: how to open it (and live link if deployed).
- Commit and push. Short summary: what the page shows + how to open it. Then stop.
