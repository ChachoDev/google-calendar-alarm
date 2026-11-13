from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from calendar_alarm.alarm_controller import AlarmController
from calendar_alarm.config import Config


class FakeAudio:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.played: list[str] = []
        self.stops = 0
        self.last_error: str | None = None if ok else "sin audio"

    def play_loop(self, path: str) -> bool:
        self.played.append(path)
        return self.ok

    def stop(self) -> None:
        self.stops += 1


@pytest.fixture
def audio():
    return FakeAudio()


@pytest.fixture
def config():
    return Config(warn_hours=0, warn_minutes=5, poll_minutes=5)


@pytest.fixture
def controller(audio, config):
    return AlarmController(audio, config)  # type: ignore[arg-type]


@pytest.fixture
def frozen_now(monkeypatch):
    """Fija «ahora» para comprobar los límites exactos de la ventana de aviso."""
    now = datetime(2026, 5, 4, 10, 0, 0).astimezone()

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return now if tz is None else now.astimezone(tz)

    import calendar_alarm.alarm_controller as module

    monkeypatch.setattr(module, "datetime", FrozenDatetime)
    return now


def collect(controller):
    started, stopped, errors = [], [], []
    controller.alarm_started.connect(lambda *args: started.append(args[0] if args else True))
    controller.alarm_stopped.connect(lambda: stopped.append(True))
    controller.audio_error.connect(lambda *args: errors.append(args[0] if args else True))
    return started, stopped, errors


def test_suena_dentro_del_margen(controller, audio, make_event, config):
    started, _, _ = collect(controller)
    event = make_event(minutes_from_now=3)
    controller.on_events([event])
    assert controller.ringing
    assert controller.current_event is event
    assert started == [event]
    assert audio.played == [config.resolved_sound_path]


def test_no_suena_fuera_del_margen(controller, audio, make_event):
    controller.on_events([make_event(minutes_from_now=30)])
    assert not controller.ringing
    assert audio.played == []


def test_lista_vacia_no_hace_nada(controller, audio):
    controller.on_events([])
    assert not controller.ringing
    assert audio.played == []


def test_limite_exacto_inicio_del_margen_suena(controller, make_event, frozen_now):
    controller.on_events([make_event(start=frozen_now + timedelta(minutes=5))])
    assert controller.ringing


def test_un_segundo_antes_del_margen_no_suena(controller, make_event, frozen_now):
    controller.on_events([make_event(start=frozen_now + timedelta(minutes=5, seconds=1))])
    assert not controller.ringing


def test_evento_recien_empezado_dentro_de_la_tolerancia_suena(controller, make_event, frozen_now):
    # Tolerancia = un ciclo de consulta (5 min): no se pierde el aviso entre consultas.
    controller.on_events([make_event(start=frozen_now - timedelta(minutes=5))])
    assert controller.ringing


def test_evento_empezado_hace_mas_de_un_ciclo_no_suena(controller, make_event, frozen_now):
    controller.on_events([make_event(start=frozen_now - timedelta(minutes=5, seconds=1))])
    assert not controller.ringing


def test_tolerancia_minima_de_cinco_minutos(audio, make_event, frozen_now):
    # poll_minutes=1 se recorta al mínimo de 5 minutos.
    controller = AlarmController(audio, Config(poll_minutes=1))  # type: ignore[arg-type]
    controller.on_events([make_event(start=frozen_now - timedelta(minutes=5))])
    assert controller.ringing


def test_tolerancia_minima_no_se_extiende_de_mas(audio, make_event, frozen_now):
    controller = AlarmController(audio, Config(poll_minutes=1))  # type: ignore[arg-type]
    controller.on_events([make_event(start=frozen_now - timedelta(minutes=5, seconds=1))])
    assert not controller.ringing


def test_margen_en_horas(audio, make_event, frozen_now):
    controller = AlarmController(audio, Config(warn_hours=1, warn_minutes=0))  # type: ignore[arg-type]
    controller.on_events([make_event(start=frozen_now + timedelta(minutes=59))])
    assert controller.ringing


def test_elige_el_evento_mas_proximo(controller, make_event):
    later = make_event(id="b", minutes_from_now=4)
    sooner = make_event(id="a", minutes_from_now=1)
    controller.on_events([later, sooner])
    assert controller.current_event is sooner


def test_mientras_suena_no_se_reengancha(controller, make_event, audio):
    first = make_event(id="a", minutes_from_now=2)
    controller.on_events([first])
    controller.on_events([make_event(id="b", minutes_from_now=1)])
    assert controller.current_event is first
    assert len(audio.played) == 1


def test_mismo_evento_no_vuelve_a_sonar(controller, make_event, audio):
    event = make_event()
    controller.on_events([event])
    controller.stop()
    controller.on_events([event])
    assert not controller.ringing
    assert len(audio.played) == 1


def test_evento_movido_a_otra_hora_vuelve_a_avisar(controller, make_event):
    controller.on_events([make_event(id="x", minutes_from_now=3)])
    controller.stop()
    controller.on_events([make_event(id="x", minutes_from_now=4)])
    assert controller.ringing


def test_forget_handled_permite_volver_a_avisar(controller, make_event):
    event = make_event()
    controller.on_events([event])
    controller.stop()
    controller.forget_handled()
    controller.on_events([event])
    assert controller.ringing


def test_stop_detiene_audio_y_emite_senal(controller, make_event, audio):
    _, stopped, _ = collect(controller)
    controller.on_events([make_event()])
    controller.stop()
    assert not controller.ringing
    assert controller.current_event is None
    assert audio.stops == 1
    assert stopped == [True]


def test_stop_es_idempotente(controller, audio):
    _, stopped, _ = collect(controller)
    controller.stop()
    controller.stop()
    assert audio.stops == 0
    assert stopped == []


def test_fallo_de_audio_avisa_pero_muestra_la_alarma(make_event, config):
    audio = FakeAudio(ok=False)
    controller = AlarmController(audio, config)  # type: ignore[arg-type]
    started, _, errors = collect(controller)
    controller.on_events([make_event()])
    assert controller.ringing
    assert errors == ["sin audio"]
    assert len(started) == 1


def test_fallo_de_audio_sin_detalle_usa_mensaje_generico(make_event, config):
    audio = FakeAudio(ok=False)
    audio.last_error = None
    controller = AlarmController(audio, config)  # type: ignore[arg-type]
    _, _, errors = collect(controller)
    controller.on_events([make_event()])
    assert errors == ["No se pudo reproducir el sonido de la alarma."]


def test_usa_el_sonido_personalizado(audio, make_event):
    controller = AlarmController(audio, Config(sound_path="/x/mi.ogg"))  # type: ignore[arg-type]
    controller.on_events([make_event()])
    assert audio.played == ["/x/mi.ogg"]


def test_estado_inicial(controller):
    assert controller.ringing is False
    assert controller.current_event is None


def test_tras_parar_vuelve_a_reposo_exacto(controller, make_event):
    controller.on_events([make_event()])
    controller.stop()
    assert controller.ringing is False


def test_acepta_padre_qt(audio, config):
    from PySide6.QtCore import QObject

    parent = QObject()
    controller = AlarmController(audio, config, parent=parent)  # type: ignore[arg-type]
    assert controller.parent() is parent
