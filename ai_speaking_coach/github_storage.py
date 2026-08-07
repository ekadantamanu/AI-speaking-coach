"""
github_storage.py
Optional persistence backend for session history, using your own GitHub
repo as the "database" -- $0 cost, and specifically built for free-tier
hosts like Render, whose free web services have NO persistent disk (the
filesystem resets on every restart/redeploy, which happens automatically
after ~15 minutes of inactivity). Without this, your practice history
would quietly vanish every time the free instance spins down.

Enabled automatically when both GITHUB_TOKEN and GITHUB_REPO environment
variables are set. If they're not set, tracker.py falls back to the plain
local `data/history.json` file (fine for running on your own machine or a
VPS with a real disk).

Setup: create a private repo (can be the same repo you deploy from, or a
separate one just for data), create a fine-grained Personal Access Token
scoped ONLY to that repo with "Contents: Read and write" permission, and
set it as GITHUB_TOKEN on your host. See DEPLOYMENT.md for the full walkthrough.
"""

import base64
import json
import os

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")            # "yourname/your-repo"
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_PATH = os.environ.get("GITHUB_HISTORY_PATH", "data/history.json")

_API_ROOT = "https://api.github.com"


def enabled() -> bool:
    return bool(GITHUB_TOKEN and GITHUB_REPO)


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def _url():
    return f"{_API_ROOT}/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"


def _get_existing():
    """Returns (history_list, sha_or_None). sha is None if the file doesn't exist yet."""
    import requests
    r = requests.get(_url(), headers=_headers(), params={"ref": GITHUB_BRANCH}, timeout=15)
    if r.status_code == 404:
        return [], None
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    try:
        history = json.loads(content) if content.strip() else []
    except json.JSONDecodeError:
        history = []
    return history, data["sha"]


def load_history():
    history, _ = _get_existing()
    return history


def save_history(history_list):
    """Overwrites the file in the repo with the full history list (GitHub's
    Contents API only supports whole-file writes, not appends)."""
    import requests
    _, sha = _get_existing()
    body = {
        "message": "Update speaking coach history",
        "content": base64.b64encode(json.dumps(history_list, indent=2).encode("utf-8")).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha
    r = requests.put(_url(), headers=_headers(), json=body, timeout=15)
    r.raise_for_status()
    return r.json()
