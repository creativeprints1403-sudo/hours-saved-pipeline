# Writing next week's script (for the scheduled Claude task)

Every Wednesday before the video robot runs, a scheduled Claude task writes the script for
the next topic, so the pipeline needs no Claude API key. Steps:

1. In `topics.csv`, find the first row with status `todo`. That's this week's topic. The
   next `todo` row after it is next week's topic.
2. If `plans/<id>.json` already exists for this week's topic, stop: nothing to do.
3. Read `hs/script.py`. Follow the brief in `PROMPT`, filling it in from the topic row and
   `config.toml` (channel name, `target_words`, `shorts_per_video`), and write the result as
   JSON matching the `VideoPlan` model to `plans/<id>.json`. `examples/plan-topic-1.json`
   shows the shape (the real script should be about `target_words` words of narration).
4. Check it loads:
   `pip install -q pydantic anthropic && python3 -c "from hs.script import load_plan; load_plan('plans/<id>.json')"`
5. Commit only `plans/<id>.json` with the message `Script for topic <id>` and push it to `main`.

Accuracy rules matter most: only describe features you are confident exist today, keep
examples generic enough to stay true across versions, and put anything a reviewer should
check in `fact_check`. Helvia reads that list before posting.
