"""
speech_analysis.py
Transcribes a recorded practice session with faster-whisper (local, free,
no per-minute cost) and derives the objective delivery metrics: words per
minute, filler-word rate, and pause structure.
"""

import os
import re

FILLER_WORDS = {
    "um", "uh", "umm", "uhh", "erm", "er", "like", "basically", "actually",
    "literally", "you know", "sort of", "kind of", "i mean", "so yeah",
    "right", "okay so",
}

# target speaking pace range for scoring (typical comfortable presentation pace)
TARGET_WPM_LOW = 120
TARGET_WPM_HIGH = 160

# a gap between words/segments longer than this counts as a "pause"
PAUSE_THRESHOLD_SECONDS = 0.6
LONG_PAUSE_THRESHOLD_SECONDS = 1.5

_model = None
# tiny / base / small / medium -- base is a good speed/accuracy tradeoff on a
# laptop; override with WHISPER_MODEL_SIZE=tiny on low-RAM free-tier hosts
# (e.g. Render's free 512MB plan) to cut memory use and cold-start time.
_model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")


def _get_model():
    """Lazy-load the faster-whisper model once per process."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(_model_size, device="cpu", compute_type="int8")
    return _model


def transcribe(audio_path: str):
    """
    Returns:
        {
          "text": full transcript,
          "words": [{"word": str, "start": float, "end": float}, ...],
          "duration": float seconds,
        }
    """
    model = _get_model()
    segments, info = model.transcribe(audio_path, word_timestamps=True)

    words = []
    full_text_parts = []
    last_end = 0.0
    for seg in segments:
        full_text_parts.append(seg.text.strip())
        if seg.words:
            for w in seg.words:
                words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
                last_end = max(last_end, w.end)

    return {
        "text": " ".join(p for p in full_text_parts if p),
        "words": words,
        "duration": info.duration if getattr(info, "duration", None) else last_end,
    }


def _count_fillers(text: str) -> int:
    lowered = text.lower()
    count = 0
    for phrase in FILLER_WORDS:
        # word-boundary match so "like" doesn't match inside "likely"
        count += len(re.findall(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", lowered))
    return count


def _pauses(words):
    """Returns (pause_count, long_pause_count, total_pause_seconds)."""
    if len(words) < 2:
        return 0, 0, 0.0
    pause_count = 0
    long_pause_count = 0
    total = 0.0
    for i in range(1, len(words)):
        gap = words[i]["start"] - words[i - 1]["end"]
        if gap >= PAUSE_THRESHOLD_SECONDS:
            pause_count += 1
            total += gap
            if gap >= LONG_PAUSE_THRESHOLD_SECONDS:
                long_pause_count += 1
    return pause_count, long_pause_count, total


def analyze(audio_path: str):
    """
    Full pipeline: transcribe + compute the metrics used by tracker.py and
    feedback.py. Metric conventions:
      - filler_rate: fillers per 100 words (higher = worse)
      - pace_deviation: 0-10, 0 = perfectly in target band, 10 = very off (worse = higher)
      - pause_score: 0-10 goodness score, rewards a handful of deliberate pauses,
                     penalizes zero pauses (rushed) or excessive long pauses (worse = lower)
      - wpm: raw words-per-minute, for display only
    """
    result = transcribe(audio_path)
    text = result["text"]
    words = result["words"]
    duration = max(result["duration"], 1e-6)

    word_count = len(words) if words else len(text.split())
    wpm = (word_count / duration) * 60.0

    filler_count = _count_fillers(text)
    filler_rate = (filler_count / word_count * 100.0) if word_count else 0.0

    pause_count, long_pause_count, total_pause = _pauses(words)

    # pace_deviation: 0 inside target band, scales up outside it
    if TARGET_WPM_LOW <= wpm <= TARGET_WPM_HIGH:
        pace_deviation = 0.0
    else:
        off_by = min(wpm, TARGET_WPM_LOW) - TARGET_WPM_LOW if wpm < TARGET_WPM_LOW else wpm - TARGET_WPM_HIGH
        pace_deviation = min(10.0, abs(off_by) / 8.0)  # ~8 wpm off = 1 point

    # pause_score: sweet spot is a few deliberate pauses relative to length;
    # zero pauses on a longer session, or too many long pauses, score lower.
    expected_pauses = max(1, round(duration / 20))  # roughly one pause per 20s is healthy
    pause_score = 10.0 - min(10.0, abs(pause_count - expected_pauses) * 1.2) - (long_pause_count * 0.5)
    pause_score = max(0.0, min(10.0, pause_score))

    return {
        "text": text,
        "duration_seconds": round(duration, 1),
        "word_count": word_count,
        "metrics": {
            "wpm": round(wpm, 1),
            "filler_count": filler_count,
            "filler_rate": round(filler_rate, 2),
            "pause_count": pause_count,
            "long_pause_count": long_pause_count,
            "pace_deviation": round(pace_deviation, 2),
            "pause_score": round(pause_score, 2),
        },
    }
