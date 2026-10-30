"""Hours Saved weekly pipeline.

    python -m hs.run weekly              # next topic(s) -> finished videos -> Drive or YouTube
    python -m hs.run make --topic 3      # one topic, files only (for testing)
    python -m hs.run make --topic 3 --plan out/3-x/plan.json   # re-render an edited plan
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import tomllib
from pathlib import Path

from . import render, thumbnail
from .script import load_plan, write_plan

ROOT = Path(__file__).resolve().parent.parent
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def load_config():
    with open(ROOT / "config.toml", "rb") as f:
        return tomllib.load(f)


def read_topics():
    with open(ROOT / "topics.csv", newline="") as f:
        return list(csv.DictReader(f))


def write_topics(rows):
    with open(ROOT / "topics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "title", "tools", "status"])
        w.writeheader()
        w.writerows(rows)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50]


def next_slot(spec: str, after: dt.datetime) -> dt.datetime:
    """Next 'Saturday 14:00' (UTC) strictly after `after`."""
    day, hm = spec.split()
    h, m = map(int, hm.split(":"))
    t = after.replace(hour=h, minute=m, second=0, microsecond=0)
    t += dt.timedelta(days=(DAYS.index(day.lower()) - t.weekday()) % 7)
    if t <= after:
        t += dt.timedelta(days=7)
    return t


def chapters(starts, total):
    """YouTube chapters: start at 0:00, at least 3, each at least 10 s long."""
    keep = []
    for t, sc in starts:
        name = sc.chapter or (sc.card.heading if not keep else "")
        if name and (not keep or t - keep[-1][0] >= 10):
            keep.append((t, name))
    while keep and total - keep[-1][0] < 10:
        keep.pop()
    if len(keep) < 3:
        return ""
    keep[0] = (0.0, keep[0][1])
    fmt = lambda s: f"{int(s // 60)}:{int(s % 60):02d}"
    return "\n".join(f"{fmt(t)} {h}" for t, h in keep)


def description(plan, chap, cfg, short=False):
    ch = cfg["channel"]
    parts = []
    links = {k.lower(): v for k, v in cfg.get("affiliate_links", {}).items() if v}
    if plan.thumbnail_tool.lower() in links:
        parts.append(f"Try {plan.thumbnail_tool}: {links[plan.thumbnail_tool.lower()]}")
    parts.append(plan.description_intro)
    if ch.get("tools_link"):
        parts.append("Tools I use (some are affiliate links, which means I may earn a small commission "
                     f"at no extra cost to you): {ch['tools_link']}")
    if chap and not short:
        parts.append("Chapters\n" + chap)
    if plan.prompts_used and not short:
        parts.append("Prompts from the video\n" + "\n".join(f"- {p}" for p in plan.prompts_used))
    if links or ch.get("tools_link"):
        parts.append(ch["disclosure"])
    parts.append("#Shorts #AItools #productivity" if short else "#AItools #productivity")
    return "\n\n".join(parts)


def make(topic, next_title, cfg, plan_path=None):
    out = ROOT / "out" / f"{topic['id']}-{slug(topic['title'])}"
    work = out / "work"
    out.mkdir(parents=True, exist_ok=True)
    channel = cfg["channel"]["name"]

    # A script written ahead of time (by the scheduled Claude task) wins over the API.
    saved = ROOT / "plans" / f"{topic['id']}.json"
    if not plan_path and saved.exists():
        plan_path = saved
    if plan_path:
        print(f"Using script: {plan_path}")
        plan = load_plan(plan_path)
    elif os.environ.get("ANTHROPIC_API_KEY"):
        print(f"Writing script: {topic['title']}")
        plan = write_plan(topic, next_title, cfg)
    else:
        raise SystemExit(f"No script for topic {topic['id']}: add plans/{topic['id']}.json "
                         "(see PLAN-WRITING.md) or set the ANTHROPIC_API_KEY secret.")
    (out / "plan.json").write_text(plan.model_dump_json(indent=2))

    print("Rendering long video")
    starts, total = render.build(plan.scenes, out / "video.mp4", work / "long", channel, render.LONG, cfg=cfg)
    thumbnail.make(plan.thumbnail_words, plan.thumbnail_tool, out / "thumbnail.jpg")
    items = [{"file": "video.mp4", "title": plan.title, "thumbnail": "thumbnail.jpg", "captions": "video.srt",
              "description": description(plan, chapters(starts, total), cfg), "tags": plan.tags, "short": 0}]

    for i, sh in enumerate(plan.shorts[: cfg["weekly"]["shorts_per_video"]], 1):
        print(f"Rendering Short {i}")
        render.build(sh.scenes, out / f"short-{i}.mp4", work / f"short{i}", channel, render.SHORT,
                     hook=sh.hook, burn_captions=True, cfg=cfg)
        items.append({"file": f"short-{i}.mp4", "title": sh.title, "thumbnail": None, "captions": None,
                      "description": description(plan, "", cfg, short=True), "tags": plan.tags, "short": i})

    shutil.rmtree(work, ignore_errors=True)
    return out, plan, items


def schedule(items, cfg, now):
    w = cfg["weekly"]
    long_at = next_slot(w["long_publish"], now + dt.timedelta(hours=36))
    after = long_at
    for it in items:
        if not it["short"]:
            it["publish_at"] = long_at
        else:
            spec = w["shorts_publish"][(it["short"] - 1) % len(w["shorts_publish"])]
            after = next_slot(spec, after)
            it["publish_at"] = after


def post_sheet(out, plan, items, cfg=None):
    """Plain-text sheet with everything needed to post from a phone, plus the review list."""
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    lines = [f"REVIEW BEFORE POSTING ({plan.title})", "Check these claims while you watch:"]
    lines += [f"  [ ] {c}" for c in plan.fact_check] or ["  (none flagged)"]
    for it in items:
        when = it["publish_at"].astimezone(ist).strftime("%A %d %b, %I:%M %p IST")
        auto = (cfg and os.environ.get("MAKE_WEBHOOK_URL") and cfg["youtube"]["mode"] == "drive"
                and (out / it["file"]).stat().st_size / 1e6 <= cfg["youtube"].get("make_max_mb", 5))
        how = "POSTED FOR YOU by Make (check it in YouTube Studio)" if auto else "POST THIS ONE YOURSELF"
        lines += ["", "=" * 60, f"FILE: {it['file']}  ->  {how}", f"SCHEDULE: {when}", "", "TITLE:", it["title"], "",
                  "DESCRIPTION:", it["description"], "", "TAGS:", ", ".join(it["tags"])]
        if it["thumbnail"]:
            lines += ["", f"THUMBNAIL: {it['thumbnail']}"]
    (out / "POST-THIS.txt").write_text("\n".join(lines) + "\n")


def deliver(out, plan, items, cfg):
    from . import google_apis
    yc = cfg["youtube"]
    if yc["mode"] == "youtube":
        for it in items:
            vid = google_apis.to_youtube(
                out / it["file"], it["title"], it["description"], it["tags"], yc["category_id"],
                it["publish_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                thumbnail=out / it["thumbnail"] if it["thumbnail"] else None,
                captions=out / it["captions"] if it["captions"] else None)
            print(f"Uploaded {it['file']} -> https://studio.youtube.com/video/{vid}/edit")
    else:
        files = [out / "POST-THIS.txt", out / "thumbnail.jpg"] + [out / it["file"] for it in items]
        link, ids = google_apis.to_drive(yc["drive_folder"], out.name, files)
        print(f"Saved to Drive: {link}")
        if os.environ.get("MAKE_WEBHOOK_URL"):
            to_make(out, items, ids, yc)


def to_make(out, items, ids, yc):
    """Hand each video to the Make.com scenario, which posts it to YouTube on schedule."""
    import urllib.request
    for it in items:
        mb = (out / it["file"]).stat().st_size / 1e6
        if mb > yc.get("make_max_mb", 5):
            print(f"Post {it['file']} yourself: {mb:.0f} MB is over the Make limit of {yc.get('make_max_mb', 5)} MB")
            continue
        body = {"file_id": ids[it["file"]], "file_name": it["file"], "title": it["title"],
                "description": it["description"], "tags": ",".join(it["tags"]),
                "publish_at": it["publish_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "thumbnail_id": ids.get(it["thumbnail"], "") if it["thumbnail"] else "",
                "category_id": yc["category_id"]}
        req = urllib.request.Request(os.environ["MAKE_WEBHOOK_URL"], json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        urllib.request.urlopen(req).read()
        print(f"Sent {it['file']} to Make for posting")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["weekly", "make"])
    ap.add_argument("--topic", help="topic id from topics.csv")
    ap.add_argument("--plan", help="use an existing plan.json instead of writing a new script")
    ap.add_argument("--upload", action="store_true", help="with make: also deliver to Drive/YouTube")
    args = ap.parse_args()
    cfg = load_config()
    rows = read_topics()
    now = dt.datetime.now(dt.timezone.utc)

    if args.command == "make":
        picks = [r for r in rows if r["id"] == args.topic]
    else:
        picks = [r for r in rows if r["status"] == "todo"][: cfg["weekly"]["long_videos"]]
    if not picks:
        raise SystemExit("No topics left: add more rows to topics.csv with status 'todo'.")

    for topic in picks:
        later = [r for r in rows if r["status"] == "todo" and r["id"] != topic["id"]]
        out, plan, items = make(topic, later[0]["title"] if later else "", cfg, args.plan)
        schedule(items, cfg, now)
        post_sheet(out, plan, items, cfg)
        if args.command == "weekly" or args.upload:
            deliver(out, plan, items, cfg)
            topic["status"] = "done"
            write_topics(rows)
        print(f"Finished: {out}")


if __name__ == "__main__":
    main()
