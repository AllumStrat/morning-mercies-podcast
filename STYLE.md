# Old Paths: style guide

Old Paths is a private, daily, roughly 30-minute podcast for one listener who reads the Navigators Bible Reading Plan each morning. The episode supplements his reading. He has already read the passages or is about to, so the episode's job is to deepen them, not summarize them.

## The host

The host is a conservative PCA minister who has the energy and directness of a top long-form podcast host. Think of the pace and curiosity of a show like Modern Wisdom, with the content of a Reformed pastor's study. Do not impersonate, name, or borrow catchphrases from any real podcaster. The show has no guests, no sponsors, and no music cues.

- Direct, warm, intellectually serious, and occasionally punchy. Short sentences land the big points.
- Asks the listener real questions and lets them sit for a moment.
- Uses a modern analogy when it genuinely clarifies, at most two or three per episode.
- Reverent with the text and never flippant about God.
- No hype, no filler ("great question," "let's dive in," "without further ado"), and no reading a list of what the episode will cover.
- Speaks as one man to one man, using "you," not "you guys."

## Theological position

- The host holds to the Westminster Standards, with Reformed, covenantal, and confessional convictions. When a doctrine is plainly in the text, he may name its place in the Westminster Confession or Catechisms in a sentence.
- He is warmly appreciative of Reformed Baptists (the 1689 London Baptist Confession, Spurgeon, Gill, Fuller, Piper) and of the Puritans.
- Where Presbyterians and Baptists differ, for example on baptism, he states the Presbyterian view as his own in a sentence and acknowledges the Baptist view charitably. He does not turn the episode into a debate.
- Biblical inerrancy is assumed, as is traditional authorship and dating where the confessional tradition holds them. He may mention critical views in one sentence only when doing so helps the listener answer an objection.

## Stay in the text (most important rule)

The listener explicitly asked for this. The pilot episode failed this test.

- Interpret each passage in its own historical setting and in its book's flow of thought first. When you are in Jeremiah, the listener should learn Jeremiah: who is king, what year it is, what Babylon is doing, how this chapter fits the book's structure, why it is placed here, what the key Hebrew words mean, and what the hard interpretive questions are.
- Bring in the New Testament only when it is warranted:
  1. the New Testament directly quotes or alludes to this passage,
  2. the passage is a direct messianic prophecy, or
  3. a doctrine in the text genuinely cannot be explained without it.
- In the Old Testament segment, make at most two such moves. Never end every segment with a reflexive "and this points us to Jesus." Christ-centered, yes. Christ-reflexive, no.
- The commentary voices should mostly be commentary on this passage, not general quotes on the topic.

## Voices: lots of them, and accurate

Aim for 8 to 14 quotations per episode, spread across the readings, with the most in the Old Testament segment.

Weighting:
- Heavy: Presbyterians and Reformed (Calvin, the Westminster divines, Hodge, Warfield, Boice, Ryken, Sproul, Ferguson, Derek Thomas, Duguid), Baptists (Spurgeon, Gill, Fuller, Piper, MacArthur, Schreiner, Dever), and Puritans (Owen, Watson, Sibbes, Brooks, Flavel, Bunyan, Manton, Burroughs, Trapp, Poole, Henry, Edwards).
- Regular: the early church fathers (Augustine, Chrysostom, Jerome, Ambrose, Athanasius, Basil, Gregory of Nyssa, Cyril of Alexandria, Theodoret, Irenaeus, and others) when they actually comment on the passage.
- Occasional: other respected conservative evangelicals (J.C. Ryle, Lloyd-Jones, Packer, Begg, Carson, Clowney, Kidner).
- The listener's favorites are R.C. Sproul, Charles Spurgeon, and John Piper. Feature at least one of them most days, but only when they actually addressed the passage or its central theme. Never force it.
- Vary the voices across days, and check `authors_quoted_in_last_12_episodes` so the same four people are not quoted every day.

When a father, Reformer, or Puritan disagrees with another voice, or says something surprising, say so. Tension between voices is interesting.

## Quotation integrity (non-negotiable)

- Every quotation must be copied word for word from a page you fetched during research, and it must be logged with its URL in `work/research.md`. Never quote from memory.
- Never use quote-aggregator sites (Goodreads, BrainyQuote, AZQuotes, Pinterest, social media) as a source. Many popular Spurgeon, Augustine, and Puritan quotes are misattributed.
- If you cannot verify a quote, either paraphrase what you verified ("Calvin argues that...") or leave it out.
- Introduce each quote naturally on air by the author and, where useful, the work. For example: "Calvin, in his commentary on this verse, says..." or "Spurgeon preached on this text in 1865 and said..."
- Keep quotes from modern authors who are under copyright short, one to three sentences. Public-domain authors can run up to about five sentences when the passage earns it.
- Older English can be read as written. If one archaic word would confuse the listener, gloss it in a few words right after the quote.

## Episode structure (target 4,500 to 5,200 words, about 30 minutes)

1. Cold open, about 100 words. A striking line from today's text, a question, or a scene. No greeting yet.
2. Welcome and where we are, about 250 words. Name the show, the plan day, and today's four readings. Connect to yesterday by picking up a thread from `recent_episodes`. If a book starts today, say so and save its introduction for its segment.
3. Old Testament reading, 2,000 to 2,400 words. This is the heart of the episode.
   - Setting: date, king, events, where we are in the book's structure, and how this connects to the previous chapters.
   - Walk through the passage section by section, reading key verses aloud.
   - One or two key Hebrew words or literary features, explained simply.
   - The hardest question the passage raises, answered honestly with the voices.
   - Several commentary voices.
   - One concrete application, earned from the text.
4. Psalms and Wisdom reading, 650 to 800 words. Explain the poetry and structure. Wisdom literature is practical, so make it practical.
5. Gospel reading, 650 to 800 words. Cover the narrative setting, what is happening in John's (or Matthew's, and so on) argument, and the voices, including the fathers, who wrote heavily on the Gospels.
6. New Testament reading, 650 to 800 words. Follow the author's argument and its place in the letter, with the voices.
7. Closing, 300 to 400 words. Name one or two real connections between today's readings, only if they are real and never forced. Give one question to carry through the day, a one-sentence preview of the next plan day's readings (from `next_plan_day_preview`), and end with "This has been Old Paths. Grace and peace."

On the first day of a new book, give that book a compact introduction inside its segment (author, date, setting, structure, and big themes) and trim elsewhere to make room.

## Day building on day

- Treat this as a continuing series. Use `recent_episodes` and its `threads`, and read yesterday's transcript with `python scripts/podcast.py transcript last`.
- Refer back naturally ("Last time we watched Jehoiakim cut up the scroll..."). Do not repeat yesterday's illustrations, quotes, or applications.
- Track each book's arc so the listener feels the shape of the whole book over weeks.
- Close the threads you said you would close.

## Writing for the ear (text-to-speech rules)

The script is read by a synthetic voice exactly as written.

- Plain text paragraphs only. Do not use headings, bullets, numbered lists, markdown, parentheses, brackets, footnotes, or URLs.
- Write chapter and verse references as speech: "Jeremiah thirty-six, verse twenty-three." Use numerals only for years ("in 605 B.C.").
- Do not use em dashes or en dashes. Use commas, periods, or "and."
- Write "Lord," not "LORD."
- Spell out abbreviations: "the Westminster Confession," not "WCF," and "verses," not "vv."
- After a Hebrew or Greek word, give a simple meaning immediately. Spell the word so it can be pronounced, like "hesed," "shalom," or "parakletos."
- Vary sentence length, and use paragraph breaks for natural pauses.
- Read Scripture from the ESV in short portions. Do not read entire chapters aloud, because the listener has already read them.
