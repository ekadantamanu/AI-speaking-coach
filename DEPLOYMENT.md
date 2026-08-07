# Making it accessible from anywhere

## Your path: free, GitHub-based, private (Render.com)

This is the setup the app is actually built for now -- $0/month, deployed
by connecting a GitHub repo (no domain purchase, no server administration),
and locked behind a password so it's genuinely private to you. Two other
options (a temporary tunnel, and a paid VPS) are further down if you ever
want them instead, but this section is the one to follow.

**What makes this free tier actually usable** (the app was updated
specifically for this): Render's free web services have no persistent
disk -- normally that means your practice history and downloaded models
get wiped every time the free instance restarts (which happens
automatically after ~15 minutes of inactivity, several times a day). Two
things now handle that for $0:
- `github_storage.py` -- when you set `GITHUB_TOKEN` + `GITHUB_REPO`, your
  session history is read/written straight to a file in your own GitHub
  repo via GitHub's API, instead of the local disk that Render throws away.
  Your history survives restarts, and you get free version history of
  your own progress as a side effect.
- `WHISPER_MODEL_SIZE=tiny` -- a smaller transcription model that fits
  comfortably in the free tier's 512MB RAM and re-downloads faster after
  each cold start (models themselves still can't persist without a paid
  disk, but "tiny" makes that redownload a non-issue -- seconds, not
  minutes).

And privacy is handled by the password gate already built into `app.py`
(see `login.html`) -- set `APP_PASSWORD` and nobody gets past the login
screen without it, including search engines or anyone who stumbles on the
URL.

### Step-by-step

1. **Create a private GitHub repo** (e.g. `ai-speaking-coach`) and push
   this folder to it:
   ```
   cd ai_speaking_coach
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/ai-speaking-coach.git
   git push -u origin main
   ```
   Make sure the repo is set to **Private** on GitHub (Settings → General →
   Danger Zone, or choose Private at creation) -- your code itself isn't
   sensitive, but your history file will live in this repo too.

2. **Create a fine-grained Personal Access Token** (this is what lets the
   app write to your repo): GitHub → Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token.
   - Repository access: **Only select repositories** → pick this one repo.
   - Permissions: **Contents → Read and write**. Nothing else needed.
   - Copy the token now -- GitHub only shows it once.

3. **Create a Render account** (free, [render.com](https://render.com)) and
   connect your GitHub account when prompted.

4. **New → Blueprint**, point it at your repo. Render will read the
   `render.yaml` already included in this project and pre-fill the service
   config (free plan, build/start commands, the env var names it needs).
   If you'd rather not use the Blueprint flow, **New → Web Service** works
   too -- just set Build command to `pip install -r requirements.txt` and
   Start command to `gunicorn -w 1 --threads 4 --timeout 120 app:app`.

5. **Fill in the environment variables** in Render's dashboard (these are
   the ones marked `sync: false` in `render.yaml`, meaning Render leaves
   them blank for you to type in rather than storing them in the repo):
   - `APP_PASSWORD` -- whatever password you want to log in with.
   - `SPEAKING_COACH_SECRET` -- a long random string (this signs your login
     session cookie -- don't skip it, the app ships with an insecure
     default that's fine for local use but not for anything public).
   - `GITHUB_TOKEN` -- the token from step 2.
   - `GITHUB_REPO` -- `YOUR_USERNAME/ai-speaking-coach`.

6. **Deploy.** First build takes a few minutes (installing mediapipe/opencv
   is the slow part). Render gives you a URL like
   `https://ai-speaking-coach.onrender.com`.

7. Open that URL -- you'll hit the login screen first. Enter your
   `APP_PASSWORD`, and you're in, from any device, anywhere.

### What to expect on the free tier (honest, not hidden)

- **Cold starts.** After ~15 minutes idle, the instance spins down. Your
  next visit takes 30-60+ seconds to wake back up and re-download the tiny
  Whisper/MediaPipe models. This is the real tradeoff for $0 -- totally
  fine for practicing once or twice a day, mildly annoying if you're
  session-hopping quickly.
- **Not built for heavy daily volume.** Free tier CPU (0.1 vCPU) is
  genuinely limited -- transcribing a 5-minute session may take noticeably
  longer than it did running locally on your laptop. Personal, occasional
  use is exactly what this tier is for.
- **If you outgrow it**: bump the Render plan to Starter (~$7/month) for
  an always-on instance with real resources, and you can drop
  `WHISPER_MODEL_SIZE=tiny` back to `base` for better transcription
  accuracy. Nothing else about the setup changes.

---

## Other options, if your needs change later

### Quick + free: Cloudflare Tunnel (try it from your phone *today*, no deploy)

Best for testing something right now without deploying anything. Requires
your own laptop to stay on and `app.py` running -- not a real deployment,
just a temporary public door into your local server.

```
brew install cloudflared        # or see Cloudflare's install docs for Windows/Linux
python app.py                    # in one terminal
cloudflared tunnel --url http://localhost:5000   # in another
```

Cloudflare prints a public `https://something.trycloudflare.com` URL. No
account needed, HTTPS included, free, no bandwidth cap. Downsides: the URL
changes every time you restart the tunnel, and it dies when your laptop
sleeps.

### A small always-on VPS (~$6/month, most control, no cold starts)

Best for a permanent URL with zero cold-start delay and full control, if
you decide $0 isn't worth the Render free-tier tradeoffs above.

**Resource note:** `faster-whisper` + `mediapipe`/`opencv` want at least
1GB RAM to run smoothly -- get a $6/mo droplet (1GB), not the cheapest
$4/mo (512MB) tier.

1. Provision an Ubuntu 22.04 droplet (DigitalOcean/Linode/similar).
2. `sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg nginx certbot python3-certbot-nginx`
3. Clone your repo, then `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
4. Point a domain's A record at the droplet's IP (needed for step 6 --
   Let's Encrypt won't certify a bare IP).
5. Run with gunicorn, one worker so models only load once into memory:
   ```
   export APP_PASSWORD=... SPEAKING_COACH_SECRET=...
   gunicorn -w 1 --threads 4 -b 127.0.0.1:5000 app:app
   ```
   Wrap this in a `systemd` service so it survives reboots.
6. Put nginx in front as a reverse proxy, then `sudo certbot --nginx` for
   free auto-renewing HTTPS.
7. Visit `https://yourdomain.com` -- same login screen as the Render path.

Since the VPS has a real persistent disk, you don't need `GITHUB_TOKEN`/
`GITHUB_REPO` here -- local `data/history.json` just works and survives
restarts on its own.

**Cost**: ~$6/month for the droplet, $0 for SSL (Let's Encrypt), ~$10-15/yr
if you need to buy a domain.
