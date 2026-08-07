"""
tracker.py
Persists session history locally (JSON file, no database needed) and picks
the next practice mode using the "weakness-targeted 70% / novelty 30%" logic
from the design doc (section 5).
"""

import json
import os
import random
import time

from modes import (
    MODE_KEYS, MODES, WARMUP_MODES, STRESS_MODES, MAIN_POOL,
    pick_constraint, pick_topic, pick_topics,
)
import github_storage

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

# Which modes are the best "fix" for a given weak metric.
METRIC_TO_MODES = {
    "filler_rate": ["impromptu_sprint", "qa_stress_test", "debate_rebuttal"],
    "pace_deviation": ["vocal_drill", "storytelling"],
    "pause_score": ["vocal_drill", "storytelling", "full_presentation"],
    "structure_score": ["structured_persuasion", "full_presentation"],
    "engagement_score": ["body_language_mirror", "storytelling"],
}

RECENT_WINDOW = 8       # how many past sessions to look at for trends
NOVELTY_LOOKBACK = 5    # a mode counts as "not recent" if unused in the last N sessions


def _ensure_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w") as f:
            json.dump([], f)


def load_history():
    """Reads from your GitHub repo if GITHUB_TOKEN+GITHUB_REPO are set
    (see github_storage.py -- built for free-tier hosts with no persistent
    disk), otherwise from the local data/history.json file."""
    if github_storage.enabled():
        return github_storage.load_history()
    _ensure_store()
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def save_session(record: dict):
    """record must include at least: mode, metrics (dict), timestamp is added here."""
    history = load_history()
    record = dict(record)
    record["timestamp"] = time.time()
    history.append(record)
    if github_storage.enabled():
        github_storage.save_history(history)
    else:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    return record


def compute_trends(history=None):
    """
    Returns {metric_name: {"avg": float, "latest": float, "n": int}} for every
    metric present in recent sessions, restricted to the last RECENT_WINDOW
    sessions that actually recorded that metric.
    """
    history = history if history is not None else load_history()
    recent = history[-RECENT_WINDOW:]
    trends = {}
    for metric in METRIC_TO_MODES:
        values = [s["metrics"][metric] for s in recent
                  if "metrics" in s and metric in s["metrics"]
                  and s["metrics"][metric] is not None]
        if values:
            trends[metric] = {
                "avg": sum(values) / len(values),
                "latest": values[-1],
                "n": len(values),
            }
    return trends


def worst_metric(trends: dict):
    """
    Higher score = worse for filler_rate and pace_deviation.
    Lower score = worse for pause_score, structure_score, engagement_score
    (these are 0-10 "goodness" scores).
    Returns the metric name judged worst, or None if no history yet.
    """
    if not trends:
        return None

    def badness(metric, stats):
        if metric in ("filler_rate", "pace_deviation"):
            return stats["avg"]                 # higher is worse, use directly
        return 10 - stats["avg"]                # invert 0-10 goodness scores

    return max(trends, key=lambda m: badness(m, trends[m]))


def _recent_modes(history, n=NOVELTY_LOOKBACK):
    return [s.get("mode") for s in history[-n:]]


def _all_time_counts(history):
    counts = {m: 0 for m in MODE_KEYS}
    for s in history:
        m = s.get("mode")
        if m in counts:
            counts[m] += 1
    return counts


def _never_tried(history, pool):
    """Modes in `pool` with zero appearances in the ENTIRE history (not just
    recent) -- used to prioritize true first-time discovery over merely
    'not recent', so e.g. a mode you've simply never rolled yet (like a
    video mode gated behind a rare novelty slot) doesn't take forever to
    surface."""
    counts = _all_time_counts(history)
    return [m for m in pool if counts.get(m, 0) == 0]


def choose_mode_for_slot(slot_type: str, history=None, rng=None):
    """
    slot_type: 'warmup' | 'main' | 'novelty' | 'stress' | 'cooldown'
    Returns a mode_key string.
    """
    r = rng or random
    history = history if history is not None else load_history()

    if slot_type == "warmup":
        return r.choice(WARMUP_MODES)

    if slot_type == "stress":
        return r.choice(STRESS_MODES)

    if slot_type == "cooldown":
        return "vocal_drill"

    if slot_type == "novelty":
        never_tried = _never_tried(history, MODE_KEYS)
        if never_tried:
            return r.choice(never_tried)
        recent = _recent_modes(history)
        candidates = [m for m in MODE_KEYS if m not in recent]
        return r.choice(candidates) if candidates else r.choice(MODE_KEYS)

    if slot_type == "main":
        trends = compute_trends(history)
        weak = worst_metric(trends)
        # 70% weakness-targeted, 30% novelty -- but only if we actually have
        # enough history to know a weakness; otherwise just explore.
        if weak and r.random() < 0.70:
            candidates = [m for m in METRIC_TO_MODES[weak] if m in MAIN_POOL + WARMUP_MODES + STRESS_MODES]
            if candidates:
                return r.choice(candidates)
        never_tried = _never_tried(history, MAIN_POOL)
        if never_tried:
            return r.choice(never_tried)
        recent = _recent_modes(history)
        candidates = [m for m in MAIN_POOL if m not in recent]
        return r.choice(candidates) if candidates else r.choice(MAIN_POOL)

    # fallback
    return r.choice(MODE_KEYS)


def _build_entry(mode_key, slot_type, rng):
    mode = MODES[mode_key]
    entry = {
        "slot_type": slot_type,
        "mode": mode_key,
        "mode_name": mode["name"],
        "seconds": mode["seconds"],
        "prep_seconds": mode["prep_seconds"],
        "video": mode.get("video", False),
        "trains": mode["trains"],
        "instructions": mode["instructions"],
        "topic": pick_topic(mode_key, rng),
        "constraint": pick_constraint(rng),
    }
    if mode_key == "debate_rebuttal":
        entry["rebuttal"] = rng.choice(mode["rebuttals"])
        entry["argument_seconds"] = mode["argument_seconds"]
    if mode_key == "qa_stress_test":
        entry["questions"] = pick_topics(mode_key, 3, rng)
        entry["question_seconds"] = mode["question_seconds"]
    return entry


VIDEO_MODES = [k for k, m in MODES.items() if m.get("video")]


def build_session_plan(session_count: int, seed=None):
    """
    Builds today's full queue: a list of dicts, each with mode, topic,
    constraint, and the metadata needed to render a session page.

    Also guarantees discovery of the video-scored modes: since they only
    ever get selected via the low-probability "novelty"/explore branches,
    a low-session-count user could otherwise go a long time without ever
    seeing one. If neither video mode has ever been tried, today's plan is
    guaranteed to include one.
    """
    from modes import build_queue_template

    rng = random.Random(seed) if seed is not None else random
    original_history = load_history()
    history = original_history
    template = build_queue_template(session_count)

    plan = []
    for slot_type in template:
        mode_key = choose_mode_for_slot(slot_type, history=history, rng=rng)
        entry = _build_entry(mode_key, slot_type, rng)
        plan.append(entry)
        # feed a lightweight placeholder into "history" for this planning pass
        # so back-to-back slots in the same day don't pick the identical mode
        history = history + [{"mode": mode_key, "metrics": {}}]

    video_ever_tried = any(_all_time_counts(original_history).get(m, 0) > 0 for m in VIDEO_MODES)
    already_has_video_slot = any(e["video"] for e in plan)
    if not video_ever_tried and not already_has_video_slot:
        # force one slot to a never-tried video mode -- prefer the last
        # "main" slot (most representative length/format), else "novelty",
        # else just the last slot in the queue.
        target_idx = None
        for i in range(len(plan) - 1, -1, -1):
            if plan[i]["slot_type"] == "main":
                target_idx = i
                break
        if target_idx is None:
            for i in range(len(plan) - 1, -1, -1):
                if plan[i]["slot_type"] == "novelty":
                    target_idx = i
                    break
        if target_idx is None:
            target_idx = len(plan) - 1

        forced_mode = rng.choice(VIDEO_MODES)
        plan[target_idx] = _build_entry(forced_mode, plan[target_idx]["slot_type"], rng)

    return plan


def skill_summary():
    """Human-readable snapshot of trends, used on the dashboard."""
    trends = compute_trends()
    weak = worst_metric(trends)
    return {"trends": trends, "weakest": weak}
