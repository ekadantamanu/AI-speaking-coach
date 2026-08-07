"""
feedback.py
Turns raw metrics + transcript into the feedback report described in the
design doc (section 7): one thing that worked, ONE prioritized fix, the raw
numbers, and a trend line vs. your own history.

Works with zero API cost out of the box (rubric-based local scoring). If an
ANTHROPIC_API_KEY environment variable is set, it upgrades the qualitative
write-up by calling Claude with a strict, example-anchored rubric prompt
(see design doc section 1 -- "the real quality lever is the rubric, not the
model"). Local mode never breaks the app if no key/network is available.
"""

import os
import re

CONCLUSION_CUES = [
    "in conclusion", "to conclude", "ultimately", "in summary", "so, ",
    "that's why", "that is why", "in the end", "overall,", "to sum up",
    "the bottom line", "so in short",
]
OPENING_HOOK_CUES = [
    "?", "imagine", "picture this", "what if", "did you know", "let me tell you",
]


def _sentences(text: str):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def rubric_score_structure(text: str):
    """
    Local, zero-cost heuristic structure score (0-10) + notes, kept as two
    SEPARATE lists (positive vs. negative) so callers never accidentally
    surface a negative note as a "what worked" highlight.
    Not as nuanced as an LLM read, but free, instant, and consistent.
    """
    sents = _sentences(text)
    positives, negatives = [], []
    score = 5.0  # baseline

    if not sents:
        return 0.0, [], ["No speech detected."]

    opener = sents[0].lower()
    if any(cue in opener for cue in OPENING_HOOK_CUES):
        score += 1.5
        positives.append("Strong, attention-grabbing opening line.")
    else:
        negatives.append("Opening was flat -- consider a question, stat, or short story to hook the audience.")

    closer = sents[-1].lower()
    if any(cue in closer for cue in CONCLUSION_CUES):
        score += 1.5
        positives.append("Clear closing signal.")
    else:
        negatives.append("Ending trailed off rather than landing on a clear closing line.")

    # reward having multiple distinct sentences (a "point, point, point"
    # shape) without being a wall of run-ons
    if 3 <= len(sents) <= 20:
        score += 1.0
        positives.append("Good balance of distinct points -- not a run-on, not too fragmented.")
    elif len(sents) < 3:
        negatives.append("Very few distinct sentences -- try breaking the idea into more than one point.")
    else:
        negatives.append("A lot of short fragments -- check if some should be combined into fuller thoughts.")

    # reward transition words that signal structure
    transitions = ["first", "second", "third", "next", "then", "finally", "however", "because", "for example"]
    hits = sum(1 for t in transitions if t in text.lower())
    if hits >= 2:
        score += 1.0
        positives.append("Good use of transition words to signal structure.")

    return round(max(0.0, min(10.0, score)), 1), positives, negatives


def _pick_highlight(positives, metrics):
    """Prefer a specific qualitative positive; fall back to a numeric one; else generic."""
    if positives:
        return positives[0]
    if metrics.get("eye_contact_score", 0) >= 7:
        return "You stayed facing the camera consistently -- that reads as confidence on video."
    if metrics.get("posture_score", 0) >= 7:
        return "Shoulders stayed level and steady -- posture wasn't distracting from the message."
    if metrics.get("gesture_score", 0) >= 6:
        return "Hand movement was in a healthy range -- animated without being distracting."
    if metrics["filler_rate"] <= 3:
        return f"Filler words were nearly eliminated ({metrics['filler_count']} total) -- that's a genuinely clean take."
    if metrics["pace_deviation"] == 0:
        return f"Pace stayed right in the comfortable range at {metrics['wpm']} WPM."
    if metrics["pause_score"] >= 7:
        return "Pauses were placed deliberately rather than rushed through."
    return "You completed the session -- that consistency is what compounds over time."


def _local_feedback(mode_name, topic, constraint, text, metrics, structure_score, positives, negatives, trend_line):
    """Zero-cost, template-based write-up. Used when no LLM key is configured."""
    highlight = _pick_highlight(positives, metrics)

    # priority order for "the one thing to fix": filler rate > pace > pauses > structure
    fixes = []
    if metrics["filler_rate"] > 6:
        fixes.append(("filler_rate",
            f"Filler rate was {metrics['filler_rate']}% of words ({metrics['filler_count']} fillers). "
            f"Next impromptu rep, try leaving a silent half-second instead of saying 'um'/'like'."))
    if metrics["pace_deviation"] > 2:
        direction = "faster" if metrics["wpm"] > 160 else "slower"
        fixes.append(("pace",
            f"Pace was {metrics['wpm']} WPM, {'above' if metrics['wpm'] > 160 else 'below'} the "
            f"120-160 comfortable range. Try speaking noticeably {direction} on purpose next time to recalibrate."))
    if metrics["pause_score"] < 5:
        fixes.append(("pauses",
            "Pauses were either too rare (rushed delivery) or too long/frequent (lost momentum). "
            "Aim for one deliberate breath-pause every ~20 seconds, right after a key point."))
    if structure_score < 6 and negatives:
        fixes.append(("structure", negatives[0]))
    if "eye_contact_score" in metrics and metrics["eye_contact_score"] < 5:
        fixes.append(("eye_contact",
            "You were facing away from center a lot of the time -- try positioning the camera "
            "at eye level and consciously returning your gaze to it between thoughts."))
    if "posture_score" in metrics and metrics["posture_score"] < 5:
        fixes.append(("posture",
            "Shoulders were tilted or shifting a lot -- try grounding your stance/seat before starting "
            "so posture isn't competing for attention with your message."))
    if "gesture_score" in metrics and metrics["gesture_score"] < 4:
        fixes.append(("gesture",
            "Hands stayed mostly still -- adding a couple of deliberate gestures on key points "
            "tends to read as more engaged and natural."))

    if fixes:
        top_fix = fixes[0][1]
    elif negatives:
        # numeric metrics were all fine, but there's still a qualitative note worth acting on
        top_fix = negatives[0]
    else:
        top_fix = "Nothing major stood out -- push the difficulty up (shorter time cap or a harder mode) next session."

    return {
        "highlight": highlight,
        "top_fix": top_fix,
        "trend_line": trend_line,
        "source": "local-rubric",
    }


def _llm_feedback(mode_name, topic, constraint, text, metrics, structure_score):
    """
    Optional upgrade path: calls Claude with a strict rubric prompt if
    ANTHROPIC_API_KEY is set. Returns None on any failure so callers fall
    back to the free local generator automatically.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are a Toastmasters-caliber speech evaluator. Score the transcript
below and respond in EXACTLY this format, nothing else:

HIGHLIGHT: <one specific thing that worked, one sentence, name it concretely -- not "good job">
TOP_FIX: <the single most important thing to fix, one sentence, concrete and actionable>

Rules: be specific (quote a phrase if useful), be encouraging but honest, never give more
than one fix, never use generic praise like "great job" or "nice work" without specifics.

Example of a GOOD highlight: "Your line 'failure is just data' was a strong, quotable close."
Example of a WEAK highlight (do not do this): "Good job overall, nice energy."

Mode: {mode_name}
Topic: {topic}
Constraint: {constraint}
Measured filler rate: {metrics['filler_rate']}% | Pace: {metrics['wpm']} WPM | Structure score: {structure_score}/10

Transcript:
\"\"\"{text}\"\"\"
"""
        resp = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text if resp.content else ""
        highlight_match = re.search(r"HIGHLIGHT:\s*(.+)", raw)
        fix_match = re.search(r"TOP_FIX:\s*(.+)", raw)
        if highlight_match and fix_match:
            return {
                "highlight": highlight_match.group(1).strip(),
                "top_fix": fix_match.group(1).strip(),
                "source": "claude-sonnet-5",
            }
    except Exception:
        return None
    return None


def build_feedback(mode_name, topic, constraint, text, metrics, trend_line=""):
    structure_score, positives, negatives = rubric_score_structure(text)

    llm_result = _llm_feedback(mode_name, topic, constraint, text, metrics, structure_score)
    if llm_result:
        report = llm_result
    else:
        report = _local_feedback(mode_name, topic, constraint, text, metrics,
                                  structure_score, positives, negatives, trend_line)

    report["structure_score"] = structure_score
    report["trend_line"] = trend_line
    return report


def trend_line_for(metric_name, trends, latest_value):
    """Builds the 'down 30% over your last 5 sessions' style line from tracker.py trends."""
    if not trends or metric_name not in trends or trends[metric_name]["n"] < 2:
        return "First session tracked for this metric -- future sessions will show your trend here."
    avg = trends[metric_name]["avg"]
    if avg == 0:
        return ""
    change_pct = ((latest_value - avg) / avg) * 100
    direction = "up" if change_pct > 0 else "down"
    better_when_lower = metric_name in ("filler_rate", "pace_deviation")
    is_improving = (direction == "down") if better_when_lower else (direction == "up")
    verdict = "improving" if is_improving else "worth watching"
    return f"{metric_name.replace('_', ' ')} is {direction} {abs(round(change_pct))}% vs your recent average ({verdict})."
