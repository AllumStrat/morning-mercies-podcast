#!/usr/bin/env python3
"""Morning Mercies podcast pipeline (adapted from Old Paths).

Commands
  next              Print today's plan day, readings, and series context (JSON). No token needed.
  transcript        Print a previous episode's script. No token needed.
  stage             Push today's finished episode to a claude/episode-DATE branch. No token needed.
  publish-incoming  (GitHub Action) Make the audio for staged episodes and publish them.
  publish           Publish directly from work/ (needs GH_TOKEN).
  feed       Rebuild and upload feed.xml from the saved state.
  bootstrap  One-time setup: upload cover art and seed the series state.

Shows
  The repo can run more than one show. With no show named, everything works exactly as it
  always has: config.json, plan/jump_to.txt, and feed.xml at the root of gh-pages. A second
  show lives in shows/NAME/ and is chosen with `next --show NAME` (or SHOW=NAME). Later
  commands in the same run read the show from work/today.json, so only `next` needs the flag.

Environment variables (only for publish, publish-incoming, feed, bootstrap)
  GH_TOKEN or GITHUB_TOKEN        token with contents and pages write access
  GH_REPO or GITHUB_REPOSITORY    owner/repo, for example jacob/old-paths-podcast
Optional
  PAGES_URL  only if your GitHub Pages address is not https://OWNER.github.io/REPO
"""
import argparse
import asyncio
import datetime as dt
import email.utils
import json
import os
import re
import ssl
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
BASE_CONFIG = json.loads((ROOT / "config.json").read_text())
CONFIG = BASE_CONFIG
PLAN = json.loads((ROOT / "plan" / "navigators.json").read_text())
DAYS = PLAN["days"]
IDS = [d["id"] for d in DAYS]
TZ = ZoneInfo(CONFIG["timezone"])
SYSTEM_CA = "/etc/ssl/certs/ca-certificates.crt"
NAMESPACE = uuid.UUID("6f1d3c52-8a4e-4c43-9a3e-01da4ba50000")

# Per-show settings. The defaults are the original show; set_show() switches to shows/NAME/.
SHOW = ""             # "" is the original show
PREFIX = ""           # where this show's files live on gh-pages ("" or "NAME/")
STATE_KEY = "state/series.json"
JUMP_PATH = ROOT / "plan" / "jump_to.txt"
SETTINGS = {}         # what the listener saved from the settings site (shows/NAME/settings.json)

# What the settings site may change, and the word ranges behind each length.
SETTABLE = ("voice", "voice_speed", "length", "jump_to", "focus", "show_description", "retention_days")
LENGTHS = {"short": (2200, 2600), "medium": (3300, 3800), "full": (4500, 5200)}
SHOW_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


def set_show(name):
    """Point every path, tag, and setting at one show. "" (or None) is the original show."""
    global SHOW, PREFIX, STATE_KEY, JUMP_PATH, SETTINGS, CONFIG, TZ
    name = (name or "").strip()
    if not name:
        SHOW, PREFIX, STATE_KEY, JUMP_PATH, SETTINGS, CONFIG = (
            "", "", "state/series.json", ROOT / "plan" / "jump_to.txt", {}, BASE_CONFIG)
        TZ = ZoneInfo(CONFIG["timezone"])
        return
    folder = ROOT / "shows" / name
    if not SHOW_NAME.match(name) or not (folder / "config.json").exists():
        sys.exit(f"Unknown show '{name}'. Expected shows/{name}/config.json.")
    cfg = {**BASE_CONFIG, **json.loads((folder / "config.json").read_text())}
    settings = {}
    if (folder / "settings.json").exists():
        try:
            raw = json.loads((folder / "settings.json").read_text())
            settings = {k: raw[k] for k in SETTABLE if k in raw}
        except ValueError as e:
            print(f"warning: shows/{name}/settings.json is not valid JSON ({e}); using defaults", file=sys.stderr)
    if isinstance(settings.get("voice"), str) and re.fullmatch(r"[a-z]{2}_[a-z]+", settings["voice"]):
        cfg["voice"] = settings["voice"]
    try:
        cfg["voice_speed"] = min(1.5, max(0.7, float(settings.get("voice_speed", cfg.get("voice_speed", 1.0)))))
    except (TypeError, ValueError):
        pass
    if settings.get("length") in LENGTHS:
        cfg["target_words_min"], cfg["target_words_max"] = LENGTHS[settings["length"]]
    if isinstance(settings.get("show_description"), str) and settings["show_description"].strip():
        cfg["show_description"] = settings["show_description"].strip()[:600]
    try:
        cfg["retention_days"] = min(120, max(7, int(settings.get("retention_days", cfg["retention_days"]))))
    except (TypeError, ValueError):
        pass
    SHOW, PREFIX, SETTINGS, CONFIG = name, f"{name}/", settings, cfg
    STATE_KEY = PREFIX + "state/series.json"
    JUMP_PATH = folder / "jump_to.txt"
    TZ = ZoneInfo(CONFIG["timezone"])


def tag_for(date):
    return f"ep-{SHOW}-{date}" if SHOW else f"ep-{date}"


def env(name, *fallbacks):
    for key in (name,) + fallbacks:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    sys.exit(f"Missing environment variable {name}. See README.md.")


def now():
    return dt.datetime.now(TZ)


# ---------------------------------------------------------------- storage (GitHub)
#
# Text files (feed.xml, cover.png, state, transcripts, notes) live on the repo's
# gh-pages branch and are served by GitHub Pages. Each MP3 is attached to its own
# GitHub Release, so deleting the release after the retention window truly frees
# the space (deleting a committed file would leave it in git history forever).

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
DATA_BRANCH = "gh-pages"


class GitHub:
    def __init__(self):
        import requests

        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {env('GH_TOKEN', 'GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "old-paths-podcast",
        })
        if os.path.exists(SYSTEM_CA):
            self.s.verify = SYSTEM_CA  # trusts sandbox proxies as well as public CAs
        self.repo = repo_name()

    def req(self, method, url, ok=(200, 201, 204), **kw):
        if url.startswith("/"):
            url = f"{API}/repos/{self.repo}{url}"
        r = self.s.request(method, url, timeout=300, **kw)
        if r.status_code not in ok:
            raise SystemExit(f"GitHub API {method} {url} failed: {r.status_code} {r.text[:500]}")
        return r

    # ---- branch and files

    def branch_sha(self):
        r = self.req("GET", f"/git/ref/heads/{DATA_BRANCH}", ok=(200, 404))
        return r.json()["object"]["sha"] if r.status_code == 200 else None

    def ensure_branch(self):
        if self.branch_sha():
            return
        blob = self.req("POST", "/git/blobs", json={"content": "Old Paths feed data\n", "encoding": "utf-8"}).json()["sha"]
        tree = self.req("POST", "/git/trees", json={"tree": [
            {"path": "README.md", "mode": "100644", "type": "blob", "sha": blob}]}).json()["sha"]
        commit = self.req("POST", "/git/commits", json={"message": "Create feed branch", "tree": tree, "parents": []}).json()["sha"]
        self.req("POST", "/git/refs", json={"ref": f"refs/heads/{DATA_BRANCH}", "sha": commit})

    def get_text(self, path):
        r = self.req("GET", f"/contents/{path}", ok=(200, 404), params={"ref": DATA_BRANCH},
                     headers={"Accept": "application/vnd.github.raw+json"})
        return r.content.decode("utf-8") if r.status_code == 200 else None

    def commit(self, files, message):
        """Write several files to the data branch in one commit. files: {path: bytes|str}; value None deletes."""
        import base64

        head = self.branch_sha()
        base_tree = self.req("GET", f"/git/commits/{head}").json()["tree"]["sha"]
        entries = []
        for path, body in files.items():
            if body is None:
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                continue
            if isinstance(body, str):
                body = body.encode("utf-8")
            blob = self.req("POST", "/git/blobs", json={"content": base64.b64encode(body).decode(),
                                                       "encoding": "base64"}).json()["sha"]
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob})
        tree = self.req("POST", "/git/trees", json={"base_tree": base_tree, "tree": entries}).json()["sha"]
        commit = self.req("POST", "/git/commits", json={"message": message, "tree": tree, "parents": [head]}).json()["sha"]
        self.req("PATCH", f"/git/refs/heads/{DATA_BRANCH}", json={"sha": commit})

    # ---- releases (audio)

    def upload_episode(self, tag, title, body, mp3_path):
        rel = self.req("POST", "/releases", json={"tag_name": tag, "name": title, "body": body[:100000],
                                                   "make_latest": "false"}).json()
        name = Path(mp3_path).name
        with open(mp3_path, "rb") as fh:
            asset = self.req("POST", f"{UPLOADS}/repos/{self.repo}/releases/{rel['id']}/assets",
                             params={"name": name}, data=fh,
                             headers={"Content-Type": "audio/mpeg"}).json()
        return rel["id"], asset["browser_download_url"]

    def release_exists(self, tag):
        return self.req("GET", f"/releases/tags/{tag}", ok=(200, 404)).status_code == 200

    def delete_episode(self, release_id, tag):
        self.req("DELETE", f"/releases/{release_id}", ok=(204, 404))
        self.req("DELETE", f"/git/refs/tags/{tag}", ok=(204, 404, 422))

    def delete_branch(self, name):
        self.req("DELETE", f"/git/refs/heads/{name}", ok=(204, 404, 422))

    # ---- pages

    def request_pages_build(self):
        self.req("POST", "/pages/builds", ok=(201, 403, 404, 409, 422))

    def enable_pages(self):
        r = self.req("GET", "/pages", ok=(200, 404))
        if r.status_code == 200:
            return r.json().get("html_url")
        r = self.req("POST", "/pages", ok=(201, 403, 404, 409, 422),
                     json={"source": {"branch": DATA_BRANCH, "path": "/"}})
        if r.status_code == 201:
            return r.json().get("html_url")
        print("note: could not turn on GitHub Pages automatically. In the repo, open Settings, then Pages, "
              f"and choose 'Deploy from a branch' with branch '{DATA_BRANCH}' and folder '/ (root)'.", file=sys.stderr)
        return None


def client():
    return GitHub()


def repo_name():
    """owner/repo from the environment, else from the git remote (works in Claude Code's cloud sandbox)."""
    for key in ("GH_REPO", "GITHUB_REPOSITORY"):
        if os.environ.get(key, "").strip():
            return os.environ[key].strip()
    import subprocess

    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        parts = [p for p in re.split(r"[/:]", url.removesuffix(".git")) if p]
        return f"{parts[-2]}/{parts[-1]}"
    except Exception:
        sys.exit("Could not work out the GitHub repo. Set GH_REPO=owner/repo.")


def pages_url(path=""):
    base = os.environ.get("PAGES_URL", "").strip()
    if not base:
        owner, name = repo_name().split("/", 1)
        base = f"https://{owner.lower()}.github.io/{name}"
    return base.rstrip("/") + ("/" + path if path else "/")


def load_state(c):
    text = c.get_text(STATE_KEY)
    return json.loads(text) if text else None


def load_state_readonly():
    """Read series state without an API token: from the gh-pages branch via git, else from GitHub Pages."""
    import subprocess
    import urllib.request

    try:
        subprocess.run(["git", "fetch", "-q", "origin", f"+{DATA_BRANCH}:refs/remotes/origin/{DATA_BRANCH}"],
                       cwd=ROOT, check=True, capture_output=True, timeout=120)
        out = subprocess.run(["git", "show", f"origin/{DATA_BRANCH}:{STATE_KEY}"], cwd=ROOT, check=True,
                             capture_output=True, timeout=60)
        return json.loads(out.stdout.decode("utf-8"))
    except Exception as e:
        print(f"note: could not read state through git ({e}); trying GitHub Pages", file=sys.stderr)
    try:
        url = pages_url(STATE_KEY) + f"?t={int(dt.datetime.now().timestamp())}"
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"note: could not read state from {pages_url(STATE_KEY)} ({e})", file=sys.stderr)
    return None


def real_episodes(state):
    return [e for e in state.get("episodes", []) if not e.get("seed")]


# ---------------------------------------------------------------- plan

def plan_day(day_id):
    return DAYS[IDS.index(day_id)]


def next_id(day_id):
    i = IDS.index(day_id)
    return IDS[(i + 1) % len(IDS)]


def read_jump():
    value = None
    if SETTINGS.get("jump_to"):
        value = str(SETTINGS["jump_to"]).strip()
    elif JUMP_PATH.exists():
        lines = [l.strip() for l in JUMP_PATH.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]
        value = lines[-1] if lines else None
    if not value:
        return None
    if value not in IDS:
        print(f"warning: jump value '{value}' is not a valid plan day; ignoring", file=sys.stderr)
        return None
    return value


def new_state(start):
    return {"created": now().isoformat(), "next_plan_day": start, "last_jump_applied": None, "episodes": []}


def first_plan_day(today=None):
    """Where a brand-new show starts: its saved plan day, else its config's start, else today's spot in the plan.
    The plan gives each month 25 days, so the 26th to the 31st map to the month's last plan day."""
    for value in (SETTINGS.get("jump_to"), CONFIG.get("start_plan_day")):
        if value in IDS:
            return value
    today = today or now().date()
    month = [i for i in IDS if i.split("-")[0] == str(today.month)]
    fit = [i for i in month if int(i.split("-")[1]) <= today.day]
    return fit[-1] if fit else (month[0] if month else IDS[0])


def listener_feedback(limit=15):
    """The listener's recent notes from the settings site (shows/NAME/feedback.jsonl), newest last."""
    path = ROOT / "shows" / SHOW / "feedback.jsonl" if SHOW else None
    if not path or not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows[-limit:]


# ---------------------------------------------------------------- next

def cmd_next(args):
    state = load_state_readonly()
    if state is None and SHOW:
        state = new_state(first_plan_day(dt.date.fromisoformat(args.date) if args.date else None))
        print(f"note: no episodes yet for show '{SHOW}'; starting at plan day {state['next_plan_day']}", file=sys.stderr)
    if state is None:
        sys.exit("No series state found. Has bootstrap been run? (see README.md)")

    jump = read_jump()
    jump_applied = None
    day_id = state["next_plan_day"]
    if jump and jump != state.get("last_jump_applied"):
        day_id, jump_applied = jump, jump
        print(f"note: jumping to plan day {jump} from plan/jump_to.txt", file=sys.stderr)

    today = args.date or now().date().isoformat()
    episodes = state.get("episodes", [])
    if any(e["date"] == today for e in real_episodes(state)) and not args.force:
        print(json.dumps({"status": "already_published_today", "date": today}))
        sys.exit(3)

    day = plan_day(day_id)
    tomorrow = plan_day(next_id(day_id))
    recent_sources = {}
    for ep in episodes[-12:]:
        for name in ep.get("authors", []):
            recent_sources[name] = recent_sources.get(name, 0) + 1

    context = {
        "status": "ok",
        "date": today,
        "weekday": dt.date.fromisoformat(today).strftime("%A"),
        "episode_number": len(episodes) + 1,
        "plan_day": day_id,
        "jump_applied": jump_applied,
        "plan_position": f"Day {IDS.index(day_id) + 1} of {len(IDS)} (Month {day_id.split('-')[0]}, Day {day_id.split('-')[1]})",
        "readings": day["readings"],
        "next_plan_day_preview": tomorrow["readings"],
        "recent_episodes": [
            {k: ep.get(k) for k in ("number", "date", "plan_day", "title", "readings", "summary", "threads")}
            for ep in episodes[-6:]
        ],
        "previous_transcript_path": episodes[-1].get("transcript_path") if episodes else None,
        "authors_quoted_in_last_12_episodes": dict(sorted(recent_sources.items(), key=lambda kv: -kv[1])),
        "target_words": [CONFIG["target_words_min"], CONFIG["target_words_max"]],
    }
    if SHOW:
        context["show"] = SHOW
        context["show_title"] = CONFIG["show_title"]
        context["listener"] = {
            "name": CONFIG.get("listener_name", ""),
            "style_notes_file": f"shows/{SHOW}/STYLE.md",
            "focus": str(SETTINGS.get("focus", "")).strip(),
            "length": SETTINGS.get("length", "full"),
            "recent_feedback": listener_feedback(),
        }
    WORK.mkdir(exist_ok=True)
    (WORK / "today.json").write_text(json.dumps(context, indent=1))
    print(json.dumps(context, indent=1))


def cmd_transcript(args):
    import subprocess

    state = load_state_readonly() or {}
    eps = state.get("episodes", [])
    if not eps:
        sys.exit("No episodes yet.")
    ep = eps[-1] if args.which == "last" else next((e for e in eps if e["date"] == args.which), None)
    if not ep or not ep.get("transcript_path"):
        sys.exit("Transcript not found.")
    out = subprocess.run(["git", "show", f"origin/{DATA_BRANCH}:{ep['transcript_path']}"], cwd=ROOT,
                         capture_output=True)
    if out.returncode == 0:
        print(out.stdout.decode("utf-8"))
    else:
        import urllib.request
        with urllib.request.urlopen(pages_url(ep["transcript_path"]), timeout=60) as r:
            print(r.read().decode("utf-8"))


# ---------------------------------------------------------------- tts

def clean_for_speech(text):
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.M)        # markdown headings
    text = re.sub(r"[*_`]+", "", text)                        # emphasis marks
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)           # links
    text = text.replace("\u2014", ", ").replace("\u2013", " to ")
    text = re.sub(r"\bLORD\b", "Lord", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def patch_edge_tts_ssl():
    """edge-tts pins certifi's bundle; on Linux sandboxes behind a TLS proxy, use the system bundle."""
    if not os.path.exists(SYSTEM_CA):
        return
    import edge_tts.communicate as communicate

    communicate._SSL_CTX = ssl.create_default_context(cafile=SYSTEM_CA)


async def _synthesize(text, out_path):
    import edge_tts

    await edge_tts.Communicate(text, CONFIG["edge_voice"], rate=CONFIG["edge_rate"]).save(str(out_path))


def synthesize(text, out_path):
    if CONFIG.get("tts", "edge") == "kokoro":
        try:
            return synthesize_kokoro(text, out_path)
        except Exception as e:  # keep publishing on schedule; the Edge voice is the fallback
            print(f"Kokoro failed ({e!r}); falling back to Edge TTS", file=sys.stderr)
    patch_edge_tts_ssl()
    last = None
    for attempt in range(1, 4):
        try:
            asyncio.run(_synthesize(text, out_path))
            if out_path.exists() and out_path.stat().st_size > 10_000:
                return
            last = RuntimeError("TTS produced an empty or tiny file")
        except Exception as e:  # network hiccups from the TTS service
            last = e
        print(f"TTS attempt {attempt} failed: {last}", file=sys.stderr)
    raise SystemExit(f"Text-to-speech failed after 3 attempts: {last}")


ESPEAK_LIBS = ["/opt/homebrew/lib/libespeak-ng.dylib", "/usr/local/lib/libespeak-ng.dylib"]
ESPEAK_DATA_DIRS = ["/usr/lib/x86_64-linux-gnu/espeak-ng-data", "/usr/lib/aarch64-linux-gnu/espeak-ng-data",
                    "/usr/share/espeak-ng-data", "/opt/homebrew/share/espeak-ng-data", "/usr/local/share/espeak-ng-data"]


def use_system_espeak():
    """misaki points phonemizer at espeakng-loader's bundled espeak-ng, whose baked-in data path
    is broken in some wheels. Prefer a system espeak-ng (apt or Homebrew) when one is installed."""
    import ctypes.util

    import misaki.espeak  # noqa: F401  (sets the bundled paths on import; overridden below)
    from phonemizer.backend.espeak.wrapper import EspeakWrapper

    lib = ctypes.util.find_library("espeak-ng") or next((l for l in ESPEAK_LIBS if os.path.exists(l)), None)
    data = next((d for d in ESPEAK_DATA_DIRS if os.path.exists(os.path.join(d, "phontab"))), None)
    if lib and data:
        EspeakWrapper.set_library(lib)
        EspeakWrapper.set_data_path(data)


def synthesize_kokoro(text, out_path):
    """Render with the Kokoro-82M open model on the CPU, paragraph by paragraph, then encode to MP3."""
    import subprocess

    import numpy as np
    import soundfile as sf

    use_system_espeak()
    from kokoro import KPipeline

    voice = CONFIG["voice"]
    pipe = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M", device="cpu")
    pause = np.zeros(int(24000 * 0.45), dtype=np.float32)
    parts = []
    for para in (p.strip() for p in re.split(r"\n\s*\n", text)):
        if not para:
            continue
        for _, _, audio in pipe(para, voice=voice, speed=float(CONFIG.get("voice_speed", 1.0))):
            if audio is not None:
                parts.append(np.asarray(audio, dtype=np.float32))
        parts.append(pause)
    if not parts:
        raise RuntimeError("Kokoro produced no audio")

    wav = Path(out_path).with_suffix(".wav")
    sf.write(str(wav), np.concatenate(parts), 24000)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-b:a", "64k", str(out_path)],
                   check=True)
    wav.unlink()


def mp3_duration(path):
    from mutagen.mp3 import MP3

    return int(MP3(str(path)).info.length)


# ---------------------------------------------------------------- publish

def episode_guid(date):
    return str(uuid.uuid5(NAMESPACE, f"old-paths-{date}"))


def show_notes_text(meta):
    parts = []
    if meta.get("show_notes"):
        parts.append(meta["show_notes"].strip())
    if meta.get("sources"):
        parts.append("Sources quoted:")
        for src in meta["sources"]:
            line = " - " + ", ".join(x for x in (src.get("author"), src.get("work")) if x)
            if src.get("url"):
                line += f" ({src['url']})"
            parts.append(line)
    return "\n".join(parts)


def add_episode(state, *, date, day_id, meta, tag, release_id, mp3_url, size, duration, published):
    number = len(state["episodes"]) + 1
    readings = meta.get("readings") or ([r["passage"] for r in plan_day(day_id)["readings"]] if day_id in IDS else [])
    state["episodes"].append({
        "number": number,
        "date": date,
        "published": published,
        "plan_day": day_id,
        "readings": readings,
        "title": meta["title"],
        "summary": meta.get("summary", ""),
        "threads": meta.get("threads", []),
        "authors": sorted({src.get("author", "").strip() for src in meta.get("sources", []) if src.get("author")}),
        "description": (", ".join(readings) + "\n\n" + show_notes_text(meta)).strip(),
        "tag": tag,
        "release_id": release_id,
        "mp3_url": mp3_url,
        "bytes": size,
        "duration": duration,
        "transcript_path": f"{PREFIX}transcripts/{tag}.txt",
        "notes_path": f"{PREFIX}notes/{tag}.md",
        "guid": episode_guid(tag),
        "audio_deleted": False,
    })
    return state["episodes"][-1]


def prune(c, state):
    """Delete the audio (the GitHub Release) for episodes older than the retention window."""
    cutoff = now().date() - dt.timedelta(days=int(CONFIG["retention_days"]))
    removed = 0
    for ep in state["episodes"]:
        if not ep.get("audio_deleted") and dt.date.fromisoformat(ep["date"]) < cutoff:
            c.delete_episode(ep["release_id"], ep["tag"])
            ep["audio_deleted"] = True
            removed += 1
    return removed


def validate(raw, meta, allow_short=False):
    for field in ("title", "summary", "threads", "sources"):
        if field not in meta:
            sys.exit(f"meta.json is missing '{field}'")
    words = len(raw.split())
    lo, hi = CONFIG["target_words_min"], CONFIG["target_words_max"]
    if words < lo * 0.85 and not allow_short:
        sys.exit(f"Script is {words} words; target is {lo}-{hi}. Expand it, or pass --allow-short.")
    return words


def publish_episode(c, *, date, raw, meta, research="", plan_day_id=None, jump_applied=None, force=False):
    state = load_state(c)
    first_files = {}
    if state is None and SHOW:
        # A new show sets itself up on its first episode: state, cover art, and feed under PREFIX.
        state = new_state(plan_day_id or first_plan_day())
        c.ensure_branch()  # a brand-new repo has no gh-pages branch yet
        first_files[PREFIX + "cover.png"] = cover_bytes()
        first_files[".nojekyll"] = ""
    if state is None:
        sys.exit("No series state found. Run bootstrap first.")
    if any(e["date"] == date for e in real_episodes(state)) and not force:
        print(f"An episode for {date} already exists; skipping.", file=sys.stderr)
        return None
    if jump_applied:
        state["last_jump_applied"] = jump_applied
    day_id = plan_day_id or state["next_plan_day"]
    tag = tag_for(date) + ("" if not force else "-" + now().strftime("%H%M%S"))
    if c.release_exists(tag):
        tag = f"{tag_for(date)}-{day_id}"  # an earlier episode was re-dated and still holds this tag

    WORK.mkdir(exist_ok=True)
    mp3 = WORK / f"{SHOW or 'old-paths'}-{date}.mp3"
    synthesize(clean_for_speech(raw), mp3)
    size, duration = mp3.stat().st_size, mp3_duration(mp3)
    print(f"audio: {size/1e6:.1f} MB, {duration//60}:{duration%60:02d}", file=sys.stderr)

    release_id, mp3_url = c.upload_episode(tag, meta["title"], show_notes_text(meta), mp3)
    ep = add_episode(state, date=date, day_id=day_id, meta=meta, tag=tag, release_id=release_id, mp3_url=mp3_url,
                     size=size, duration=duration, published=email.utils.format_datetime(now()))
    state["next_plan_day"] = next_id(day_id) if day_id in IDS else state["next_plan_day"]
    removed = prune(c, state)
    c.commit({
        **first_files,
        ep["transcript_path"]: raw,
        ep["notes_path"]: show_notes_text(meta) + ("\n\n---\nResearch notes\n\n" + research if research else ""),
        STATE_KEY: json.dumps(state, indent=1),
        PREFIX + "feed.xml": build_feed(state),
    }, f"{CONFIG['show_title'] + ' e' if SHOW else 'E'}pisode {ep['number']}: {meta['title']}")
    if first_files:
        c.enable_pages()
    c.request_pages_build()
    result = {"status": "published", "show": SHOW or "default", "episode": ep["number"], "plan_day": day_id,
              "next_plan_day": state["next_plan_day"], "audio": mp3_url,
              "feed": pages_url(PREFIX + "feed.xml"), "pruned_old_episodes": removed}
    print(json.dumps(result, indent=1))
    return result


def cmd_publish(args):
    """Publish directly (needs GH_TOKEN). Used for manual runs."""
    raw = Path(args.script).read_text()
    meta = json.loads(Path(args.meta).read_text())
    print(f"script words: {validate(raw, meta, args.allow_short)}", file=sys.stderr)
    research = Path(args.research).read_text() if args.research and Path(args.research).exists() else ""
    today = {}
    if (WORK / "today.json").exists():
        today = json.loads((WORK / "today.json").read_text())
    publish_episode(client(), date=args.date or today.get("date") or now().date().isoformat(), raw=raw, meta=meta,
                    research=research, plan_day_id=today.get("plan_day"), jump_applied=today.get("jump_applied"),
                    force=args.force)


def cmd_stage(args):
    """Scheduled-task side: package today's episode and push it to a claude/episode-DATE branch.
    The GitHub Action on that branch does the audio, release, feed, and cleanup."""
    import shutil
    import subprocess

    today = json.loads((WORK / "today.json").read_text())
    raw = (WORK / "script.txt").read_text()
    meta = json.loads((WORK / "meta.json").read_text())
    words = validate(raw, meta, args.allow_short)
    date = args.date or today["date"]
    folder = ROOT / "incoming" / date
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(WORK / "script.txt", folder / "script.txt")
    shutil.copy(WORK / "meta.json", folder / "meta.json")
    if (WORK / "research.md").exists():
        shutil.copy(WORK / "research.md", folder / "research.md")
    (folder / "plan.json").write_text(json.dumps({"plan_day": today["plan_day"],
                                                  "jump_applied": today.get("jump_applied"),
                                                  **({"show": SHOW} if SHOW else {})}, indent=1))
    branch = f"claude/episode-{SHOW}-{date}" if SHOW else f"claude/episode-{date}"

    def git(*a):
        print("+ git " + " ".join(a), file=sys.stderr)
        subprocess.run(["git", *a], cwd=ROOT, check=True)

    git("checkout", "-B", branch)
    git("add", "-f", f"incoming/{date}")
    git("-c", "user.name=Old Paths", "-c", "user.email=old-paths@users.noreply.github.com",
        "commit", "-m", f"Stage episode for {date}: {meta['title']}")
    git("push", "-f", "-u", "origin", branch)
    print(json.dumps({"status": "staged", "show": SHOW or "default", "date": date, "branch": branch, "words": words,
                      "feed": pages_url(PREFIX + "feed.xml"),
                      "note": "The 'Publish episode' GitHub Action now makes the audio and updates the feed (about 5-10 minutes)."},
                     indent=1))


def cmd_publish_incoming(args):
    """GitHub Action side: publish every staged episode in incoming/, then delete the staging branch."""
    c = client()
    folders = sorted(p for p in (ROOT / "incoming").glob("*") if p.is_dir()) if (ROOT / "incoming").exists() else []
    if not folders:
        print("Nothing staged in incoming/.")
    for folder in folders:
        raw = (folder / "script.txt").read_text()
        meta = json.loads((folder / "meta.json").read_text())
        plan = json.loads((folder / "plan.json").read_text()) if (folder / "plan.json").exists() else {}
        research = (folder / "research.md").read_text() if (folder / "research.md").exists() else ""
        set_show(plan.get("show"))
        validate(raw, meta, allow_short=True)
        publish_episode(c, date=folder.name, raw=raw, meta=meta, research=research,
                        plan_day_id=plan.get("plan_day"), jump_applied=plan.get("jump_applied"))
    branch = os.environ.get("SOURCE_BRANCH", "")
    if branch.startswith("claude/episode-"):
        c.delete_branch(branch)
        print(f"deleted staging branch {branch}")


def cmd_remake(args):
    """GitHub Action side: render the newest episode again with the show's current voice and speed.
    The settings site asks for this by pushing a claude/remake-SHOW-TIME branch."""
    c = client()
    state = load_state(c)
    live = [e for e in real_episodes(state or {}) if not e.get("audio_deleted")]
    if not live:
        print("No episode to remake yet; the next one will use the saved settings.")
    else:
        ep = live[-1]
        raw = c.get_text(ep["transcript_path"])
        if not raw:
            sys.exit(f"Transcript {ep['transcript_path']} is missing; cannot remake episode {ep['number']}.")
        WORK.mkdir(exist_ok=True)
        mp3 = WORK / f"{SHOW or 'old-paths'}-{ep['date']}.mp3"
        synthesize(clean_for_speech(raw), mp3)
        size, duration = mp3.stat().st_size, mp3_duration(mp3)
        tag = f"{tag_for(ep['date'])}-r{now().strftime('%H%M%S')}"
        old_release, old_tag = ep["release_id"], ep["tag"]
        release_id, mp3_url = c.upload_episode(tag, ep["title"], ep["description"], mp3)
        # A new guid makes podcast apps fetch the new audio instead of keeping the old download.
        ep.update(tag=tag, release_id=release_id, mp3_url=mp3_url, bytes=size, duration=duration,
                  guid=episode_guid(tag), voice=CONFIG["voice"], voice_speed=CONFIG.get("voice_speed", 1.0),
                  remade=email.utils.format_datetime(now()))
        c.commit({STATE_KEY: json.dumps(state, indent=1), PREFIX + "feed.xml": build_feed(state)},
                 f"{CONFIG['show_title']}: remake episode {ep['number']} ({CONFIG['voice']}, {CONFIG.get('voice_speed', 1.0)}x)")
        c.delete_episode(old_release, old_tag)
        c.request_pages_build()
        print(json.dumps({"status": "remade", "show": SHOW or "default", "episode": ep["number"], "audio": mp3_url,
                          "voice": CONFIG["voice"], "voice_speed": CONFIG.get("voice_speed", 1.0),
                          "feed": pages_url(PREFIX + "feed.xml")}, indent=1))
    branch = os.environ.get("SOURCE_BRANCH", "")
    if branch.startswith("claude/remake-"):
        c.delete_branch(branch)
        print(f"deleted request branch {branch}")


# ---------------------------------------------------------------- feed

def fmt_duration(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def cdata(text):
    return "<![CDATA[" + text.replace("]]>", "]] >") + "]]>"


def enclosure_url(ep):
    """Where podcast apps fetch the audio. A show with audio_base gets it through the settings
    site's /audio/ route, which serves GitHub's release file as audio/mpeg so Apple can play it."""
    base, marker = CONFIG.get("audio_base"), "/releases/download/"
    if base and marker in ep["mp3_url"]:
        return base.rstrip("/") + "/audio/" + ep["mp3_url"].split(marker, 1)[1]
    return ep["mp3_url"]


def build_feed(state):
    cfg = CONFIG
    items = []
    for ep in reversed(state["episodes"]):
        if ep.get("audio_deleted"):
            continue
        items.append(f"""    <item>
      <title>{escape(ep['title'])}</title>
      <description>{cdata(ep['description'])}</description>
      <itunes:summary>{cdata(ep['description'])}</itunes:summary>
      <enclosure url="{escape(enclosure_url(ep))}" length="{ep['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{ep['guid']}</guid>
      <pubDate>{ep['published']}</pubDate>
      <itunes:duration>{fmt_duration(ep['duration'])}</itunes:duration>
      <itunes:episode>{ep['number']}</itunes:episode>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    owner = (f"<itunes:owner><itunes:name>{escape(cfg['author'])}</itunes:name>"
             f"<itunes:email>{escape(cfg['owner_email'])}</itunes:email></itunes:owner>") if cfg.get("owner_email") else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:googleplay="http://www.google.com/schemas/play-podcasts/1.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(cfg['show_title'])}</title>
    <link>{escape(pages_url(PREFIX))}</link>
    <atom:link href="{escape(pages_url(PREFIX + 'feed.xml'))}" rel="self" type="application/rss+xml"/>
    <description>{escape(cfg['show_description'])}</description>
    <language>{cfg['language']}</language>
    <itunes:subtitle>{escape(cfg['show_subtitle'])}</itunes:subtitle>
    <itunes:author>{escape(cfg['author'])}</itunes:author>
    {owner}
    <itunes:image href="{escape(pages_url(PREFIX + 'cover.png'))}"/>
    <itunes:category text="Religion &amp; Spirituality"><itunes:category text="Christianity"/></itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <googleplay:block>yes</googleplay:block>{chr(10) + '    <itunes:block>Yes</itunes:block>' if cfg.get('itunes_block') else ''}
    <lastBuildDate>{email.utils.format_datetime(now())}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""


def cmd_feed(args):
    c = client()
    state = load_state(c)
    if state is None:
        sys.exit("No series state found.")
    files = {PREFIX + "feed.xml": build_feed(state)}
    if SHOW and (ROOT / "shows" / SHOW / "cover.png").exists():
        files[PREFIX + "cover.png"] = cover_bytes()
    c.commit(files, "Rebuild feed")
    print(pages_url(PREFIX + "feed.xml"))


# ---------------------------------------------------------------- bootstrap

def cover_bytes():
    own = ROOT / "shows" / SHOW / "cover.png" if SHOW else None
    return (own if own and own.exists() else ROOT / "seed" / "cover.png").read_bytes()


def cmd_bootstrap(args):
    c = client()
    c.ensure_branch()
    if load_state(c) and not args.force:
        sys.exit("Series state already exists. Pass --force to overwrite it.")
    if args.start not in IDS:
        sys.exit(f"--start must be a plan day like 10-14; got {args.start}")

    state = {"created": now().isoformat(), "next_plan_day": args.start, "last_jump_applied": read_jump(), "episodes": []}
    files = {PREFIX + "cover.png": cover_bytes(), ".nojekyll": ""}

    if args.seed_mp3 and Path(args.seed_mp3).exists() and not SHOW:
        meta = json.loads(Path(args.seed_meta).read_text())
        date = meta.get("date") or now().date().isoformat()
        tag = tag_for(date)
        mp3 = Path(args.seed_mp3)
        release_id, mp3_url = c.upload_episode(tag, meta["title"], show_notes_text(meta), mp3)
        published = email.utils.format_datetime(dt.datetime.fromisoformat(date + "T06:00:00").replace(tzinfo=TZ))
        ep = add_episode(state, date=date, day_id=meta.get("plan_day", "seed"), meta=meta, tag=tag,
                         release_id=release_id, mp3_url=mp3_url, size=mp3.stat().st_size,
                         duration=mp3_duration(mp3), published=published)
        ep["seed"] = True
        if Path(args.seed_script).exists():
            files[ep["transcript_path"]] = Path(args.seed_script).read_text()
        files[ep["notes_path"]] = show_notes_text(meta)

    files[STATE_KEY] = json.dumps(state, indent=1)
    files[PREFIX + "feed.xml"] = build_feed(state)
    c.commit(files, "Bootstrap Old Paths feed")
    site = c.enable_pages()
    c.request_pages_build()
    print(json.dumps({"status": "bootstrapped", "next_plan_day": state["next_plan_day"],
                      "episodes": len(state["episodes"]), "pages_site": site or pages_url(),
                      "feed": pages_url(PREFIX + "feed.xml"),
                      "note": "GitHub Pages can take a few minutes to go live the first time."}, indent=1))


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("next")
    n.add_argument("--force", action="store_true", help="run even if an episode already exists for today")
    n.add_argument("--date", help="treat this date (YYYY-MM-DD) as today")
    n.add_argument("--show", help="a show in shows/NAME/ (default: the original show)")
    n.set_defaults(func=cmd_next)

    st = sub.add_parser("stage", help="push today's finished episode to a claude/episode-DATE branch")
    st.add_argument("--date")
    st.add_argument("--allow-short", action="store_true")
    st.set_defaults(func=cmd_stage)

    pi = sub.add_parser("publish-incoming", help="(GitHub Action) publish staged episodes")
    pi.set_defaults(func=cmd_publish_incoming)

    rm = sub.add_parser("remake", help="(GitHub Action) render the newest episode again with current settings")
    rm.add_argument("--show")
    rm.set_defaults(func=cmd_remake)

    t = sub.add_parser("transcript")
    t.add_argument("which", nargs="?", default="last", help="'last' or a date like 2026-10-19")
    t.set_defaults(func=cmd_transcript)

    pub = sub.add_parser("publish")
    pub.add_argument("--script", default="work/script.txt")
    pub.add_argument("--meta", default="work/meta.json")
    pub.add_argument("--research", default="work/research.md")
    pub.add_argument("--date")
    pub.add_argument("--allow-short", action="store_true")
    pub.add_argument("--force", action="store_true")
    pub.set_defaults(func=cmd_publish)

    f = sub.add_parser("feed")
    f.set_defaults(func=cmd_feed)

    b = sub.add_parser("bootstrap")
    b.add_argument("--start", default="10-14", help="first plan day the daily task should produce")
    b.add_argument("--seed-mp3", default=str(ROOT / "seed" / "episode-000.mp3"))
    b.add_argument("--seed-script", default=str(ROOT / "seed" / "episode-000.txt"))
    b.add_argument("--seed-meta", default=str(ROOT / "seed" / "episode-000.json"))
    b.add_argument("--force", action="store_true")
    b.set_defaults(func=cmd_bootstrap)

    args = p.parse_args()
    os.chdir(ROOT)
    set_show(resolve_show(args))
    args.func(args)


def resolve_show(args):
    """--show, else SHOW, else the show today's `next` picked (work/today.json), else config.json's
    default_show (in this repo, Grace's show), else the original show.
    publish-incoming ignores all of these and takes the show from each staged folder."""
    if getattr(args, "show", None) is not None:
        return args.show
    if os.environ.get("SHOW", "").strip():
        return os.environ["SHOW"].strip()
    if args.cmd in ("stage", "transcript", "publish") and (WORK / "today.json").exists():
        try:
            return json.loads((WORK / "today.json").read_text()).get("show", "")
        except ValueError:
            pass
    return BASE_CONFIG.get("default_show", "")


if __name__ == "__main__":
    main()
