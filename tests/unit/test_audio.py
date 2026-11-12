from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from calendar_alarm import audio as audio_module
from calendar_alarm.audio import AudioPlayer


@pytest.fixture
def fake_pygame(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(audio_module, "pygame", fake)
    return fake


def test_estado_inicial(fake_pygame):
    player = AudioPlayer()
    assert player.available is False
    assert player.last_error is None
    fake_pygame.mixer.init.assert_not_called()  # el mezclador se abre bajo demanda


def test_play_loop_reproduce_en_bucle_infinito(fake_pygame):
    player = AudioPlayer()
    assert player.play_loop("/a.wav") is True
    fake_pygame.mixer.init.assert_called_once()
    fake_pygame.mixer.music.load.assert_called_once_with("/a.wav")
    fake_pygame.mixer.music.set_volume.assert_called_once_with(1.0)
    fake_pygame.mixer.music.play.assert_called_once_with(loops=-1)
    assert player.available
    assert player.last_error is None


def test_el_mezclador_se_inicializa_una_sola_vez(fake_pygame):
    player = AudioPlayer()
    player.play_loop("/a.wav")
    player.test("/a.wav")
    fake_pygame.mixer.init.assert_called_once()


def test_sin_dispositivo_de_audio(fake_pygame):
    fake_pygame.mixer.init.side_effect = RuntimeError("no device")
    player = AudioPlayer()
    assert player.play_loop("/a.wav") is False
    assert player.available is False
    assert player.last_error == "Sin dispositivo de audio: no device"
    assert player.test("/a.wav") is False


def test_archivo_que_no_se_puede_cargar(fake_pygame):
    fake_pygame.mixer.music.load.side_effect = RuntimeError("formato raro")
    player = AudioPlayer()
    assert player.play_loop("/x.xyz") is False
    assert player.last_error == "No se pudo reproducir el sonido: formato raro"
    assert player.test("/x.xyz") is False
    assert player.last_error == "No se pudo reproducir el sonido: formato raro"


def test_reproducir_bien_limpia_el_error_anterior(fake_pygame):
    player = AudioPlayer()
    fake_pygame.mixer.music.load.side_effect = [RuntimeError("x"), None, RuntimeError("y"), None]
    assert not player.play_loop("/a")
    assert player.play_loop("/b")
    assert player.last_error is None
    assert not player.test("/a")
    assert player.test("/b")
    assert player.last_error is None


def test_recuperacion_tras_fallo_de_inicializacion(fake_pygame):
    fake_pygame.mixer.init.side_effect = [RuntimeError("ocupado"), None]
    player = AudioPlayer()
    assert not player.play_loop("/a")
    assert player.play_loop("/a")
    assert player.last_error is None


def test_test_reproduce_una_sola_vez(fake_pygame):
    player = AudioPlayer()
    assert player.test("/a.wav") is True
    fake_pygame.mixer.music.play.assert_called_once_with(loops=0)


def test_stop_sin_inicializar_no_toca_pygame(fake_pygame):
    AudioPlayer().stop()
    fake_pygame.mixer.music.stop.assert_not_called()


def test_stop_detiene_la_musica(fake_pygame):
    player = AudioPlayer()
    player.play_loop("/a")
    player.stop()
    fake_pygame.mixer.music.stop.assert_called_once()


def test_stop_tolera_errores(fake_pygame):
    fake_pygame.mixer.music.stop.side_effect = RuntimeError("x")
    player = AudioPlayer()
    player.play_loop("/a")
    player.stop()  # no lanza


def test_shutdown_cierra_el_mezclador(fake_pygame):
    player = AudioPlayer()
    player.play_loop("/a")
    player.shutdown()
    fake_pygame.mixer.music.stop.assert_called_once()
    fake_pygame.mixer.quit.assert_called_once()
    assert player.available is False


def test_shutdown_sin_inicializar_no_hace_nada(fake_pygame):
    AudioPlayer().shutdown()
    fake_pygame.mixer.quit.assert_not_called()


def test_shutdown_tolera_errores_y_queda_cerrado(fake_pygame):
    fake_pygame.mixer.quit.side_effect = RuntimeError("x")
    player = AudioPlayer()
    player.play_loop("/a")
    player.shutdown()
    assert player.available is False


def test_audio_real_con_driver_nulo():
    """Con el pygame real y SDL_AUDIODRIVER=dummy (conftest) el ciclo completo funciona."""
    from calendar_alarm.config import default_sound_path

    player = AudioPlayer()
    assert player.test(default_sound_path()), player.last_error
    player.stop()
    player.shutdown()
    assert player.available is False


def test_ensure_mixer_limpia_el_error_al_recuperarse(fake_pygame):
    fake_pygame.mixer.init.side_effect = [RuntimeError("ocupado"), None]
    player = AudioPlayer()
    assert player._ensure_mixer() is False
    assert player._ensure_mixer() is True
    assert player.last_error is None
