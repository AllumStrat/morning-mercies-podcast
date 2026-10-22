# Daily production run

You are producing today's episode of the show named by `show_title` in `work/today.json` (Morning Mercies in this repo). Work through every step in order. Do not skip the research. Do not edit any file in this repository. Everything you write goes in `work/`, which is ignored by git. The only git operation is the one `stage` performs in step 8. No tokens, environment variables, or package installs are needed for your part.

## 1. Set up

```bash
mkdir -p work
python3 scripts/podcast.py next
```

- If `next` exits with status 3 (`already_published_today`), stop. Report that today's episode already exists.
- If it cannot read the series state, stop and report the error.
- Otherwise read `work/today.json`. It contains today's plan day, today's readings (four for Old Paths; a show can drop a track, so cover exactly the readings listed), the next plan day's readings, recent episodes with their summaries and open threads, and which authors were quoted recently.
- Read `STYLE.md` and `SOURCES.md` in full.
- Read yesterday's script with `python3 scripts/podcast.py transcript last` so you build on it and do not repeat it.

## 2. Read the passages

Fetch and read every verse of every reading in `work/today.json` in the ESV. Note the structure of each passage, its key verses, and the questions it raises. If there is an Old Testament reading, also reread the end of the previous chapter so you know where the story stands.

## 3. Research (spend real effort here)

Build `work/research.md` with these sections:

1. **Setting and background**, for each reading: date, historical situation, place in the book's structure, and relevant archaeology or culture. Go deepest on the Old Testament reading, or on the reading the show's style file names as the heart of the episode.
2. **Outline** of each passage with its key verses.
3. **Interpretive questions**, the two or three hardest or most interesting questions in each passage and how the voices answer them.
4. **Quote bank.** Every candidate quotation goes here, copied word for word from a fetched page, with author, work, and URL. Note which verse it comments on.

Minimum research per episode:
- Old Testament reading, when there is one: at least six distinct voices, including at least one Reformer or Puritan commentary (Calvin, Henry, Poole, Trapp, or Gill), a Spurgeon search on the passage's key verses, a check for any church father on the passage, and at least one modern conservative (for example Ryken, Sproul, Piper, or MacArthur).
- Each of the other readings: at least three distinct voices (a show's style file may ask for more), including a church father where one exists (they are plentiful for the Gospels, Psalms, and epistles).
- Search Ligonier (Sproul) and Desiring God (Piper) for the passages every day, and use them when they truly engage the text.
- Prefer voices not overused in `authors_quoted_in_last_12_episodes`.

Gather roughly twice as many quotes as you will use, then choose the best.

## 4. Outline the episode

Using the structure and word budget in `STYLE.md`, write a short outline at the top of `work/research.md`. List the segments, the main point of each, the quotes assigned to each, the thread from yesterday you will pick up, and any real cross-reading connection for the close.

## 5. Write the script

Write `work/script.txt` following `STYLE.md` exactly. Plain spoken text only. Target 4,500 to 5,200 words.

## 6. Review and revise

Check each of these and fix anything that fails:

- [ ] `wc -w work/script.txt` is between 4,500 and 5,200.
- [ ] Every quotation in the script appears word for word in the quote bank with a URL. Remove or paraphrase anything that does not.
- [ ] No quote is attributed to an author who did not write on that book. For example, Calvin wrote no commentary on Ecclesiastes or Song of Songs.
- [ ] If there is an Old Testament reading, its segment teaches the Old Testament passage in its own setting, with no more than two New Testament moves, each one warranted.
- [ ] No segment ends with a reflexive "this points us to Jesus" line.
- [ ] There are 8 to 14 quotations, with at least one father, one Puritan or Reformer, one Baptist, and one Presbyterian across the episode. Sproul, Spurgeon, or Piper appears if they genuinely addressed the passages.
- [ ] The opening picks up a thread from the recent episodes, and the close previews the next plan day.
- [ ] The script follows the text-to-speech rules: no markdown, lists, parentheses, URLs, em dashes, abbreviations, or "LORD" in capitals, and references are written as speech.
- [ ] Nothing from yesterday's script is repeated, whether an illustration, quote, or application.

## 7. Write the metadata

Create `work/meta.json`:

```json
{
  "title": "A short evocative title: main passages, for example 'The Scroll and the Knife: Jeremiah 36-38, Ecclesiastes 11, John 4, 1 Peter 1'",
  "summary": "Four to seven sentences recording what this episode actually taught, passage by passage, including key claims and which voices were used. Future episodes read this, so make it informative.",
  "threads": ["Things to pick up in later episodes: unfinished arcs, promised follow-ups, where each book is heading."],
  "sources": [{"author": "John Calvin", "work": "Commentary on Jeremiah, Lecture 140", "url": "https://..."}],
  "show_notes": "Two or three sentences for the podcast app's episode description."
}
```

List every quoted source in `sources`.

## 8. Stage for publishing

```bash
python3 scripts/podcast.py stage
```

This copies your script, metadata, and research into `incoming/DATE/` and pushes them to a `claude/episode-DATE` branch. A GitHub Action on that branch then makes the audio, attaches it to a GitHub Release, updates the feed and series state on `gh-pages`, deletes audio older than 60 days, and removes the branch.

- If it rejects the script as too short, expand the script with more substance from your research, not padding, and run it again.
- If the push fails, run it once more. If it fails again, stop and report the error.
- Optionally, if you can reach the feed URL printed by `stage`, wait up to 15 minutes and confirm today's title appears in it.

## 9. Report

Finish with a short report: the episode title, the plan day, the word count, the number of quotes and the authors used, the staging branch, and whether you confirmed the episode in the feed.
