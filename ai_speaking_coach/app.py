"""
app.py
Simple Flask web app: pick how many sessions you want today, get a varied
daily queue (see modes.py / tracker.py), record each session in the browser,
get instant feedback (speech_analysis.py + feedback.py), repeat.

Run locally with:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""

import os
import tempfile
import subprocess
import uuid

from flask import Flask, render_template, request, redirect, url_for, session as flask_session

import tracker
import speech_analysis
import feedback as feedback_mod
import video_analysis
from modes import MODES

app = Flask(__name__)
app.secret_key = os.environ.get("SPEAKING_COACH_SECRET", "dev-secret-change-me")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Privacy gate --------------------------------------------------------
# Set APP_PASSWORD as an environment variable on any host you deploy this
# to (Render, a VPS, etc.) and the whole app requires that password before
# anyone -- including you -- can use it. Locally with no APP_PASSWORD set,
# the gate is skipped entirely so `python app.py` on your own machine works
# with zero setup, same as before.
APP_PASSWORD = os.environ.get("APP_PASSWORD")


@app.before_request
def _require_password():
    if not APP_PASSWORD:
        return  # no password configured -- gate is off (local/dev use)
    if request.endpoint in ("login", "static"):
        return
    if flask_session.get("authed"):
        return
    return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            flask_session["authed"] = True
            flask_session.permanent = True
            dest = request.args.get("next") or url_for("index")
            return redirect(dest)
        error = "Wrong password."
    return render_template("login.html", error=error)


@app.route("/")
def index():
    summary = tracker.skill_summary()
    history = tracker.load_history()
    return render_template("index.html", summary=summary, session_count=len(history))


@app.route("/plan", methods=["POST"])
def plan():
    count = int(request.form.get("session_count", 1))
    today_plan = tracker.build_session_plan(count)
    flask_session["plan"] = today_plan
    flask_session["results"] = []
    return redirect(url_for("session_view", idx=0))


@app.route("/session/<int:idx>")
def session_view(idx):
    plan_list = flask_session.get("plan")
    if not plan_list:
        return redirect(url_for("index"))
    if idx >= len(plan_list):
        return redirect(url_for("finished"))
    entry = plan_list[idx]
    return render_template("session.html", entry=entry, idx=idx, total=len(plan_list))


def _convert_to_wav(raw_path: str) -> str:
    """Browser MediaRecorder gives webm/ogg -- convert to wav via ffmpeg for
    reliable decoding, and to keep speech_analysis.py's dependency surface small."""
    wav_path = raw_path + ".wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_path, "-ar", "16000", "-ac", "1", wav_path],
        check=True, capture_output=True,
    )
    return wav_path


@app.route("/submit/<int:idx>", methods=["POST"])
def submit(idx):
    plan_list = flask_session.get("plan")
    if not plan_list or idx >= len(plan_list):
        return redirect(url_for("index"))
    entry = plan_list[idx]

    audio_file = request.files.get("audio")
    if audio_file is None:
        return render_template("session.html", entry=entry, idx=idx,
                                total=len(plan_list), error="No audio received -- check mic permissions and try again.")

    raw_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.webm")
    audio_file.save(raw_path)

    try:
        wav_path = _convert_to_wav(raw_path)
        analysis = speech_analysis.analyze(wav_path)
    except Exception as e:
        return render_template("session.html", entry=entry, idx=idx, total=len(plan_list),
                                error=f"Couldn't process that recording ({e}). Try again.")

    video_metrics = None
    video_note = None
    if entry.get("video"):
        try:
            video_result = video_analysis.analyze(raw_path)
            video_metrics = video_result["metrics"]
            if video_metrics is None:
                video_note = "No person detected in frame -- body-language scoring skipped for this take."
        except Exception as e:
            video_note = f"Body-language scoring failed ({e}) -- voice feedback below is still valid."

    for p in (raw_path, raw_path + ".wav"):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    metrics = analysis["metrics"]
    if video_metrics:
        metrics.update(video_metrics)

    # trend line vs history BEFORE this session is saved
    trends_before = tracker.compute_trends()
    if video_metrics and "engagement_score" in trends_before:
        trend_line = feedback_mod.trend_line_for("engagement_score", trends_before, metrics["engagement_score"])
    else:
        trend_line = feedback_mod.trend_line_for("filler_rate", trends_before, metrics["filler_rate"])

    report = feedback_mod.build_feedback(
        entry["mode_name"], entry["topic"], entry["constraint"]["label"],
        analysis["text"], metrics, trend_line=trend_line,
    )

    metrics_to_store = dict(metrics)
    metrics_to_store["structure_score"] = report["structure_score"]

    saved = tracker.save_session({
        "mode": entry["mode"],
        "mode_name": entry["mode_name"],
        "topic": entry["topic"],
        "metrics": metrics_to_store,
    })

    result = {
        "entry": entry,
        "transcript": analysis["text"],
        "duration_seconds": analysis["duration_seconds"],
        "word_count": analysis["word_count"],
        "metrics": metrics,
        "report": report,
        "video_note": video_note,
        "has_video_metrics": video_metrics is not None,
    }
    results = flask_session.get("results", [])
    results.append(result)
    flask_session["results"] = results

    next_idx = idx + 1
    has_next = next_idx < len(plan_list)
    return render_template("result.html", result=result, idx=idx, total=len(plan_list),
                            has_next=has_next, next_idx=next_idx)


@app.route("/finished")
def finished():
    results = flask_session.get("results", [])
    summary = tracker.skill_summary()
    return render_template("finished.html", results=results, summary=summary)


@app.route("/dashboard")
def dashboard():
    summary = tracker.skill_summary()
    history = tracker.load_history()
    return render_template("dashboard.html", summary=summary, history=list(reversed(history)))


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
