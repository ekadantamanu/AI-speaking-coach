"""
video_analysis.py
Body-language scoring from the recorded webcam video, using MediaPipe's
Pose Landmarker (free, open-source, runs locally -- see design doc section 1).

Honest scope note: this uses BlazePose's 33 body keypoints (which include
nose/eye/ear positions) as a PROXY for head-forward orientation, not true
gaze/iris tracking -- MediaPipe's dedicated iris tracking would need a
second model (Face Landmarker) for real eye-contact detection. Treat
eye_contact_score as "were you facing the camera," not "were your eyes on
the exact right spot." That distinction is called out again in the UI.

On first use, this downloads the pose_landmarker_lite.task model (~5-9MB)
from Google's model store -- a one-time download, then fully offline.
"""

import math
import os
import urllib.request

MODEL_DIR = os.path.join(os.path.dirname(__file__), "data", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "pose_landmarker_lite.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_lite/float16/1/pose_landmarker_lite.task")

# BlazePose landmark indices we care about
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 2, 5, 7, 8
L_SHOULDER, R_SHOULDER = 11, 12
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24

FRAME_SAMPLE_FPS = 2  # analyze ~2 frames/second -- plenty for body-language trends, keeps CPU cost low

_landmarker = None


def _ensure_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)


def _get_landmarker():
    global _landmarker
    if _landmarker is None:
        _ensure_model()
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
        )
        _landmarker = vision.PoseLandmarker.create_from_options(options)
    return _landmarker


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def _analyze_frame(landmarks):
    """Returns a dict of per-frame raw signals, or None if no person detected."""
    if not landmarks:
        return None
    lm = landmarks[0]

    nose, l_ear, r_ear = lm[NOSE], lm[L_EAR], lm[R_EAR]
    l_shoulder, r_shoulder = lm[L_SHOULDER], lm[R_SHOULDER]
    l_wrist, r_wrist = lm[L_WRIST], lm[R_WRIST]

    # -- head-forward proxy: how symmetric are the ears around the nose (x-axis)?
    left_gap = abs(nose.x - l_ear.x)
    right_gap = abs(r_ear.x - nose.x)
    if max(left_gap, right_gap) > 1e-6:
        symmetry = min(left_gap, right_gap) / max(left_gap, right_gap)
    else:
        symmetry = 0.0  # degenerate, treat as not-forward

    # -- shoulder levelness: angle of the shoulder line vs horizontal (degrees)
    dx = r_shoulder.x - l_shoulder.x
    dy = r_shoulder.y - l_shoulder.y
    shoulder_angle = abs(math.degrees(math.atan2(dy, dx)))
    shoulder_angle = min(shoulder_angle, 180 - shoulder_angle)  # fold to 0-90

    return {
        "forward_symmetry": symmetry,
        "shoulder_angle": shoulder_angle,
        "wrist_positions": ((l_wrist.x, l_wrist.y), (r_wrist.x, r_wrist.y)),
    }


def analyze(video_path: str):
    """
    Samples frames from the video, runs pose detection, and returns:
      {
        "frames_analyzed": int,
        "frames_with_person": int,
        "metrics": {
          "eye_contact_score": 0-10,   # facing-camera proxy, see module docstring
          "posture_score": 0-10,        # shoulder levelness/stability
          "gesture_score": 0-10,        # healthy hand-movement band
          "engagement_score": 0-10,     # combined
        }
      }
    Returns metrics as None (not a crash) if no video/no person was ever
    detected, so callers can gracefully skip this layer.
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"frames_analyzed": 0, "frames_with_person": 0, "metrics": None}

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 24
    frame_interval = max(1, round(src_fps / FRAME_SAMPLE_FPS))

    landmarker = _get_landmarker()
    import mediapipe as mp

    frame_idx = 0
    analyzed = 0
    symmetries, shoulder_angles, wrist_series = [], [], []

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_interval == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)
            analyzed += 1
            per_frame = _analyze_frame(result.pose_landmarks)
            if per_frame:
                symmetries.append(per_frame["forward_symmetry"])
                shoulder_angles.append(per_frame["shoulder_angle"])
                wrist_series.append(per_frame["wrist_positions"])
        frame_idx += 1
    cap.release()

    frames_with_person = len(symmetries)
    if frames_with_person == 0:
        return {"frames_analyzed": analyzed, "frames_with_person": 0, "metrics": None}

    # eye_contact_score: average forward-symmetry, scaled 0-10
    avg_symmetry = sum(symmetries) / len(symmetries)
    eye_contact_score = round(max(0.0, min(10.0, avg_symmetry * 10)), 1)

    # posture_score: lower average shoulder angle + lower variance = better
    avg_angle = sum(shoulder_angles) / len(shoulder_angles)
    posture_score = round(max(0.0, min(10.0, 10 - (avg_angle / 3.0))), 1)

    # gesture_score: healthy band of wrist movement -- reward some motion,
    # penalize near-zero (stiff) or extreme (erratic) movement
    if len(wrist_series) >= 2:
        movements = []
        for i in range(1, len(wrist_series)):
            (lx0, ly0), (rx0, ry0) = wrist_series[i - 1]
            (lx1, ly1), (rx1, ry1) = wrist_series[i]
            movements.append(math.hypot(lx1 - lx0, ly1 - ly0) + math.hypot(rx1 - rx0, ry1 - ry0))
        avg_movement = sum(movements) / len(movements)
        # sweet spot ~0.02-0.08 (normalized coords) per sampled frame gap
        if avg_movement < 0.01:
            gesture_score = round(avg_movement / 0.01 * 5, 1)          # too stiff
        elif avg_movement <= 0.08:
            gesture_score = round(5 + (avg_movement - 0.01) / 0.07 * 5, 1)  # healthy band
        else:
            gesture_score = round(max(0.0, 10 - (avg_movement - 0.08) * 20), 1)  # too erratic
        gesture_score = max(0.0, min(10.0, gesture_score))
    else:
        gesture_score = 5.0

    engagement_score = round((eye_contact_score + posture_score + gesture_score) / 3, 1)

    return {
        "frames_analyzed": analyzed,
        "frames_with_person": frames_with_person,
        "metrics": {
            "eye_contact_score": eye_contact_score,
            "posture_score": posture_score,
            "gesture_score": gesture_score,
            "engagement_score": engagement_score,
        },
    }
