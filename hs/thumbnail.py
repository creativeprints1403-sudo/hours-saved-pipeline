"""Thumbnail from the channel template: tool badge, 2-4 big words, yellow arrow."""
from PIL import Image, ImageDraw

from .cards import NAVY, NAVY_LIGHT, WHITE, YELLOW, fit, font

W, H = 1280, 720


def make(words: str, tool: str, path) -> None:
    img = Image.new("RGB", (W, H), NAVY)
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
