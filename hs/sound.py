"""Original background music and small sound effects, generated here (no licences needed)."""
import numpy as np

SR = 24000  # same rate as the voice


def _note(m):
    return 440.0 * 2 ** ((m - 69) / 12)


CHORDS = [[48, 55, 59, 64], [45, 52, 55, 60], [41, 48, 52, 57], [43, 50, 55, 59]]  # Cmaj7 Am7 Fmaj7 G
ARP = [0, 2, 3, 1, 2, 3, 1, 2]


def music(seconds, seed=1, bpm=100):
    """Light, upbeat bed: soft pad, plucked arpeggio, a quiet kick and hat on the beat."""
    n = int(seconds * SR)
    out = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = beat * 4
    for b in range(int(np.ceil(seconds / bar))):
        ch = CHORDS[b % 4]
        s0 = int(b * bar * SR)
        s1 = min(n, int((b + 1) * bar * SR + 1.0 * SR))
        if s0 >= n:
            break
        tt = np.arange(s1 - s0) / SR
        env = np.minimum(1, tt / 0.8) * np.exp(-np.maximum(0, tt - bar) / 0.5)
        seg = np.zeros(s1 - s0)
        for m in ch:
            f = _note(m)
            for det in (-0.15, 0.15):
                seg += np.sin(2 * np.pi * f * (1 + det / 100) * tt + rng.random() * 6) * 0.07
        out[s0:s1] += (seg * env).astype(np.float32)
        for i, k in enumerate(ARP):  # eighth-note pluck
            p0 = int((b * bar + i * beat / 2) * SR)
            if p0 >= n:
                break
            L = min(n - p0, int(0.6 * SR))
            tp = np.arange(L) / SR
            out[p0:p0 + L] += (np.sin(2 * np.pi * _note(ch[k] + 12) * tp) * np.exp(-tp / 0.18) * 0.09).astype(np.float32)
        for q in range(4):  # kick on every beat, hat on the off-beat
            p0 = int((b * bar + q * beat) * SR)
            if p0 < n:
                L = min(n - p0, int(0.25 * SR))
                tp = np.arange(L) / SR
                f = 120 * np.exp(-tp * 30) + 45
                out[p0:p0 + L] += (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tp * 14) * 0.22).astype(np.float32)
            p1 = int((b * bar + q * beat + beat / 2) * SR)
            if p1 < n:
                L = min(n - p1, int(0.05 * SR))
                hat = rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 90) * 0.035
                out[p1:p1 + L] += np.diff(hat, prepend=0).astype(np.float32)
    t = np.arange(n) / SR
    out *= np.minimum(1, t / 1.5) * np.minimum(1, (seconds - t) / 2.5)
    return out / (np.max(np.abs(out)) + 1e-9) * 0.8


def whoosh(rng):
    L = int(0.35 * SR)
    noise = rng.standard_normal(L)
    # band-passed noise: a short smoothing window minus a long one
    out = np.convolve(noise, np.ones(12) / 12, mode="same") - np.convolve(noise, np.ones(60) / 60, mode="same")
    env = np.sin(np.linspace(0, np.pi, L)) ** 2
    return (out * env * 0.5).astype(np.float32)


def pop():
    L = int(0.07 * SR)
    t = np.arange(L) / SR
    f = 900 * np.exp(-t * 25) + 500
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 60) * 0.35).astype(np.float32)


def clicks(seconds, rng):
    """Soft keyboard ticks for a typing animation."""
    L = int(seconds * SR)
    out = np.zeros(L, dtype=np.float32)
    t = 0.0
    while t < seconds:
        p = int(t * SR)
        k = min(L - p, int(0.012 * SR))
        out[p:p + k] += (rng.standard_normal(k) * np.exp(-np.arange(k) / SR * 600) * 0.12).astype(np.float32)
        t += rng.uniform(0.05, 0.11)
    return out


def effects(total, cues, seed=2):
    """cues: list of (time, kind, length). Returns a mono track of `total` seconds."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(total * SR) + SR, dtype=np.float32)
    for t, kind, ln in cues:
        clip = {"whoosh": lambda: whoosh(rng), "pop": pop, "type": lambda: clicks(ln, rng)}[kind]()
        p = int(t * SR)
        k = min(len(out) - p, len(clip))
        if k > 0:
            out[p:p + k] += clip[:k]
    return out[: int(total * SR)]
