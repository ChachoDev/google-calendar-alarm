from __future__ import annotations

import threading

import pygame


class AudioPlayer:
    """Reproduce el sonido de alarma en bucle sin bloquear la interfaz gráfica.

    pygame.mixer.music se reproduce de forma asíncrona: `play()` devuelve
    inmediatamente y el hilo de audio sigue sonando en segundo plano.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._initialized = False
        self._last_error: str | None = None

    @property
    def available(self) -> bool:
        return self._initialized

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _ensure_mixer(self) -> bool:
        if self._initialized:
            return True
        try:
            pygame.mixer.init()
            self._initialized = True
            self._last_error = None
        except Exception as exc:  # pygame.error si no hay dispositivo de audio
            self._last_error = f"Sin dispositivo de audio: {exc}"
            self._initialized = False
        return self._initialized

    def play_loop(self, path: str) -> bool:
        """Inicia la reproducción en bucle infinito. No bloquea."""
        with self._lock:
            if not self._ensure_mixer():
                return False
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(1.0)
                pygame.mixer.music.play(loops=-1)
                self._last_error = None
                return True
            except Exception as exc:
                self._last_error = f"No se pudo reproducir el sonido: {exc}"
                return False

    def stop(self) -> None:
        with self._lock:
            if not self._initialized:
                return
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    def test(self, path: str) -> bool:
        """Reproduce una sola vez para que el usuario pruebe el sonido."""
        with self._lock:
            if not self._ensure_mixer():
                return False
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.play(loops=0)
                self._last_error = None
                return True
            except Exception as exc:
                self._last_error = f"No se pudo reproducir el sonido: {exc}"
                return False

    def shutdown(self) -> None:
        with self._lock:
            if self._initialized:
                try:
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
                except Exception:
                    pass
                self._initialized = False
