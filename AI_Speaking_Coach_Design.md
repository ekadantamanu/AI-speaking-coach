# AI Speaking Coach — Design Notes

Refined tool stack, engagement variety system, and daily-practice logic for a personal
speaking/presentation practice agent. Written as a working spec you can hand to yourself
(or an AI coding assistant) to build from.

---

## 1. Refined technical stack (better than the original suggestion)

| Layer | Original suggestion | Refined recommendation | Why |
|---|---|---|---|
| Speech-to-text | OpenAI Whisper API, $0.006/min | **faster-whisper**, run locally, $0/min | Same accuracy as Whisper (identical model weights), 4–8x faster, zero marginal cost once your machine can run it. No API dependency, no rate limits, works offline. If you'd rather not run anything locally: **AssemblyAI** ($50 free credit, then $0.0025/min) is the cheapest hosted fallback. |
| Prosody / vocal delivery | Praat / librosa | **openSMILE** | Purpose-built for paralinguistic feature extraction (pitch, energy, pause structure, voice quality) and easier to drive from Python than raw Parselmouth. Free, open-source, industry-standard in speech-emotion research. |
| Body language | MediaPipe | **MediaPipe (unchanged)** + optional **py-feat** or **DeepFace** layered on top | MediaPipe still wins for pose/gaze — free and best-in-class. Adding a facial-expression model gives you an "engagement/energy" signal (are you animated or flat) that pose data alone misses. |
| Qualitative feedback ("was this well-structured, did the argument land") | Claude/GPT API, ~$0.05–0.10/session | **Two-tier option**: (a) Claude Sonnet API — cheap and highest quality, still under $0.10/session; or (b) **Ollama running a local model (Llama 3, Mistral)** — genuinely $0/session forever, no internet dependency | Local models are noticeably weaker at nuanced rhetorical judgment than Claude/GPT, but if the prompt gives them a tight rubric (see §3) rather than an open-ended "critique this," the gap narrows a lot. Good default: use Claude for anything you'll act on seriously; use local for daily reps where a decent-not-perfect critique is enough. |

**The real quality lever isn't which model — it's the rubric.** A generic "give me feedback on this speech" prompt produces generic feedback regardless of model. What actually gets you Toastmasters-evaluator-quality feedback is an **LLM-as-judge** setup: a structured prompt that scores against fixed named criteria (opening hook, structure, filler-word rate, vocal variety signal from the prosody data, closing strength, one specific actionable fix), with a couple of worked examples of "good" vs "weak" feedback baked into the prompt so the model calibrates its tone and specificity. That's what turns a cheap model into something that feels like a real reviewer.

Total marginal cost per session with the local-first stack: **effectively $0**, aside from electricity. With the cloud-first stack: still under $0.10/session.

---

## 2. Why monotony kills these apps (and the fix)

Every AI speaking app that's just "random topic → speak → score" gets abandoned within 2–3 weeks, because it drills the same muscle every time and gives you the same three metrics back. Two separate things need variety, not one:

1. **The exercise format** — what kind of speaking task you're doing.
2. **The constraint** — what specific thing today's session is forcing you to practice.

Varying only the topic (which most apps do) isn't real variety — it's the same skill in a different costume. Varying the *format* and *constraint* is what actually builds a rounded speaker and avoids treadmill fatigue.

---

## 3. Engagement library — 10 distinct practice modes

Each mode trains a genuinely different skill, so rotating through them (rather than doing "impromptu topic" every day) is the core anti-monotony mechanism.

| Mode | Length | What it trains | Format |
|---|---|---|---|
| **Impromptu Sprint** | 60–90 sec | Fluency under zero prep, filler-word control | Random topic, no prep time, speak immediately |
| **Structured Persuasion** | 2–3 min | Argument construction | Random topic, must follow a forced structure (e.g. Point → Reason → Example → Point) |
| **Storytelling** | 2–4 min | Vocal variety, pacing, emotional arc | Personal-narrative prompt ("tell about a time you failed") |
| **Explain-It-Simply** | 60–90 sec | Clarity, simplification | Complex topic, must be explainable to a 10-year-old |
| **Debate + Rebuttal** | 90 sec + 45 sec | Quick thinking under pushback | Argue a stance, then the agent generates a counter-argument you must rebut immediately, unscripted |
| **Elevator Pitch** | Hard 30–60 sec cap | Conciseness, strong open/close | Fixed, tight time constraint — going over or well under is scored |
| **Full Presentation** | 5–10 min | End-to-end structure, transitions, slide-to-speech sync | You bring (or the agent generates) a 3–5 slide outline, deliver as a full talk |
| **Q&A Stress Test** | 3 questions, unscripted | Handling the unpredictable | Runs right after Full Presentation — agent asks 3 follow-up questions live, no prep |
| **Vocal Drill** | 3–5 min | Pure mechanics: pace, pitch range, pause control | Read-aloud passage — removes content-generation stress so you can isolate delivery |
| **Body Language Mirror** | 2 min | Posture, eye contact, gesture presence | Video-only scoring pass, low content pressure, minimal talking required |

---

## 4. Constraint layer (stacked on top of any mode)

Pick one constraint per session, randomized or targeted at a weak area, to keep even a repeated format from feeling identical:

- A banned filler word or crutch phrase for the session
- A required rhetorical device (rule of three, callback to the opening, a rhetorical question)
- A specific emotion to convey (urgency, humor, warmth, gravity)
- A forced opening line style (a question, a statistic, a short story)
- An audience persona to address differently each time (skeptical exec, curious beginner, hostile critic)
- A hard time ceiling that's tighter than usual (compress a normally 2-min task into 75 seconds)

---

## 5. The actual anti-monotony engine: adaptive targeting, not randomness

Pure randomness feels varied for a week, then starts feeling arbitrary. The differentiator that actually works long-term is having the agent **track a rolling skill profile** from every session's metrics — filler-word rate trend, pace (WPM) variance, pause distribution, structure score, vocal-variety score, engagement/gesture score — and use that profile to choose what you practice next, the way a strength coach programs around your weakest lift rather than repeating a random exercise list.

Two selection strategies, both worth keeping active:

- **Weakness-targeted (70% of sessions)**: the agent looks at your last 5–10 sessions, identifies your worst-trending metric (say, filler-word rate creeping up under time pressure), and serves a mode + constraint combination designed to hit exactly that (e.g. Impromptu Sprint with a banned-filler-word constraint).
- **Deliberate novelty (30% of sessions)**: the agent forces a mode you haven't done in the last N sessions, regardless of your scores, purely to prevent stagnation and keep the whole skill set fresh — this is where the "explore" budget lives.

This is what separates "vigorous, varied practice" from a slot machine of random topics: the variety has direction.

---

## 6. Configurable daily session builder

Let yourself set **sessions-per-day (1–6)** and the agent builds a queue, not a random pull, following a simple template so a 1-session day and a 5-session day both feel coherent rather than arbitrary:

- **1 session/day** → one weakness-targeted mode, medium length (2–3 min). Minimum viable habit.
- **2 sessions/day** → one short warm-up (Impromptu Sprint or Vocal Drill, low stakes) + one weakness-targeted main session.
- **3 sessions/day** → warm-up + weakness-targeted main + one novelty mode (keeps it from feeling like a grind).
- **4–5 sessions/day** → warm-up + two weakness-targeted (different metrics) + one novelty + one stress test (Debate/Rebuttal or Q&A Stress Test) to end on the hardest rep.
- **6 sessions/day** → full rotation across the day: warm-up, two weakness-targeted, one novelty, one full presentation + Q&A pair, one vocal drill cool-down.

Total daily time stays proportional to session count (roughly 3–5 min per session including feedback review), so this scales from a 5-minute habit to a 30-minute intensive day without you having to hand-pick exercises yourself.

---

## 7. Feedback delivery — what "high quality" should actually look like

Per session, the report should give you, in order: one thing that worked (name it specifically, not "good job"), the single most important thing to fix (not five — one, prioritized), the raw numbers (filler rate, WPM, pause count, eye-contact %), and a one-line comparison to your own trend ("filler rate down 30% over your last 5 impromptu sessions"). Comparing you to your own history rather than a stranger's benchmark keeps the tool motivating rather than discouraging — and it's the thing generic apps skip because it requires the adaptive tracking in §5, not just a single-session score.

---

## 8. Suggested build order

1. Get faster-whisper transcribing a recorded clip locally — this alone unlocks filler-word/pace/pause metrics for free.
2. Add MediaPipe for basic eye-contact/posture signal on a webcam recording.
3. Write the LLM rubric prompt (§1) and wire it to Claude Sonnet first, since quality matters most while you're validating the rubric — swap to a local Ollama model later once you trust the rubric's calibration.
4. Build the skill-profile tracker (a simple running average/trend per metric is enough to start — no ML needed).
5. Implement the mode + constraint library (§3–4) as a lookup table, then layer the weakness-targeted/novelty selection logic (§5) on top.
6. Build the session-count-to-queue mapping (§6) last, once individual modes work end to end.
