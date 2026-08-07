"""
modes.py
Practice-mode library, topic pools, constraint layer, and the daily
session-count -> queue builder, per the design doc (AI_Speaking_Coach_Design.md).
"""

import random

# ---------------------------------------------------------------------------
# 1. Mode library — each mode trains a different skill
# ---------------------------------------------------------------------------

MODES = {
    "impromptu_sprint": {
        "name": "Impromptu Sprint",
        "seconds": 75,
        "prep_seconds": 0,
        "trains": "Fluency under zero prep, filler-word control",
        "instructions": "Speak on the topic below immediately. No prep time. "
                         "Just start talking.",
        "topics": [
            "The best advice you never took",
            "Why routines matter (or don't)",
            "A skill everyone should learn",
            "The most useful app on your phone",
            "A decision you're glad you made",
            "What makes a good leader",
            "A place you'd love to visit and why",
            "Something you changed your mind about",
            "The value of failure",
            "A habit you're trying to build",
        ],
    },
    "structured_persuasion": {
        "name": "Structured Persuasion",
        "seconds": 150,
        "prep_seconds": 20,
        "trains": "Argument construction",
        "instructions": "Argue for or against the topic below. You MUST follow this "
                         "structure out loud: Point -> Reason -> Example -> Point "
                         "(restate). 20 seconds to plan.",
        "topics": [
            "Remote work is better than office work",
            "Social media does more harm than good",
            "Failure is more valuable than success",
            "Everyone should learn to code",
            "Cities should be car-free",
            "AI will make people less creative",
            "Reading fiction makes you a better thinker",
            "Money can buy happiness",
        ],
    },
    "storytelling": {
        "name": "Storytelling",
        "seconds": 210,
        "prep_seconds": 20,
        "trains": "Vocal variety, pacing, emotional arc",
        "instructions": "Tell a short personal story on the prompt below. Give it a "
                         "clear beginning, turning point, and ending.",
        "topics": [
            "Tell about a time you failed at something",
            "Tell about a time you were completely wrong about someone",
            "Tell about the best piece of advice you ever received",
            "Tell about a moment you felt truly proud",
            "Tell about a time you had to adapt fast",
            "Tell about someone who changed how you think",
        ],
    },
    "explain_simply": {
        "name": "Explain-It-Simply",
        "seconds": 75,
        "prep_seconds": 10,
        "trains": "Clarity, simplification",
        "instructions": "Explain the topic below so a 10-year-old could understand "
                         "it. No jargon.",
        "topics": [
            "How the internet works",
            "Why the sky is blue",
            "What inflation is",
            "How vaccines work",
            "What a black hole is",
            "How interest rates affect the economy",
            "What blockchain is",
            "Why we dream",
        ],
    },
    "debate_rebuttal": {
        "name": "Debate + Rebuttal",
        "seconds": 120,
        "argument_seconds": 75,
        "prep_seconds": 10,
        "trains": "Quick thinking under pushback",
        "instructions": "Argue the stance below. At the 75-second mark a "
                         "counter-argument will appear on screen -- rebut it "
                         "immediately, unscripted, for the remaining time. "
                         "Recording stays on the whole time.",
        "topics": [
            "Homework should be abolished",
            "Zoos should not exist",
            "Four-day work weeks should be standard",
            "College degrees are overrated",
            "Self-driving cars are safer than humans",
            "Space exploration is worth the cost",
        ],
        "rebuttals": [
            "But doesn't that ignore the practical downsides?",
            "Isn't that just true for a small group of people, not everyone?",
            "What about the people who lose out under your proposal?",
            "Isn't there a cheaper/easier alternative that gets the same result?",
            "Doesn't the evidence actually point the other way?",
        ],
    },
    "elevator_pitch": {
        "name": "Elevator Pitch",
        "seconds": 45,
        "prep_seconds": 15,
        "trains": "Conciseness, strong open/close",
        "instructions": "Pitch the idea below in under 45 seconds. Going well over "
                         "or well under is scored against you -- aim tight.",
        "topics": [
            "Pitch a productivity app idea to an investor",
            "Pitch yourself for a promotion in 45 seconds",
            "Pitch a new product for people who work from home",
            "Pitch a nonprofit idea to a potential donor",
            "Pitch a book you'd want to write",
        ],
    },
    "full_presentation": {
        "name": "Full Presentation",
        "seconds": 360,
        "prep_seconds": 60,
        "video": True,
        "trains": "End-to-end structure, transitions, opening/closing",
        "instructions": "Deliver a short talk (aim 4-6 minutes) on the topic below "
                         "with a clear opening, 2-3 main points, and a closing. "
                         "Outline it in your prep time.",
        "topics": [
            "Why [a skill you have] is worth learning",
            "The biggest change in your industry in the last 5 years",
            "A project you're proud of and what you learned",
            "How you'd improve something at your workplace",
            "A book, show, or idea that shaped how you think",
        ],
    },
    "qa_stress_test": {
        "name": "Q&A Stress Test",
        "seconds": 90,
        "question_seconds": 30,
        "prep_seconds": 0,
        "trains": "Handling the unpredictable",
        "instructions": "Three follow-up questions will appear one at a time, "
                         "30 seconds apart. Answer each unscripted as it appears. "
                         "Recording stays on the whole time.",
        "topics": [
            "What's the biggest weakness in what you just said?",
            "How would you convince someone who completely disagrees?",
            "What would change your mind on this?",
            "What's the one thing you're least sure about here?",
            "If you had to cut everything but one point, what stays?",
        ],
    },
    "vocal_drill": {
        "name": "Vocal Drill",
        "seconds": 90,
        "prep_seconds": 0,
        "trains": "Pure mechanics: pace, pitch range, pause control",
        "instructions": "Read the passage below aloud. Focus purely on pace, pitch "
                         "variation, and deliberate pauses -- content isn't the "
                         "point here.",
        "topics": [
            "The greatest glory in living lies not in never falling, but in "
            "rising every time we fall. Success is not final, failure is not "
            "fatal: it is the courage to continue that counts. Our lives begin "
            "to end the day we become silent about things that matter.",
            "It was the best of times, it was the worst of times. It was the "
            "age of wisdom, it was the age of foolishness. We must never "
            "confuse honest dissent with disloyal subversion.",
            "The only way to do great work is to love what you do. If you "
            "haven't found it yet, keep looking. Don't settle. Stay hungry, "
            "stay foolish, and trust that the dots will somehow connect.",
        ],
    },
    "body_language_mirror": {
        "name": "Body Language Mirror",
        "seconds": 90,
        "prep_seconds": 0,
        "video": True,
        "trains": "Posture, eye contact, gesture presence",
        "instructions": "Talk about anything you like for 90 seconds (this one is "
                         "about HOW you look, not what you say). Face the camera "
                         "and speak naturally.",
        "topics": [
            "Describe your ideal weekend",
            "Talk about a hobby you enjoy",
            "Describe your morning routine",
            "Talk about a goal you're working toward",
        ],
    },
}

MODE_KEYS = list(MODES.keys())

# ---------------------------------------------------------------------------
# 2. Constraint layer -- stacks on top of any mode
# ---------------------------------------------------------------------------

CONSTRAINTS = [
    {"id": "no_filler", "label": "Banned word: avoid saying 'um', 'like', or 'basically' at all this session."},
    {"id": "rule_of_three", "label": "Required device: use a 'rule of three' list somewhere in your answer."},
    {"id": "callback", "label": "Required device: reference your opening line again in your closing line."},
    {"id": "rhetorical_question", "label": "Required device: open with a rhetorical question."},
    {"id": "emotion_urgency", "label": "Target emotion: deliver this with a sense of urgency."},
    {"id": "emotion_warmth", "label": "Target emotion: deliver this with warmth, like you're talking to a friend."},
    {"id": "emotion_gravity", "label": "Target emotion: deliver this like the topic really matters."},
    {"id": "persona_skeptic", "label": "Audience: imagine a skeptical executive who needs convincing."},
    {"id": "persona_beginner", "label": "Audience: imagine a curious beginner who knows nothing about this."},
    {"id": "tight_time", "label": "Extra constraint: try to finish in 75% of the allotted time."},
    {"id": "none", "label": "No extra constraint this time -- just focus on the mode itself."},
]


def pick_constraint(rng: random.Random | None = None):
    r = rng or random
    return r.choice(CONSTRAINTS)


def pick_topic(mode_key: str, rng: random.Random | None = None):
    r = rng or random
    return r.choice(MODES[mode_key]["topics"])


def pick_topics(mode_key: str, n: int, rng: random.Random | None = None):
    r = rng or random
    pool = list(MODES[mode_key]["topics"])
    r.shuffle(pool)
    return pool[:n]


# ---------------------------------------------------------------------------
# 3. Daily session-count -> queue templates (design doc section 6)
# ---------------------------------------------------------------------------

WARMUP_MODES = ["impromptu_sprint", "vocal_drill"]
STRESS_MODES = ["debate_rebuttal", "qa_stress_test"]
MAIN_POOL = [
    "structured_persuasion", "storytelling", "explain_simply",
    "elevator_pitch", "full_presentation", "body_language_mirror",
]

# Template = list of "slot types": 'warmup' | 'main' | 'novelty' | 'stress' | 'cooldown'
QUEUE_TEMPLATES = {
    1: ["main"],
    2: ["warmup", "main"],
    3: ["warmup", "main", "novelty"],
    4: ["warmup", "main", "main", "novelty"],
    5: ["warmup", "main", "main", "novelty", "stress"],
    6: ["warmup", "main", "main", "novelty", "stress", "cooldown"],
}


def build_queue_template(session_count: int):
    """Return the ordered list of slot-type strings for a given sessions/day count."""
    session_count = max(1, min(6, session_count))
    return QUEUE_TEMPLATES[session_count]
