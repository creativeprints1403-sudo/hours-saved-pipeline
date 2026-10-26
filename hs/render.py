"""Assemble cards and narration into an MP4 with ffmpeg, plus caption files."""
import re
import subprocess
from pathlib import Path

import numpy as np

from . import cards, voice

LONG = (1920, 1080)
SHORT = (1080, 1920)
MUSIC = Path(__file__).resolve().parent.parent / "assets" / "music.mp3"


def _ts(t: float, sep=","):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int((s % 1) * 1000):03d}"


def _chunks(text: str, start: float, dur: float, max_words: int):
    """Split narration into caption chunks timed by their share of the characters."""
    words = text.split()
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or re.search(r"[.!?,:;]$", w) and len(cur) >= max_words // 2:
            groups.append(" ".join(cur))
            cur = []
    if cur:
        groups.append(" ".join(cur))
    total = sum(len(g) for g in groups) or 1
    speech = max(dur - 0.45, 0.5)  # voice.speak adds a 0.45 s pause
    t = start
    for g in groups:
        d = speech * len(g) / total
        yield t, t + d, g
        t += d


def build(scenes, out_mp4: Path, work: Path, channel: str, size=LONG, hook: str = "",
          burn_captions: bool = False, cfg: dict = None):
    """scenes: list of Scene. Returns list of (start_seconds, scene) for chapters."""
    work.mkdir(parents=True, exist_ok=True)
    concat, audio_parts, captions, starts = [], [], [], []
    t = 0.0
    n_img = 0

    def add_image(img, dur):
        nonlocal n_img
        p = work / f"f{n_img:04d}.png"
        img.save(p)
        concat.append((p, dur))
        n_img += 1

    if hook:
        a = voice.speak(hook, cfg)
        audio_parts.append(a)
        dur = len(a) / voice.RATE
        add_image(cards.draw_hook(hook, size, channel), dur)
        captions += list(_chunks(hook, t, dur, 4 if burn_captions else 10))
        t += dur

    step = 0
    for sc in scenes:
        a = voice.speak(sc.voiceover, cfg)
        audio_parts.append(a)
        dur = len(a) / voice.RATE
        starts.append((t, sc))
        if sc.card.kind == "steps":
            step += 1
        label = f"STEP {step}" if sc.card.kind == "steps" else ""
        n = len(sc.card.lines)
        if sc.card.kind == "title" or n == 0:
            add_image(cards.draw_card(sc.card, n, size, channel, label), dur)
        else:
            lead = min(0.8, dur * 0.12)
            add_image(cards.draw_card(sc.card, 0, size, channel, label), lead)
            for k in range(1, n + 1):
                add_image(cards.draw_card(sc.card, k, size, channel, label), (dur - lead) / n)
        captions += list(_chunks(sc.voiceover, t, dur, 4 if burn_captions else 10))
        t += dur

    wav = work / "voice.wav"
    voice.save(np.concatenate(audio_parts), wav)

    lst = work / "list.txt"
    with open(lst, "w") as f:
        for p, d in concat:
            f.write(f"file '{p}'\nduration {d:.3f}\n")
        f.write(f"file '{concat[-1][0]}'\n")

    srt = out_mp4.with_suffix(".srt")
    with open(srt, "w") as f:
        for i, (a, b, text) in enumerate(captions, 1):
            f.write(f"{i}\n{_ts(a)} --> {_ts(b)}\n{text}\n\n")

    vf = "fps=30,format=yuv420p"
    if burn_captions:
        ass = work / "captions.ass"
        _write_ass(captions, ass, size)
        vf += f",ass=filename={ass}:fontsdir={cards.FONTS}"

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav)]
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11"  # YouTube plays everything at about -14 LUFS
    if MUSIC.exists():
        # Optional royalty-free music bed, ducked under the voice.
        cmd += ["-stream_loop", "-1", "-i", str(MUSIC), "-filter_complex",
                f"[0:v]{vf}[v];[1:a]asplit[vo][key];[2:a]volume=0.25[m];"
                f"[m][key]sidechaincompress=threshold=0.02:ratio=8:release=400[duck];"
                f"[vo][duck]amix=inputs=2:duration=first:normalize=0,{loud}[a]",
                "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-filter_complex", f"[0:v]{vf}[v];[1:a]{loud}[a]", "-map", "[v]", "-map", "[a]"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out_mp4)]
    subprocess.run(cmd, check=True)
    return starts, t


def _write_ass(captions, path: Path, size):
    w, h = size
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat ExtraBold,78,&H0011A3FC,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,6,0,2,60,60,{int(h * 0.12)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(path, "w") as f:
        f.write(head)
        for a, b, text in captions:
            text = text.upper().replace("\n", " ").replace("{", "(").replace("}", ")")
            f.write(f"Dialogue: 0,{_ts(a, '.')[1:-1]},{_ts(b, '.')[1:-1]},Default,,0,0,0,,{text}\n")
