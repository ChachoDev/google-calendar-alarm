from __future__ import annotations

import threading
import time

from calendar_alarm.workers import CalendarWorker


def wait_until(qtbot, predicate, timeout=3000):
    qtbot.waitUntil(predicate, timeout=timeout)


def test_emite_eventos_y_duerme_el_intervalo(qtbot):
    calls = []
    worker = CalendarWorker(fetch_fn=lambda: calls.append(1) or ["e"], interval_fn=lambda: 60)
    received = []
    worker.events_ready.connect(lambda *args: received.append(args[0] if args else True))
    worker.start()
    try:
        wait_until(qtbot, lambda: received == [["e"]])
        time.sleep(0.2)
        assert len(calls) == 1  # duerme 60 s entre consultas
    finally:
        worker.stop()
    assert not worker.isRunning()


def test_errores_se_emiten_y_el_hilo_sigue(qtbot):
    attempts = []

    def fetch():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("red caída")
        return []

    worker = CalendarWorker(fetch_fn=fetch, interval_fn=lambda: 60)
    errors, events = [], []
    worker.error.connect(lambda *args: errors.append(args[0] if args else True))
    worker.events_ready.connect(lambda *args: events.append(args[0] if args else True))
    worker.start()
    try:
        wait_until(qtbot, lambda: errors == ["red caída"])
        worker.wake()
        wait_until(qtbot, lambda: events == [[]])
    finally:
        worker.stop()


def test_wake_fuerza_una_consulta_inmediata(qtbot):
    calls = []
    worker = CalendarWorker(fetch_fn=lambda: calls.append(1) or [], interval_fn=lambda: 600)
    worker.start()
    try:
        wait_until(qtbot, lambda: len(calls) == 1)
        worker.wake()
        wait_until(qtbot, lambda: len(calls) == 2)
    finally:
        worker.stop()


def test_intervalo_minimo_de_5_segundos(qtbot):
    calls = []
    worker = CalendarWorker(fetch_fn=lambda: calls.append(1) or [], interval_fn=lambda: 0)
    worker.start()
    try:
        wait_until(qtbot, lambda: len(calls) == 1)
        time.sleep(0.5)
        assert len(calls) == 1
    finally:
        worker.stop()


def test_stop_es_rapido_aunque_el_intervalo_sea_largo(qtbot):
    worker = CalendarWorker(fetch_fn=list, interval_fn=lambda: 3600)
    worker.start()
    qtbot.wait(100)
    started = time.monotonic()
    worker.stop()
    assert time.monotonic() - started < 1.5
    assert not worker.isRunning()


def test_stop_no_espera_a_una_consulta_colgada(qtbot):
    """Una consulta de red colgada no bloquea la salida ni emite después."""
    release = threading.Event()
    worker = CalendarWorker(fetch_fn=lambda: release.wait(10) or ["tarde"], interval_fn=lambda: 60)
    received = []
    worker.events_ready.connect(lambda *args: received.append(args[0] if args else True))
    worker.start()
    qtbot.wait(100)
    started = time.monotonic()
    assert worker.stop(timeout_ms=300) is False
    assert time.monotonic() - started < 1.0
    release.set()  # la consulta acaba después de pedir la parada
    qtbot.wait(300)
    assert received == []
    assert not worker.isRunning()


def test_el_hilo_es_daemon_y_no_bloquea_al_interprete(qtbot):
    worker = CalendarWorker(fetch_fn=list, interval_fn=lambda: 60)
    worker.start()
    try:
        assert worker._thread is not None and worker._thread.daemon
    finally:
        worker.stop()


def test_start_dos_veces_no_crea_otro_hilo(qtbot):
    worker = CalendarWorker(fetch_fn=list, interval_fn=lambda: 60)
    worker.start()
    first = worker._thread
    worker.start()
    try:
        assert worker._thread is first
    finally:
        worker.stop()


def test_stop_sin_arrancar():
    worker = CalendarWorker(fetch_fn=list, interval_fn=lambda: 60)
    assert worker.stop() is True
    assert not worker.isRunning()
