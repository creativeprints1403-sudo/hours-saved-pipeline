"""Draw the on-screen cards in the channel's brand (navy, yellow, white)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = (20, 33, 61)
NAVY_LIGHT = (32, 50, 88)
YELLOW = (252, 163, 17)
WHITE = (255, 255, 255)
GREY = (190, 198, 214)

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def font(size: int, kind: str = "bold") -> ImageFont.FreeTypeFont:
    name = {"bold": "Montserrat-ExtraBold.ttf", "body": "Montserrat-SemiBold.ttf",
            "mono": "DejaVuSansMono-Bold.ttf"}[kind]
    return ImageFont.truetype(str(FONTS / name), size)


def wrap(draw, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=fnt) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(draw, text, kind, width, max_lines, start, smallest):
    """Largest font size at which text wraps into max_lines within width."""
    size = start
    while size > smallest:
        f = font(size, kind)
        lines = wrap(draw, text, f, width)
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= width for l in lines):
            return f, lines
        size -= 4
    f = font(smallest, kind)
    return f, wrap(draw, text, f, width)


def _frame(w, h, channel):
    img = Image.new("RGB", (w, h), NAVY)
    d = ImageDraw.Draw(img)
    s = w / 1920 if w > h else w / 1080
    d.rectangle([0, 0, w, int(10 * s)], fill=YELLOW)
    d.text((int(60 * s), h - int(70 * s)), channel.upper(), font=font(int(26 * s), "bold"), fill=GREY)
    return img, d, s


def draw_card(card, shown: int, size, channel: str, step_label: str = "") -> Image.Image:
    """Render a card with the first `shown` lines visible (lines appear one by one)."""
    w, h = size
    vertical = h > w
    img, d, s = _frame(w, h, channel)
    margin = int((90 if not vertical else 70) * s)
    inner = w - 2 * margin
    y = int((110 if not vertical else 300) * s)

    if card.kind == "title":
        hf, hl = fit(d, card.heading.upper(), "bold", inner, 3, int(120 * s), int(60 * s))
        y = int(h * (0.30 if not vertical else 0.32))
        for line in hl:
            d.text((margin, y), line, font=hf, fill=WHITE)
            y += int(hf.size * 1.12)
        d.rectangle([margin, y + int(20 * s), margin + int(220 * s), y + int(34 * s)], fill=YELLOW)
        y += int(80 * s)
        bf = font(int(44 * s), "body")
        for text in card.lines[:shown]:
            for line in wrap(d, text, bf, inner):
                d.text((margin, y), line, font=bf, fill=GREY)
                y += int(bf.size * 1.3)
        return img

    label = {"warning": "WATCH OUT", "tip": "TIP", "recap": "RECAP"}.get(card.kind, step_label)
    # Measure the finished card, then centre it vertically so it doesn't jump as lines appear.
    probe = ImageDraw.Draw(Image.new("RGB", (w, h)))
    height = _body(probe, card, len(card.lines), label, 0, margin, inner, w, s, vertical)
    top = max(y, (h - height) // 2 - int(30 * s))
    _body(d, card, shown, label, top, margin, inner, w, s, vertical)
    return img


def _body(d, card, shown, label, y, margin, inner, w, s, vertical):
    """Draw label, heading and the first `shown` lines from y downwards; return the end y."""
    y0 = y
    accent = {"warning": (230, 80, 70), "tip": YELLOW}.get(card.kind, YELLOW)
    if label:
        lf = font(int(30 * s), "bold")
        tw = d.textlength(label, font=lf)
        d.rounded_rectangle([margin, y, margin + tw + int(40 * s), y + int(56 * s)],
                            radius=int(28 * s), fill=accent)
        d.text((margin + int(20 * s), y + int(11 * s)), label, font=lf, fill=NAVY)
        y += int(90 * s)

    hf, hl = fit(d, card.heading, "bold", inner, 2, int(84 * s), int(52 * s))
    for line in hl:
        d.text((margin, y), line, font=hf, fill=WHITE)
        y += int(hf.size * 1.15)
    y += int(40 * s)

    body_size = int((46 if not vertical else 58) * s)
    for i, text in enumerate(card.lines[:shown]):
        if card.kind == "chat":
            who, _, msg = text.partition(":")
            is_ai = who.strip().lower() in ("ai", "chatgpt", "claude", "gemini")
            bf = font(int(body_size * 0.9), "body")
            lines = wrap(d, msg.strip() or text, bf, inner - int(120 * s))
            bh = len(lines) * int(bf.size * 1.3) + int(50 * s)
            x0 = margin + (int(80 * s) if is_ai else 0)
            x1 = w - margin - (0 if is_ai else int(80 * s))
            d.rounded_rectangle([x0, y, x1, y + bh], radius=int(24 * s),
                                fill=NAVY_LIGHT if is_ai else WHITE)
            d.text((x0 + int(30 * s), y - int(34 * s)), "AI" if is_ai else "YOU",
                   font=font(int(24 * s), "bold"), fill=YELLOW)
            ty = y + int(25 * s)
            for line in lines:
                d.text((x0 + int(30 * s), ty), line, font=bf, fill=WHITE if is_ai else NAVY)
                ty += int(bf.size * 1.3)
            y += bh + int(60 * s)
        elif card.kind == "code":
            mf, ml = fit(d, text, "mono", inner - int(60 * s), 3, int(body_size * 0.95), int(26 * s))
            bh = len(ml) * int(mf.size * 1.35) + int(44 * s)
            d.rounded_rectangle([margin, y, w - margin, y + bh], radius=int(16 * s), fill=(10, 18, 36))
            ty = y + int(22 * s)
            for line in ml:
                d.text((margin + int(30 * s), ty), line, font=mf, fill=YELLOW)
                ty += int(mf.size * 1.35)
            y += bh + int(30 * s)
        else:
            bf = font(body_size, "body")
            bullet = f"{i + 1}" if card.kind in ("steps", "recap") else "•"
            d.ellipse([margin, y + int(4 * s), margin + int(54 * s), y + int(58 * s)], fill=accent)
            bw = d.textlength(bullet, font=font(int(30 * s), "bold"))
            d.text((margin + int(27 * s) - bw / 2, y + int(13 * s)), bullet,
                   font=font(int(30 * s), "bold"), fill=NAVY)
            for line in wrap(d, text, bf, inner - int(90 * s)):
                d.text((margin + int(85 * s), y), line, font=bf, fill=WHITE)
                y += int(bf.size * 1.3)
            y += int(28 * s)
    return y - y0


def draw_hook(text: str, size, channel: str) -> Image.Image:
    """Big first frame of a Short."""
    w, h = size
    img, d, s = _frame(w, h, channel)
    margin = int(70 * s)
    hf, hl = fit(d, text.upper(), "bold", w - 2 * margin, 6, int(110 * s), int(60 * s))
    y = int(h * 0.30)
    for i, line in enumerate(hl):
        d.text((margin, y), line, font=hf, fill=YELLOW if i == 0 else WHITE)
        y += int(hf.size * 1.15)
    return img
