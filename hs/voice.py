"""Turn narration text into audio.

Default: Kokoro (free, Apache 2.0 licence, fine for monetized videos) run with sherpa-onnx on
the CPU, the same voice as video 1. The workflow downloads the model into models/kokoro.
Optional: ElevenLabs (paid plan needed to monetize).
"""
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 24000
MODEL = Path(os.environ.get("HS_KOKORO_DIR", Path(__file__).resolve().parent.parent / "models" / "kokoro"))
_tts = None

# Speaker ids in the kokoro-en-v0_19 model.
VOICES = ["af", "af_bella", "af_nicole", "af_sarah", "af_sky", "am_adam",
          "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"]


def _kokoro(text: str, voice: str, speed: float) -> np.ndarray:
    global _tts
    if _tts is None:
        import sherpa_onnx
        model = next(p for p in ("model.int8.onnx", "model.onnx") if (MODEL / p).exists())
        _tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model=str(MODEL / model), voices=str(MODEL / "voices.bin"),
                    tokens=str(MODEL / "tokens.txt"), data_dir=str(MODEL / "espeak-ng-data")),
                num_threads=os.cpu_count() or 2)))
    audio = _tts.generate(text, sid=VOICES.index(voice), speed=speed)
    assert audio.sample_rate == RATE, audio.sample_rate
    return np.asarray(audio.samples, dtype=np.float32)


def _elevenlabs(text: str, voice_id: str) -> np.ndarray:
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_24000",
        data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
    )
    pcm = urllib.request.urlopen(req, timeout=120).read()
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768


def speak(text: str, cfg: dict) -> np.ndarray:
    """Return mono float32 audio at 24 kHz, with a short pause after it."""
    v = cfg["voice"]
    if v["engine"] == "elevenlabs":
        audio = _elevenlabs(text, v["elevenlabs_voice_id"])
    else:
        audio = _kokoro(text, v["kokoro_voice"], v.get("speed", 1.0))
    pause = np.zeros(int(RATE * 0.45), dtype=np.float32)
    return np.concatenate([audio, pause])


def save(audio: np.ndarray, path) -> None:
    sf.write(path, audio, RATE)
