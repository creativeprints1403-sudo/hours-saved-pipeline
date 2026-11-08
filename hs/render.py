"""Assemble cards and narration into an MP4 with ffmpeg, plus caption files."""
import re
import subprocess
from pathlib import Path

import numpy as np

from . import cards, motion, sound, voice

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
    """Render an animated video from scenes. Returns (chapter starts, total seconds)."""
    work.mkdir(parents=True, exist_ok=True)
    vertical = size[1] > size[0]

    # 1. Voice first, so every scene's length is known before drawing.
    parts = []  # (kind, payload, start, dur)
    audio, captions, starts, cues = [], [], [], []
    t = 0.0
    if hook:
        a = voice.speak(hook, cfg)
        dur = len(a) / voice.RATE
        audio.append(a)
        parts.append(("hook", hook, t, dur, ""))
        captions += list(_chunks(hook, t, dur, 4 if burn_captions else 10))
        t += dur
    step = 0
    for sc in scenes:
        a = voice.speak(sc.voiceover, cfg)
        dur = len(a) / voice.RATE
        audio.append(a)
        starts.append((t, sc))
        if sc.card.kind == "steps":
            step += 1
        label = f"STEP {step}" if sc.card.kind == "steps" else ""
        parts.append(("scene", sc.card, t, dur, label))
        cues.append((t, "whoosh", 0))
        cues += [(t + ct, kind, ln) for ct, kind, ln in motion.events(sc.card, dur)]
        captions += list(_chunks(sc.voiceover, t, dur, 4 if burn_captions else 10))
        t += dur
    total = t

    vo = np.concatenate(audio)
    fx = sound.effects(len(vo) / voice.RATE, cues)
    wav = work / "voice.wav"
    voice.save(np.clip(vo + fx[: len(vo)] * 0.6, -1, 1), wav)
    music = work / "music.wav"
    if MUSIC.exists():
        music = MUSIC
    else:
        voice.save(sound.music(total + 1), music)

    srt = out_mp4.with_suffix(".srt")
    with open(srt, "w") as f:
        for i, (a, b, text) in enumerate(captions, 1):
            f.write(f"{i}\n{_ts(a)} --> {_ts(b)}\n{text}\n\n")

    # 2. Frames, streamed straight into ffmpeg.
    vf = "format=yuv420p"
    if burn_captions:
        ass = work / "captions.ass"
        _write_ass(captions, ass, size)
        vf += f",ass=filename={ass}:fontsdir={cards.FONTS}"
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11"  # YouTube plays everything at about -14 LUFS
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}", "-r", str(motion.FPS), "-i", "-",
           "-i", str(wav), "-stream_loop", "-1", "-i", str(music), "-filter_complex",
           f"[0:v]{vf}[v];[1:a]asplit[vo][key];[2:a]aresample=24000,volume=0.22[m];"
           f"[m][key]sidechaincompress=threshold=0.03:ratio=6:release=500[duck];"
           f"[vo][duck]amix=inputs=2:duration=first:normalize=0,{loud}[a]",
           "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(total * motion.FPS))
    k = 0
    for kind, payload, st, dur, label in parts:
        end = int(round((st + dur) * motion.FPS))
        while k < end:
            gt = k / motion.FPS
            lt = gt - st
            if kind == "hook":
                img = motion.hook(payload, size, channel, lt, gt)
            else:
                img = motion.scene(payload, size, channel, label, lt, dur, gt,
                                   None if vertical else gt / total)
            proc.stdin.write(img.tobytes())
            k += 1
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return starts, total


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
