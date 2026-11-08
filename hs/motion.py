"""Animated frames for the videos: a moving background, a chat window that types, a spreadsheet
formula bar, lines that slide in, and a progress bar. Pure Pillow, one frame at a time.

Every draw function takes the scene time t (seconds) and returns a finished RGB frame.
"""
import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .cards import GREY, NAVY, NAVY_LIGHT, WHITE, YELLOW, fit, font, wrap

FPS = 30
INK = (32, 36, 44)
APP = (24, 30, 46)          # chat app window
APP_BAR = (36, 44, 64)
SHEET_GRID = (214, 219, 228)
SHEET_HEAD = (238, 241, 246)
GREEN = (33, 140, 80)
RED = (220, 70, 70)


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def back_out(x):
    """Overshoots a little, for 'pop' animations."""
    x = clamp(x)
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def mix(c1, c2, a):
    """Colour c1 faded towards c2 by (1-a): a=1 gives c1."""
    return tuple(int(b + (f - b) * a) for f, b in zip(c1, c2))


# ---------- background ----------
@lru_cache(maxsize=4)
def _bg(size):
    w, h = size
    base = Image.new("RGB", size, NAVY)
    d = ImageDraw.Draw(base)
    for y in range(h):  # slight vertical gradient
        k = y / h
        d.line([(0, y), (w, y)], fill=(int(20 - 8 * k), int(33 - 11 * k), int(61 - 17 * k)))
    s = w / 1920 if w > h else w / 1080
    step = int(48 * s)
    for x in range(step // 2, w, step):  # faint dot grid
        for y in range(step // 2, h, step):
            d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(40, 56, 92))
    # glow canvas twice the frame size; a moving crop of it drifts the light around
    g = Image.new("RGB", (w * 2, h * 2), (0, 0, 0))
    gd = ImageDraw.Draw(g)
    r = int(min(w, h) * 0.45)
    gd.ellipse([w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r], fill=(70, 48, 8))
    gd.ellipse([w + w // 2 - r, h + h // 2 - r, w + w // 2 + r, h + h // 2 + r], fill=(10, 40, 80))
    g = g.filter(ImageFilter.GaussianBlur(r // 2))
    return base, g


def background(size, gt):
    """gt: global time, so the light keeps drifting across scene cuts."""
    w, h = size
    base, g = _bg(size)
    ox = int(w / 2 + math.sin(gt * 0.13) * w * 0.35)
    oy = int(h / 2 + math.cos(gt * 0.09) * h * 0.35)
    return ImageChops.add(base, g.crop((ox, oy, ox + w, oy + h)))


def chrome(img, size, channel, progress=None):
    """Brand strip, channel name and (long videos) a progress bar."""
    w, h = size
    d = ImageDraw.Draw(img)
    s = w / 1920 if w > h else w / 1080 * 1.3
    d.rectangle([0, 0, w, int(8 * s)], fill=YELLOW)
    d.text((int(60 * s), h - int(70 * s)), channel.upper(), font=font(int(26 * s), "bold"), fill=GREY)
    if progress is not None:
        y = h - int(10 * s)
        d.rectangle([0, y, w, h], fill=(30, 44, 76))
        d.rectangle([0, y, int(w * clamp(progress)), h], fill=YELLOW)
    return d, s


# ---------- scene timing ----------
def slots(n, dur):
    """When each of n lines appears: same rhythm as the narration."""
    lead = min(0.8, dur * 0.12)
    each = (dur - lead) / max(n, 1)
    return [(lead + i * each, each) for i in range(n)]


# ---------- pieces ----------
def _pill(d, x, y, text, s, a, fill):
    lf = font(int(30 * s), "bold")
    tw = d.textlength(text, font=lf)
    d.rounded_rectangle([x, y, x + tw + int(40 * s), y + int(56 * s)], radius=int(28 * s),
                        fill=mix(fill, NAVY, a))
    d.text((x + int(20 * s), y + int(11 * s)), text, font=lf, fill=mix(NAVY, fill, a) if a < 1 else NAVY)
    return int(90 * s)


def _heading(d, text, x, y, width, s, t):
    a = ease_out(t / 0.35)
    off = int((1 - a) * 50 * s)
    hf, hl = fit(d, text, "bold", width, 2, int(84 * s), int(52 * s))
    for line in hl:
        d.text((x - off, y), line, font=hf, fill=mix(WHITE, NAVY, a))
        y += int(hf.size * 1.15)
    return y + int(40 * s)


def _typed(text, start, t, cps=28.0, max_time=None):
    """Characters of text visible at time t when typing starts at `start`."""
    if t < start:
        return ""
    speed = cps
    if max_time:
        speed = max(cps, len(text) / max_time)
    return text[: int((t - start) * speed) + 1]


# ---------- card kinds ----------
def _title(d, card, size, s, t, dur):
    w, h = size
    vertical = h > w
    margin = int((90 if not vertical else 70) * s)
    inner = w - 2 * margin
    hf, hl = fit(d, card.heading.upper(), "bold", inner, 3, int(120 * s), int(60 * s))
    y = int(h * (0.30 if not vertical else 0.32))
    k = 0
    for line in hl:
        x = margin
        for word in line.split():
            a = back_out((t - 0.1 - k * 0.12) / 0.35)
            dy = int((1 - clamp(a)) * 40 * s)
            col = YELLOW if k == 0 else WHITE
            d.text((x, y + dy), word, font=hf, fill=mix(col, NAVY, clamp(a)))
            x += d.textlength(word + " ", font=hf)
            k += 1
        y += int(hf.size * 1.12)
    bar = ease_out((t - 0.2 - k * 0.12) / 0.5)
    d.rectangle([margin, y + int(20 * s), margin + int(220 * s * bar), y + int(34 * s)], fill=YELLOW)
    y += int(80 * s)
    bf = font(int(44 * s), "body")
    for i, text in enumerate(card.lines):
        a = ease_out((t - 0.5 - k * 0.12 - i * 0.3) / 0.4)
        for line in wrap(d, text, bf, inner):
            d.text((margin, y + int((1 - a) * 20 * s)), line, font=bf, fill=mix(GREY, NAVY, a))
            y += int(bf.size * 1.3)


def _list(d, card, size, s, t, dur, label):
    w, h = size
    vertical = h > w
    margin = int((90 if not vertical else 70) * s)
    inner = w - 2 * margin
    accent = {"warning": RED, "tip": YELLOW}.get(card.kind, YELLOW)
    body = font(int((56 if not vertical else 58) * s), "body")
    # measure for vertical centring
    height = (int(90 * s) if label else 0) + int(84 * s * 1.15) * 2 + int(40 * s)
    for text in card.lines:
        height += len(wrap(d, text, body, inner - int(90 * s))) * int(body.size * 1.3) + int(28 * s)
    y = max(int((110 if not vertical else 300) * s), (h - height) // 2 - int(30 * s))
    if label:
        y += _pill(d, margin, y, label, s, ease_out(t / 0.3), accent)
    y = _heading(d, card.heading, margin, y, inner, s, t)
    for i, ((st, _), text) in enumerate(zip(slots(len(card.lines), dur), card.lines)):
        a = ease_out((t - st) / 0.35)
        if a <= 0:
            break
        off = int((1 - a) * 60 * s)
        p = back_out((t - st) / 0.35)
        r = int(27 * s * clamp(p, 0, 1.3))
        cx, cy = margin + int(27 * s), y + int(31 * s)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=mix(accent, NAVY, a))
        bullet = f"{i + 1}" if card.kind in ("steps", "recap") else ("!" if card.kind == "warning" else "•")
        bfnt = font(int(30 * s), "bold")
        d.text((cx - d.textlength(bullet, font=bfnt) / 2, y + int(13 * s)), bullet, font=bfnt,
               fill=mix(NAVY, accent, a))
        for line in wrap(d, text, body, inner - int(90 * s)):
            d.text((margin + int(85 * s) + off, y), line, font=body, fill=mix(WHITE, NAVY, a))
            y += int(body.size * 1.3)
        y += int(28 * s)


def _chat(d, card, size, s, t, dur):
    """A chat app window: your message types out, then the AI 'thinks' and answers."""
    w, h = size
    vertical = h > w
    margin = int((160 if not vertical else 60) * s)
    inner = w - 2 * margin
    y = int((90 if not vertical else 260) * s)
    y = _heading(d, card.heading, margin, y, inner, s, t)
    # window
    a = ease_out(t / 0.4)
    top = y + int((1 - a) * 40 * s)
    bottom = h - int((120 if not vertical else 330) * s)
    d.rounded_rectangle([margin, top, w - margin, bottom], radius=int(24 * s), fill=mix(APP, NAVY, a),
                        outline=mix((60, 72, 100), NAVY, a), width=max(1, int(2 * s)))
    d.rounded_rectangle([margin, top, w - margin, top + int(64 * s)], radius=int(24 * s),
                        fill=mix(APP_BAR, NAVY, a))
    d.rectangle([margin, top + int(40 * s), w - margin, top + int(64 * s)], fill=mix(APP_BAR, NAVY, a))
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (98, 197, 84)]):
        cx = margin + int((34 + i * 30) * s)
        d.ellipse([cx - int(8 * s), top + int(24 * s), cx + int(8 * s), top + int(40 * s)], fill=mix(c, NAVY, a))
    tf = font(int(24 * s), "bold")
    d.text((w / 2 - d.textlength("AI CHAT", font=tf) / 2, top + int(19 * s)), "AI CHAT", font=tf,
           fill=mix(GREY, NAVY, a))
    # input box at the bottom of the window
    ib = bottom - int(90 * s)
    d.rounded_rectangle([margin + int(30 * s), ib, w - margin - int(30 * s), bottom - int(24 * s)],
                        radius=int(30 * s), fill=mix((44, 54, 78), NAVY, a))

    y = top + int(100 * s)
    bsize = int((40 if not vertical else 50) * s)
    pad = int(28 * s)
    for (st, ln), text in zip(slots(len(card.lines), dur), card.lines):
        if t < st:
            break
        who, _, msg = text.partition(":")
        is_ai = who.strip().lower() in ("ai", "chatgpt", "claude", "gemini", "copilot")
        msg = msg.strip() or text
        maxw = inner - int(200 * s)
        bf, lines = fit(d, msg, "body", maxw, 6, bsize, int(24 * s))
        if is_ai:
            think = min(0.5, ln * 0.25)
            if t < st + think:  # typing dots
                x0 = margin + int(40 * s)
                d.rounded_rectangle([x0, y, x0 + int(130 * s), y + int(64 * s)], radius=int(30 * s),
                                    fill=NAVY_LIGHT)
                for k in range(3):
                    bounce = math.sin((t - st) * 10 - k * 0.8) * 6 * s
                    cx = x0 + int((36 + k * 30) * s)
                    d.ellipse([cx - int(8 * s), y + int(24 * s) - bounce, cx + int(8 * s),
                               y + int(40 * s) - bounce], fill=GREY)
                break
            words = msg.split()
            shown = int(len(words) * clamp((t - st - think) / max(0.3, min(1.2, ln * 0.5)))) + 1
            visible = " ".join(words[:shown])
        else:
            visible = _typed(msg, st, t, max_time=max(0.4, min(1.6, ln * 0.55)))
        _, vlines = fit(d, visible, "body", maxw, 6, bf.size, bf.size)
        full_w = max(d.textlength(l, font=bf) for l in lines)
        bh = len(lines) * int(bf.size * 1.3) + 2 * pad - int(bf.size * 0.3)
        if is_ai:
            x0 = margin + int(40 * s)
            x1 = x0 + full_w + 2 * pad
            fill, ink = NAVY_LIGHT, WHITE
        else:
            x1 = w - margin - int(40 * s)
            x0 = x1 - full_w - 2 * pad
            fill, ink = WHITE, INK
        d.rounded_rectangle([x0, y, x1, y + bh], radius=int(26 * s), fill=fill)
        d.text((x0 + pad, y - int(30 * s)), "AI" if is_ai else "YOU", font=font(int(22 * s), "bold"),
               fill=YELLOW)
        ty = y + pad
        for line in vlines:
            d.text((x0 + pad, ty), line, font=bf, fill=ink)
            ty += int(bf.size * 1.3)
        typing = not is_ai and len(visible) < len(msg)
        if typing and int(t * 3) % 2 == 0:
            cx = x0 + pad + d.textlength(vlines[-1], font=bf) + int(4 * s)
            d.rectangle([cx, ty - int(bf.size * 1.3), cx + int(4 * s), ty - int(bf.size * 0.25)], fill=ink)
        y += bh + int(56 * s)


def _code(d, card, size, s, t, dur):
    """Spreadsheet look: a formula bar that types each formula, over a small grid."""
    w, h = size
    vertical = h > w
    margin = int((160 if not vertical else 60) * s)
    inner = w - 2 * margin
    y = int((100 if not vertical else 280) * s)
    y = _heading(d, card.heading, margin, y, inner, s, t)
    a = ease_out(t / 0.4)
    sheet_top = y + int((1 - a) * 40 * s)
    formulas = [l for l in card.lines if l.strip().startswith("=")] or card.lines[:1]
    notes = [l for l in card.lines if l not in formulas]
    times = slots(len(card.lines), dur)
    when = {l: times[i][0] for i, l in enumerate(card.lines)}
    # current formula in the bar = the latest one that has started
    cur = formulas[0]
    for f in formulas:
        if t >= when[f]:
            cur = f
    st = when[cur]
    typed = _typed(cur, st, t, cps=30, max_time=1.4)
    done = len(typed) >= len(cur)
    # sheet window
    white = mix(WHITE, NAVY, a)
    rows, cols = (5, 5) if not vertical else (6, 4)
    bar_h = int(76 * s)
    cell_h = int(56 * s)
    mf, ml = fit(d, cur, "mono", inner - int(140 * s), 3, int(40 * s), int(22 * s))
    bar_h = max(bar_h, len(ml) * int(mf.size * 1.3) + int(30 * s))
    bottom = sheet_top + bar_h + cell_h * (rows + 1) + int(20 * s)
    d.rounded_rectangle([margin, sheet_top, w - margin, bottom], radius=int(18 * s), fill=white)
    # formula bar
    d.rectangle([margin + int(14 * s), sheet_top + int(14 * s), w - margin - int(14 * s),
                 sheet_top + bar_h], outline=mix(SHEET_GRID, NAVY, a), width=max(1, int(2 * s)))
    fxf = font(int(30 * s), "bold")
    d.text((margin + int(30 * s), sheet_top + int(26 * s)), "fx", font=fxf, fill=mix((120, 128, 140), NAVY, a))
    _, tl = fit(d, typed, "mono", inner - int(140 * s), 3, mf.size, mf.size)
    ty = sheet_top + int(26 * s)
    for line in tl:
        d.text((margin + int(100 * s), ty), line, font=mf, fill=mix(GREEN, NAVY, a))
        ty += int(mf.size * 1.3)
    if not done and int(t * 3) % 2 == 0 and tl:
        cx = margin + int(100 * s) + d.textlength(tl[-1], font=mf) + 3
        d.rectangle([cx, ty - int(mf.size * 1.25), cx + int(3 * s), ty - int(mf.size * 0.2)], fill=INK)
    # grid
    gx0 = margin + int(14 * s)
    gy0 = sheet_top + bar_h + int(14 * s)
    gx1 = w - margin - int(14 * s)
    head_w = int(56 * s)
    cw = (gx1 - gx0 - head_w) / cols
    gl = mix(SHEET_GRID, NAVY, a)
    d.rectangle([gx0, gy0, gx1, gy0 + cell_h], fill=mix(SHEET_HEAD, NAVY, a))
    d.rectangle([gx0, gy0, gx0 + head_w, gy0 + cell_h * (rows + 1)], fill=mix(SHEET_HEAD, NAVY, a))
    hf = font(int(22 * s), "bold")
    for c in range(cols):
        x = gx0 + head_w + c * cw
        d.line([(x, gy0), (x, gy0 + cell_h * (rows + 1))], fill=gl, width=1)
        letter = "ABCDEFG"[c]
        d.text((x + cw / 2 - d.textlength(letter, font=hf) / 2, gy0 + int(16 * s)), letter, font=hf,
               fill=mix((110, 118, 130), NAVY, a))
    for r in range(rows + 1):
        yy = gy0 + r * cell_h
        d.line([(gx0, yy), (gx1, yy)], fill=gl, width=1)
        if r:
            d.text((gx0 + int(18 * s), yy + int(16 * s)), str(r + 1), font=hf, fill=mix((110, 118, 130), NAVY, a))
            for c in range(cols - 1):  # grey bars that read as data
                bw = cw * (0.35 + 0.4 * ((r * 7 + c * 3) % 5) / 4)
                bx = gx0 + head_w + c * cw + int(12 * s)
                d.rounded_rectangle([bx, yy + int(20 * s), bx + bw, yy + cell_h - int(20 * s)],
                                    radius=int(6 * s), fill=mix((226, 230, 237), WHITE, a))
    # active cell, turns into a result tick when the formula is finished
    ax = gx0 + head_w + (cols - 1) * cw
    ay = gy0 + cell_h * 2
    d.rectangle([ax, ay, ax + cw, ay + cell_h], outline=mix(GREEN, NAVY, a), width=max(2, int(4 * s)))
    if done:
        p = back_out((t - st - len(cur) / max(30, len(cur) / 1.4)) / 0.3)
        r = int(20 * s * clamp(p, 0, 1.3))
        cx, cy = ax + cw - int(30 * s), ay + cell_h // 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN)
        if p > 0.6:
            d.line([(cx - 9 * s, cy), (cx - 2 * s, cy + 7 * s), (cx + 10 * s, cy - 8 * s)], fill=WHITE,
                   width=max(2, int(4 * s)))
    # notes under the sheet
    y = bottom + int(40 * s)
    nf = font(int((40 if not vertical else 50) * s), "body")
    for n in notes:
        na = ease_out((t - when[n]) / 0.35)
        if na <= 0:
            continue
        for line in wrap(d, n, nf, inner):
            d.text((margin, y + int((1 - na) * 20 * s)), line, font=nf, fill=mix(GREY, NAVY, na))
            y += int(nf.size * 1.3)


def hook(text, size, channel, t, gt):
    """First frame of a Short: big words punch in one by one."""
    w, h = size
    img = background(size, gt)
    d, s = chrome(img, size, channel)
    margin = int(70 * s)
    hf, hl = fit(d, text.upper(), "bold", w - 2 * margin, 6, int(120 * s), int(60 * s))
    y = int(h * 0.30)
    k = 0
    for i, line in enumerate(hl):
        x = margin
        for word in line.split():
            a = back_out((t - k * 0.09) / 0.3)
            dy = int((1 - clamp(a)) * 50 * s)
            d.text((x, y + dy), word, font=hf, fill=mix(YELLOW if i == 0 else WHITE, NAVY, clamp(a)))
            x += d.textlength(word + " ", font=hf)
            k += 1
        y += int(hf.size * 1.15)
    return img


def scene(card, size, channel, label, t, dur, gt, progress=None):
    img = background(size, gt)
    d, s = chrome(img, size, channel, progress)
    if card.kind == "title":
        _title(d, card, size, s, t, dur)
    elif card.kind == "chat" and card.lines:
        _chat(d, card, size, s, t, dur)
    elif card.kind == "code" and card.lines:
        _code(d, card, size, s, t, dur)
    else:
        _list(d, card, size, s, t, dur, {"warning": "WATCH OUT", "tip": "TIP", "recap": "RECAP"}.get(card.kind, label))
    return img


def events(card, dur):
    """(time, kind) sound cues for one scene: 'type' spans and 'pop's."""
    out = []
    for (st, ln), text in zip(slots(len(card.lines), dur), card.lines):
        who, _, msg = text.partition(":")
        if card.kind == "chat" and who.strip().lower() in ("you", "me"):
            out.append((st, "type", max(0.4, min(1.6, ln * 0.55))))
        elif card.kind == "code" and text.strip().startswith("="):
            out.append((st, "type", min(1.4, len(text) / 30)))
        elif card.kind != "title":
            out.append((st, "pop", 0))
    return out
