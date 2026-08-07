# AI Speaking Coach

A simple local web app for daily speaking/presentation practice with instant
feedback. Pick how many sessions you want today (1-6), get a varied queue
built for you (not just random topics -- different exercise *formats*), record
each one in your browser, and get a feedback report immediately.

Companion design doc: `AI_Speaking_Coach_Design.md` (one level up, in the
same folder you got this from) explains the reasoning behind the mode
library, the adaptive targeting logic, and the tool choices below.

## What it does

- **10 practice modes** (impromptu sprint, structured persuasion, storytelling,
  explain-it-simply, debate + rebuttal, elevator pitch, full presentation,
  Q&A stress test, vocal drill, body language mirror) so you're never just
  drilling the same "random topic" format every day.
- **Adaptive targeting** -- it tracks your filler-word rate, pace, pause
  quality, and structure score over time, and weights future sessions toward
  whichever metric is trending worst (70% of "main" slots), with a 30%
  "novelty" budget forcing modes you haven't touched recently so it never
  gets stale.
- **Instant feedback** -- one thing that worked, one prioritized fix, the raw
  numbers, and a trend line vs. your own recent history.
- **Body-language scoring** for the Full Presentation and Body Language
  Mirror modes -- camera turns on, and MediaPipe (local, free) scores how
  much you faced the camera, shoulder levelness, and hand-gesture range,
  combined into an engagement score. Other modes stay audio-only so you're
  not granting camera access for a 60-second impromptu rep.
- **Runs locally, free by default** -- transcription via `faster-whisper`
  and body-language scoring via `MediaPipe` (both open-source, run on your
  machine, no per-minute API fee), and feedback via a free rubric-based
  generator. No account, no cloud dependency, no cost, unless you opt into
  the Claude upgrade below.

## Setup

1. **Requirements**: Python 3.9+, and `ffmpeg` installed and on your PATH
   (used to convert the browser's recorded audio to WAV).
   - macOS: `brew install ffmpeg`
   - Windows: install from ffmpeg.org and add to PATH, or `choco install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

2. **Install Python dependencies**:
   ```
   cd ai_speaking_coach
   pip install -r requirements.txt
   ```

3. **Run it**:
   ```
   python app.py
   ```
   Then open **http://127.0.0.1:5000** in your browser (Chrome or Edge
   recommended -- they have the most reliable `MediaRecorder`/mic permission
   support).

4. **First run note**: the first time you record a session, `faster-whisper`
   downloads its model (~150MB for the default "base" size) from Hugging
   Face. This needs internet access once; after that, transcription runs
   fully offline. If you want it faster/lighter, open `speech_analysis.py`
   and change `_model_size = "base"` to `"tiny"` (less accurate but much
   faster on a laptop CPU) or `"small"` (slower, more accurate).

5. **First video-mode run note**: the first time you do a Full Presentation
   or Body Language Mirror session, `video_analysis.py` downloads MediaPipe's
   pose model (~5-9MB) from Google's model store -- also a one-time download,
   also fully offline afterward. If your firewall/network blocks
   `storage.googleapis.com`, this download will fail; the app will show an
   error on that specific session but the rest of the app keeps working
   (audio-only modes are unaffected).

## Optional: upgrade feedback quality with Claude

By default, feedback comes from a free, local, rubric-based generator (see
`feedback.py`) -- no API key, no cost, works offline. If you want richer,
more nuanced qualitative feedback, set an API key before running the app:

```
export ANTHROPIC_API_KEY=your-key-here   # macOS/Linux
set ANTHROPIC_API_KEY=your-key-here      # Windows (cmd)
python app.py
```

The app automatically detects the key and switches to Claude for the
"what worked / what to fix" write-up; if the key is missing or the call
fails for any reason, it silently falls back to the local generator so the
app never breaks. Cost is a few cents per session at most (see the design
doc for exact pricing).

## Running it privately from anywhere (not just localhost)

See `DEPLOYMENT.md` for the full walkthrough -- the short version is a free
Render.com deployment, connected via GitHub, locked behind a password.
Relevant environment variables, all optional for local use:

| Variable | Purpose |
|---|---|
| `APP_PASSWORD` | Locks the whole app behind a login screen. Unset = no gate (fine for `python app.py` on your own machine). |
| `SPEAKING_COACH_SECRET` | Signs the login session cookie -- set a real random value on any public deployment. |
| `GITHUB_TOKEN` / `GITHUB_REPO` | When both are set, session history is stored in your own GitHub repo instead of the local disk -- needed on free-tier hosts with no persistent storage (see `github_storage.py`). |
| `WHISPER_MODEL_SIZE` | Overrides the transcription model size (`tiny`/`base`/`small`/`medium`). Defaults to `base`; use `tiny` on low-RAM free hosting. |
| `ANTHROPIC_API_KEY` | Optional Claude feedback upgrade, described above. |

## Project structure

```
ai_speaking_coach/
  app.py                 Flask routes / session flow / password gate
  modes.py                10 practice modes, topics, constraints, daily queue templates
  tracker.py              session history + adaptive weakness-targeting logic
  speech_analysis.py      faster-whisper transcription + filler/pace/pause metrics
  video_analysis.py        MediaPipe body-language scoring (eye contact/posture/gesture)
  feedback.py              local rubric feedback generator + optional Claude upgrade
  github_storage.py        optional GitHub-backed history storage (see table above)
  render.yaml               Render Blueprint config for one-click free deployment
  templates/               Flask/Jinja HTML pages (includes login.html)
  static/                  CSS + the browser-side recorder JavaScript
  data/history.json        your local session history (created automatically; ignored if using GitHub storage)
  data/models/              downloaded model files (whisper cache elsewhere, mediapipe .task here)
```

## Known limitations (honest list)

- **"Facing camera" is a head-orientation proxy, not real gaze/iris tracking.**
  `video_analysis.py` uses BlazePose's body keypoints (nose/ear symmetry) to
  estimate whether you're facing the camera -- it can't tell if your *eyes*
  specifically are on the lens vs. just your head being turned that way.
  True gaze tracking would need MediaPipe's Face Landmarker (iris landmarks)
  layered on top; left out here to keep the app to a single vision model.
- **Structure scoring is a heuristic**, not deep semantic understanding,
  when running in free/local mode -- it checks for openers, closers,
  transition words, and sentence count, not whether your argument was
  actually persuasive. The Claude upgrade path improves this meaningfully.
- **Single-user, local-only.** History is a flat JSON file, sessions are
  tracked in a browser cookie -- fine for personal daily practice, not built
  for multiple users or deployment as a public site as-is.
- **Debate + Rebuttal and Q&A Stress Test** run as one continuous recording
  with the prompt changing on-screen mid-recording (simpler to build and
  more realistic for "thinking on your feet"), rather than stopping and
  starting multiple separate recordings.

## Suggested next steps if you want to extend it

1. Add openSMILE-based pitch/vocal-variety scoring alongside the current
   pace/pause metrics.
2. Add MediaPipe's Face Landmarker (iris tracking) for true gaze detection
   instead of the current head-orientation proxy.
3. Add simple charts (e.g. Chart.js) to the dashboard so trend lines are
   visual, not just numbers in a table.
4. Swap the flat JSON history file for SQLite if you want multi-device sync
   or more than a few hundred sessions of history.

## Making it accessible from anywhere (not just localhost)

See `DEPLOYMENT.md` in this same folder for step-by-step options -- a quick
temporary tunnel to try it from your phone today, and a proper always-on
deployment with HTTPS if you want a permanent URL.
