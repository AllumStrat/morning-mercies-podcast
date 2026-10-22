# Morning Mercies

Grace's private daily podcast on the Navigators Bible Reading Plan, plus a small password-protected site where she leaves feedback and changes how the show sounds. It started as a copy of Old Paths (AllumStrat/old-paths-podcast) and now runs on its own.

## How it works

1. **Scheduled task (Claude Code on the web, 4:30 AM Phoenix daily).** Its prompt is `ROUTINE_PROMPT.md`. Claude runs `python3 scripts/podcast.py next --show grace`, researches the day's readings, writes the script, and runs `python3 scripts/podcast.py stage`. That pushes the episode to a `claude/episode-grace-DATE` branch. This step needs no tokens.
2. **GitHub Action (`.github/workflows/publish.yml`).** It triggers on that branch, turns the script into audio with the open Kokoro voice model on the Actions CPU, attaches the MP3 to a GitHub Release tagged `ep-grace-DATE`, updates the feed and series state on `gh-pages`, deletes audio older than 60 days, and deletes the staging branch. It uses GitHub's built-in token.
3. **GitHub Pages** serves the feed: `https://allumstrat.github.io/morning-mercies-podcast/grace/feed.xml`. The feed is marked private (`itunes_block`), so podcast directories won't list it.

**First episode:** the show sets itself up when its first episode publishes. It creates the `gh-pages` branch, uploads the cover, and tries to switch on GitHub Pages. If Pages doesn't come on by itself, open Settings, then Pages, and choose "Deploy from a branch" with `gh-pages` and `/ (root)`.

**The repo must be public** for free GitHub Pages and for podcast apps to download the audio. That also means Grace's feedback and focus notes in `shows/grace/` are publicly readable.

## Grace's settings

- `shows/grace/config.json` holds the show's fixed details (title, description, starting voice).
- `shows/grace/settings.json` (voice, speed, length, plan day, focus) and `shows/grace/feedback.jsonl` are written by the site in `site/`. Each morning's run reads them from its checkout.
- `shows/grace/STYLE.md` adjusts `STYLE.md` for her show and says how the writer uses her focus and feedback.
- With no show named, every command in this repo uses Grace's show (`"default_show": "grace"` in `config.json`). `config.json` also holds shared settings like the time zone and retention.

## The site

See `site/README.md`. It's an Astro app that runs as one Cloudflare Worker behind a password. Set `DEMO` to `"true"` to run it with sample episodes and no saving, which is how to preview it before the GitHub token exists.

## Tests

- `python3 -m unittest discover -s tests` runs `next`, `stage`, and `publish-incoming` offline against a fake GitHub.
- `cd site && npm test` checks the site's save logic offline.

## Costs

- **GitHub:** free. About 60 episodes are kept at a time.
- **Text-to-speech:** free. Kokoro runs on the GitHub Actions CPU.
- **Claude:** each daily run counts against the Claude plan's usage.

## Files

| File | Purpose |
|---|---|
| `ROUTINE_PROMPT.md` | Prompt for the daily scheduled task |
| `.github/workflows/publish.yml` | Makes the audio and publishes staged episodes |
| `INSTRUCTIONS.md` | Step-by-step workflow Claude follows each run |
| `STYLE.md`, `shows/grace/STYLE.md` | Host voice, structure, quote rules, text-to-speech rules, and Grace's adjustments |
| `SOURCES.md` | Where to find the fathers, Reformers, Puritans, and modern voices |
| `plan/navigators.json` | All 300 days of the Navigators Bible Reading Plan |
| `config.json` | Shared settings and the default show |
| `shows/grace/` | Grace's show: config, settings, feedback, style |
| `scripts/podcast.py` | `next`, `transcript`, `stage`, `publish-incoming`, `publish`, `feed` |
| `seed/cover.png` | Cover art until Grace has her own (put it at `shows/grace/cover.png`) |
| `site/` | The password-protected feedback and settings site |
