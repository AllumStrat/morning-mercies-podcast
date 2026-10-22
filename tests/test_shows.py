"""Offline checks for running more than one show from this repo.

Runs the real `next`, `stage`, and `publish-incoming` code against a throwaway copy of the
repo with a local git remote, a fake GitHub API, and fake audio. No network, no tokens.

    python3 -m unittest discover -s tests
"""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATE = "2026-10-25"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def load(root, name):
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / "podcast.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeGitHub:
    """Stands in for the GitHub API: gh-pages files and releases kept in memory."""

    def __init__(self):
        self.files, self.releases, self.deleted_branches, self.squashed = {}, {}, [], []

    def get_text(self, path):
        body = self.files.get(path)
        return body.decode() if isinstance(body, bytes) else body

    def commit(self, files, message, squash=False):
        self.squashed.append(squash)
        for path, body in files.items():
            if body is None:
                self.files.pop(path, None)
            else:
                self.files[path] = body

    def upload_episode(self, tag, title, body, mp3_path):
        self.releases[tag] = title
        return len(self.releases), f"https://github.com/o/r/releases/download/{tag}/{Path(mp3_path).name}"

    def release_exists(self, tag):
        return tag in self.releases

    def delete_episode(self, release_id, tag):
        self.releases.pop(tag, None)

    def delete_branch(self, name):
        self.deleted_branches.append(name)

    def request_pages_build(self):
        pass

    def ensure_branch(self):
        self.files.setdefault("README.md", "feed data")

    def enable_pages(self):
        self.pages_enabled = True


def fake_audio(mod):
    def synthesize(text, out_path):
        Path(out_path).write_bytes(b"\0" * 20_000)
    mod.synthesize = synthesize
    mod.mp3_duration = lambda path: 1800


class ShowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.remote = self.tmp / "remote.git"
        self.repo = self.tmp / "repo"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.remote))
        shutil.copytree(REPO, self.repo, ignore=shutil.ignore_patterns(
            ".git", "work", "incoming", "site", "node_modules", "__pycache__", "*.mp3"))
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-q", "origin", "main")
        self.gh = FakeGitHub()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_next(self, show, date, state):
        mod = load(self.repo, f"next_{show}_{date}")
        mod.load_state_readonly = lambda: json.loads(json.dumps(state)) if state else None
        mod.set_show(show)
        os.chdir(self.repo)
        mod.cmd_next(argparse.Namespace(date=date, force=False))
        return json.loads((self.repo / "work" / "today.json").read_text())

    def write_episode(self, words):
        work = self.repo / "work"
        (work / "script.txt").write_text(" ".join(["word"] * words))
        (work / "meta.json").write_text(json.dumps({
            "title": "Test episode", "summary": "s", "threads": [], "show_notes": "n",
            "sources": [{"author": "John Calvin", "work": "Commentary", "url": "https://example.invalid"}]}))

    def stage(self):
        env = {k: v for k, v in os.environ.items() if k != "SHOW"}
        out = subprocess.run([sys.executable, "scripts/podcast.py", "stage"], cwd=self.repo, env=env,
                             check=True, capture_output=True, text=True).stdout
        return json.loads(out[out.rindex("\n{") + 1:] if "\n{" in out else out)  # git's own output comes first

    def publish_branch(self, branch):
        clone = self.tmp / f"{branch.replace('/', '_')}-{len(list(self.tmp.iterdir()))}"
        git(self.tmp, "clone", "-q", "-b", branch, str(self.remote), str(clone))
        mod = load(clone, f"pub_{branch}")
        fake_audio(mod)
        mod.client = lambda: self.gh
        os.environ["SOURCE_BRANCH"] = branch
        try:
            os.chdir(clone)
            mod.set_show("")
            mod.cmd_publish_incoming(argparse.Namespace())
        finally:
            os.environ.pop("SOURCE_BRANCH", None)

    def test_grace_end_to_end(self):
        today = self.run_next("grace", DATE, None)
        self.assertEqual(today["show"], "grace")
        self.assertEqual(today["episode_number"], 1)
        self.assertIn("listener", today)

        self.write_episode(4600)
        staged = self.stage()
        self.assertEqual(staged["branch"], f"claude/episode-grace-{DATE}")
        self.assertTrue(staged["feed"].endswith("/grace/feed.xml"))

        self.publish_branch(staged["branch"])
        tag = f"ep-grace-{DATE}"
        self.assertEqual(self.gh.releases, {})               # Grace's audio lives on gh-pages, not in a release
        self.assertTrue(all(self.gh.squashed))               # and gh-pages is kept to one commit
        for path in (f"grace/audio/{tag}.mp3", "grace/state/series.json", "grace/feed.xml", "grace/cover.png",
                     f"grace/transcripts/{tag}.txt", f"grace/notes/{tag}.md"):
            self.assertIn(path, self.gh.files)
        self.assertNotIn("feed.xml", self.gh.files)          # the original show's feed is untouched
        self.assertNotIn("state/series.json", self.gh.files)
        feed = self.gh.get_text("grace/feed.xml")
        # Listed on Apple Podcasts: no block, and an owner email Apple can verify.
        self.assertNotIn("<itunes:block>", feed)
        self.assertIn("<itunes:email>jacob@allumstrategies.com</itunes:email>", feed)
        # Pages serves the MP3 as audio/mpeg with byte ranges, which Apple's player needs.
        self.assertIn(f'/grace/audio/{tag}.mp3"', feed)
        self.assertNotIn("releases/download", feed)
        self.assertEqual(len(today["readings"]), 3)          # no Old Testament track
        self.assertNotIn("Old Testament", [r["track"] for r in today["readings"]])
        self.assertEqual(self.gh.deleted_branches, [staged["branch"]])

        # The next day continues from the saved state and reads yesterday's transcript path.
        state = json.loads(self.gh.get_text("grace/state/series.json"))
        tomorrow = self.run_next("grace", "2026-10-26", state)
        self.assertEqual(tomorrow["episode_number"], 2)
        self.assertNotEqual(tomorrow["plan_day"], today["plan_day"])
        self.assertEqual(tomorrow["previous_transcript_path"], f"grace/transcripts/{tag}.txt")

    def test_grace_settings_and_feedback(self):
        folder = self.repo / "shows" / "grace"
        (folder / "settings.json").write_text(json.dumps(
            {"voice": "bf_emma", "voice_speed": 1.2, "length": "short", "jump_to": "3-4", "focus": "More on the Psalms."}))
        (folder / "feedback.jsonl").write_text(json.dumps(
            {"episode_date": "2026-10-24", "rating": "up", "note": "Loved it"}) + "\n")
        mod = load(self.repo, "settings")
        mod.set_show("grace")
        self.assertEqual(mod.CONFIG["voice"], "bf_emma")
        self.assertEqual((mod.CONFIG["target_words_min"], mod.CONFIG["target_words_max"]), mod.LENGTHS["short"])

        today = self.run_next("grace", DATE, None)
        self.assertEqual(today["plan_day"], "3-4")
        self.assertEqual(today["target_words"], list(mod.LENGTHS["short"]))
        self.assertEqual(today["listener"]["focus"], "More on the Psalms.")
        self.assertEqual(today["listener"]["recent_feedback"][0]["note"], "Loved it")

        # A saved plan day is applied once. After publishing, the next run moves forward, not back.
        self.write_episode(2300)
        self.publish_branch(self.stage()["branch"])
        state = json.loads(self.gh.get_text("grace/state/series.json"))
        self.assertEqual(self.run_next("grace", "2026-10-26", state)["plan_day"], "3-5")

    def test_grace_is_the_default_show(self):
        mod = load(self.repo, "default_show")
        args = argparse.Namespace(cmd="next", show=None)
        env = os.environ.pop("SHOW", None)
        try:
            self.assertEqual(mod.resolve_show(args), "grace")
        finally:
            if env is not None:
                os.environ["SHOW"] = env

    def test_first_episode_sets_up_pages(self):
        self.run_next("grace", DATE, None)
        self.write_episode(4600)
        self.publish_branch(self.stage()["branch"])
        self.assertIn(".nojekyll", self.gh.files)
        self.assertTrue(getattr(self.gh, "pages_enabled", False))

    def test_remake_swaps_audio_with_new_voice(self):
        self.run_next("grace", DATE, None)
        self.write_episode(4600)
        self.publish_branch(self.stage()["branch"])
        old = json.loads(self.gh.get_text("grace/state/series.json"))["episodes"][-1]

        (self.repo / "shows" / "grace" / "settings.json").write_text(json.dumps(
            {"voice": "af_bella", "voice_speed": 1.1, "show_description": "Grace's mornings.", "retention_days": 30}))
        mod = load(self.repo, "remake")
        fake_audio(mod)
        mod.client = lambda: self.gh
        os.environ["SOURCE_BRANCH"] = "claude/remake-grace-1761000000"
        try:
            os.chdir(self.repo)
            mod.set_show("grace")
            mod.cmd_remake(argparse.Namespace())
        finally:
            os.environ.pop("SOURCE_BRANCH", None)

        state = json.loads(self.gh.get_text("grace/state/series.json"))
        ep = state["episodes"][-1]
        self.assertEqual(len(state["episodes"]), 1)
        self.assertEqual((ep["voice"], ep["voice_speed"]), ("af_bella", 1.1))
        self.assertNotEqual(ep["tag"], old["tag"])
        self.assertNotEqual(ep["guid"], old["guid"])
        self.assertNotIn(old["audio_path"], self.gh.files)
        self.assertIn(ep["audio_path"], self.gh.files)
        feed = self.gh.get_text("grace/feed.xml")
        self.assertIn(f"/grace/audio/{ep['tag']}.mp3", feed)
        self.assertIn("Grace&#x27;s mornings." if "&#x27;" in feed else "Grace's mornings.", feed)
        self.assertEqual(mod.CONFIG["retention_days"], 30)
        self.assertIn("claude/remake-grace-1761000000", self.gh.deleted_branches)

    def test_replace_todays_episode(self):
        settings = self.repo / "shows" / "grace" / "settings.json"
        settings.write_text(json.dumps({"jump_to": "", "length": "medium"}))  # before the move to 9-16
        self.run_next("grace", DATE, None)
        self.write_episode(3500)
        self.publish_branch(self.stage()["branch"])
        old = json.loads(self.gh.get_text("grace/state/series.json"))["episodes"][-1]

        settings.write_text(json.dumps({"jump_to": "9-16", "length": "medium"}))
        mod = load(self.repo, "replace_next")
        mod.load_state_readonly = lambda: json.loads(self.gh.get_text("grace/state/series.json"))
        mod.set_show("grace")
        os.chdir(self.repo)
        mod.cmd_next(argparse.Namespace(date=DATE, force=True))
        today = json.loads((self.repo / "work" / "today.json").read_text())
        self.assertEqual(today["plan_day"], "9-16")
        self.assertEqual([r["passage"] for r in today["readings"]],
                         ["Luke 23:26-31", "Hebrews 9:11-28", "Proverbs 26:1-16"])
        self.write_episode(3500)
        env = {k: v for k, v in os.environ.items() if k != "SHOW"}
        subprocess.run([sys.executable, "scripts/podcast.py", "stage", "--replace"], cwd=self.repo, env=env,
                       check=True, capture_output=True)
        self.publish_branch(f"claude/episode-grace-{DATE}")

        state = json.loads(self.gh.get_text("grace/state/series.json"))
        self.assertEqual(len(state["episodes"]), 1)
        ep = state["episodes"][0]
        self.assertEqual((ep["number"], ep["plan_day"]), (1, "9-16"))
        self.assertNotEqual(ep["guid"], old["guid"])
        self.assertEqual(state["next_plan_day"], "9-17")
        self.assertEqual(state["last_jump_applied"], "9-16")
        for path in (old["audio_path"], old["transcript_path"], old["notes_path"]):
            self.assertNotIn(path, self.gh.files)
        self.assertIn(ep["audio_path"], self.gh.files)

    def test_remake_before_any_episode_is_harmless(self):
        mod = load(self.repo, "remake_empty")
        mod.client = lambda: self.gh
        os.chdir(self.repo)
        mod.set_show("grace")
        mod.cmd_remake(argparse.Namespace())
        self.assertEqual(self.gh.releases, {})

    def test_original_show_unchanged(self):
        state = {"next_plan_day": "10-20", "last_jump_applied": None, "episodes": []}
        today = self.run_next("", DATE, state)
        self.assertNotIn("show", today)
        self.write_episode(4600)
        staged = self.stage()
        self.assertEqual(staged["branch"], f"claude/episode-{DATE}")
        self.gh.files["state/series.json"] = json.dumps(state)
        self.publish_branch(staged["branch"])
        self.assertIn(f"ep-{DATE}", self.gh.releases)
        self.assertIn("feed.xml", self.gh.files)
        self.assertIn(f"releases/download/ep-{DATE}/", self.gh.get_text("feed.xml"))  # no audio_base, unchanged
        self.assertIn(f"transcripts/ep-{DATE}.txt", self.gh.files)
        self.assertFalse(any(p.startswith("grace/") for p in self.gh.files))


if __name__ == "__main__":
    unittest.main()
