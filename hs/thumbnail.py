"""Thumbnail from the channel template.

With a before/after example: a crossed-out messy "before", a clean "after" with a green
tick, and 2-4 big words on the right (the style of the hand-made video 1 thumbnail).
Without one: tool badge, yellow arrow and big words.
"""
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .cards import NAVY, NAVY_LIGHT, WHITE, YELLOW, fit, font, wrap

W, H = 1280, 720
RED = (220, 60, 60)
GREEN = (46, 160, 90)
INK = (40, 44, 52)


def _glow(img):
    """Soft warm glow behind the big words so they pop off the navy."""
    g = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(g).ellipse([720, 140, 1220, 600], fill=(90, 60, 10))
    return ImageChops.add(img, g.filter(ImageFilter.GaussianBlur(110)))


def _words(d, words, x, width):
    wf, wl = fit(d, words.upper(), "bold", width, 3, 170, 70)
    step = int(wf.size * 1.02)
    y = 360 - len(wl) * step // 2
    for i, line in enumerate(wl):
        d.text((x, y), line, font=wf, fill=YELLOW if i == 0 else WHITE,
               stroke_width=6, stroke_fill=(10, 14, 30))
        y += step


def _mono_lines(d, text, width, max_lines):
    """Monospace text split anywhere (formulas have no spaces), cut with '...' if too long."""
    for size in range(52, 29, -4):
        f = font(size, "mono")
        per = max(1, int(width // d.textlength("M", font=f)))
        words = wrap(d, text, f, width)
        if len(words) <= max_lines and all(d.textlength(l, font=f) <= width for l in words):
            return f, words
        if len(text) <= per * max_lines:
            break
    lines = [text[i:i + per] for i in range(0, len(text), per)]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:-3] + "..."
    return f, lines


def _before_after(img, before, after):
    # "before": light card, tilted, with a red cross
    card = Image.new("RGBA", (620, 250), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([0, 0, 619, 249], radius=24, fill=(244, 245, 247))
    bf, bl = _mono_lines(cd, before, 560, 3)
    y = 125 - len(bl) * int(bf.size * 1.2) // 2
    for line in bl:
        cd.text((30, y), line, font=bf, fill=INK)
        y += int(bf.size * 1.2)
    cd.line([(20, 30), (600, 220)], fill=RED, width=16)
    cd.line([(20, 220), (600, 30)], fill=RED, width=16)
    card = card.rotate(5, expand=True, resample=Image.BICUBIC)
    img.paste(card, (30, 170), card)
    # "after": white box, green border and tick
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 520, 640, 640], radius=22, fill=WHITE, outline=GREEN, width=8)
    af, _ = fit(d, after, "mono", 500, 1, 40, 22)
    d.text((90, 580 - af.size // 2 - 4), after, font=af, fill=(30, 110, 60))
    d.ellipse([588, 488, 668, 568], fill=GREEN)
    d.line([(608, 528), (622, 544), (650, 510)], fill=WHITE, width=10)


def _tool_badge(d, tool):
    d.rounded_rectangle([60, 50, 200, 190], radius=28, fill=NAVY_LIGHT, outline=YELLOW, width=6)
    tf, tl = fit(d, tool.upper(), "bold", 120, 2, 40, 18)
    y = 120 - len(tl) * int(tf.size * 1.1) // 2
    for line in tl:
        d.text((130 - d.textlength(line, font=tf) / 2, y), line, font=tf, fill=WHITE)
        y += int(tf.size * 1.1)


def make(words: str, tool: str, path, before: str = "", after: str = "") -> None:
    img = Image.new("RGB", (W, H), NAVY)
    if before and after:
        img = _glow(img)
        _before_after(img, before, after)
        d = ImageDraw.Draw(img)
        _tool_badge(d, tool)
        _words(d, words, 700, 540)
        img.save(path, quality=92)
        return

    d = ImageDraw.Draw(img)
    # left panel with the tool name
    d.rounded_rectangle([50, 140, 470, 580], radius=40, fill=NAVY_LIGHT, outline=YELLOW, width=8)
    tf, tl = fit(d, tool.upper(), "bold", 360, 3, 92, 40)
    th = len(tl) * int(tf.size * 1.1)
    y = 360 - th // 2
    for line in tl:
        d.text((260 - d.textlength(line, font=tf) / 2, y), line, font=tf, fill=WHITE)
        y += int(tf.size * 1.1)
    # arrow pointing at the panel
    d.polygon([(560, 360), (500, 300), (500, 330), (430, 330), (430, 390), (500, 390), (500, 420)],
              fill=YELLOW)
    # big words, last word in yellow
    wf, wl = fit(d, words.upper(), "bold", 680, 3, 150, 70)
    total = len(wl) * int(wf.size * 1.05)
    y = 360 - total // 2
    for i, line in enumerate(wl):
        d.text((570, y), line, font=wf, fill=YELLOW if i == len(wl) - 1 else WHITE,
               stroke_width=4, stroke_fill=(0, 0, 0))
        y += int(wf.size * 1.05)
    d.rectangle([0, H - 16, W, H], fill=YELLOW)
    img.save(path, quality=92)
