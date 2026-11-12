"""Genera el sonido de alarma por defecto (src/calendar_alarm/assets/alarm.wav).

Solo usa la librería estándar. Uso:  python3 scripts/generate_default_sound.py
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parents[1] / "src" / "calendar_alarm" / "assets" / "alarm.wav"

# Patrón de "timbre": (inicio, duración, frecuencia) en segundos / Hz
PATTERN = [
    (0.00, 0.22, 988.00),  # SI5
    (0.30, 0.22, 1319.00),  # MI6
    (0.60, 0.22, 1175.00),  # LA#5
    (0.88, 0.34, 1568.00),  # SOL6
]
TOTAL = 1.35  # duración total del bucle


def sample(freq: float, t: float) -> float:
    # Seno con armónico para un timbre más "eléctrico" y envolvente suave
    wave_val = 0.72 * math.sin(2 * math.pi * freq * t)
    wave_val += 0.28 * math.sin(2 * math.pi * freq * 2 * t)
    return wave_val


def envelope(t_local: float, duration: float) -> float:
    attack = min(0.012, duration / 4)
    release = min(0.05, duration / 3)
    if t_local < attack:
        return t_local / attack
    if t_local > duration - release:
        return max(0.0, (duration - t_local) / release)
    return 1.0


def main() -> None:
    total_samples = int(RATE * TOTAL)
    frames = bytearray()
    amplitude = 0.62

    for i in range(total_samples):
        t = i / RATE
        value = 0.0
        for start, duration, freq in PATTERN:
            if start <= t < start + duration:
                value = sample(freq, t - start) * envelope(t - start, duration)
                break
        # Ligera onda de fondo grave para dar cuerpo al silencio entre pitidos
        value += 0.05 * math.sin(2 * math.pi * 196.0 * t)
        frames += struct.pack("<h", int(max(-1.0, min(1.0, value * amplitude)) * 32767))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(bytes(frames))

    print(f"Sonido generado: {OUT} ({OUT.stat().st_size / 1024:.1f} KiB, {TOTAL} s)")


if __name__ == "__main__":
    main()
