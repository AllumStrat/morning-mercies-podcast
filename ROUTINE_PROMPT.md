Produce today's episode of Morning Mercies, Grace's show.

Open INSTRUCTIONS.md in this repository and follow it from step 1 through step 9, in order, with these changes:

- In step 1, run `python3 scripts/podcast.py next --show grace` instead of plain `next`. Every later `podcast.py` command picks up the show from work/today.json, so run them exactly as INSTRUCTIONS.md shows.
- In step 1, read STYLE.md and SOURCES.md, then read shows/grace/STYLE.md. Where it differs from STYLE.md, shows/grace/STYLE.md wins.
- Use `target_words` from work/today.json as the word range everywhere INSTRUCTIONS.md says 4,500 to 5,200, including the step 6 check.
- Read the `listener` block in work/today.json and follow shows/grace/STYLE.md on how to use Grace's focus and feedback.

Do the research thoroughly before writing. Quote only what you fetched and logged with a URL. Do not edit repository files; work only inside the work/ folder. Finish by running `python3 scripts/podcast.py stage`, which pushes the episode to a claude/episode-grace-DATE branch for the publishing workflow, and then report the result.
