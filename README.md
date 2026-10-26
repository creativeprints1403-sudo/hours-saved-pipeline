# Hours Saved video pipeline

Every Wednesday this repository makes the week's videos on its own:

1. takes the next topic from `topics.csv`
2. uses the script a scheduled Claude task saved in `plans/` (see PLAN-WRITING.md), or writes one with the Claude API if `ANTHROPIC_API_KEY` is set
3. records the narration with a free AI voice (Kokoro)
4. draws branded cards and renders a 1080p tutorial and three vertical Shorts with captions
5. makes the thumbnail
6. sends everything to Google Drive (`mode = "drive"`) or uploads private, scheduled drafts to YouTube (`mode = "youtube"`)
7. marks the topic as done

You review the videos once a week and approve them. Nothing goes public without you.

## Change things without code

- **Topics:** edit `topics.csv` on GitHub. Add rows with status `todo`. Change a row back to `todo` to remake it.
- **Voice, schedule, links:** edit `config.toml`.
- **Make a video now:** Actions tab, "Weekly videos", "Run workflow". Type a topic number or leave it empty for the next one.
- **Fix a script and re-render:** download `plan.json` from the run's files, edit the text, then run locally with
  `python -m hs.run make --topic 3 --plan plan.json`.

## Secrets (Settings, Secrets and variables, Actions)

| Name | Where it comes from |
|---|---|
| `ANTHROPIC_API_KEY` | optional: only if you don't use the scheduled Claude task for scripts |
| `GOOGLE_CLIENT_ID` | Google Cloud console, Credentials, OAuth client |
| `GOOGLE_CLIENT_SECRET` | same place |
| `GOOGLE_REFRESH_TOKEN` | Google OAuth Playground (see the setup guide) |
| `ELEVENLABS_API_KEY` | optional, only if `engine = "elevenlabs"` |

## Run it on your own computer

```
pip install -r requirements.txt          # also needs ffmpeg
mkdir -p models && curl -L https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-en-v0_19.tar.bz2 | tar xj -C models
mv models/kokoro-en-v0_19 models/kokoro
python -m hs.run make --topic 1 --plan examples/plan-topic-1.json   # no API key needed
```

Files land in `out/`. `POST-THIS.txt` has the title, description, tags, schedule and the
review checklist for each video.

## Costs

GitHub Actions is free for this (about 30 of the 2,000 free minutes per run). Claude costs
about $0.20 per tutorial. The voice, Drive and YouTube APIs are free.
