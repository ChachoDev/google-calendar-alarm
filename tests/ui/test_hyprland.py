from __future__ import annotations

import json
import subprocess

import pytest

from calendar_alarm.ui import hyprland as h


class FakeHyprctl:
    """Simula hyprctl: responde a clients/activewindow y registra los dispatch."""

    def __init__(self, clients=None, active=None, lua_ok=True, lua_applies=True):
        self.clients = clients or []
        self.active = active
        self.lua_ok = lua_ok
        self.lua_applies = lua_applies
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("clients", "-j"):
            return subprocess.CompletedProcess(args, 0, json.dumps(self.clients), "")
        if args[:2] == ("activewindow", "-j"):
            return subprocess.CompletedProcess(args, 0, json.dumps({"address": self.active}), "")
        if args[0] == "eval":
            if self.lua_ok and self.lua_applies:
                for client in self.clients:
                    if "float" in args[1]:
                        client["floating"] = True
                    if ".pin(" in args[1]:
                        client["pinned"] = True
            return subprocess.CompletedProcess(args, 0 if self.lua_ok else 1, "ok", "")
        if args[0] == "dispatch":
            for client in self.clients:
                if args[1] == "setfloating":
                    client["floating"] = True
                if args[1] == "pin":
                    client["pinned"] = True
            return subprocess.CompletedProcess(args, 0, "ok", "")
        return subprocess.CompletedProcess(args, 0, "", "")


@pytest.fixture
def fake(monkeypatch):
    def install(**kwargs):
        f = FakeHyprctl(**kwargs)
        monkeypatch.setattr(h, "_hyprctl", f)
        return f

    return install


def test_is_hyprland_depende_de_la_variable(monkeypatch):
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    assert h.is_hyprland() is False
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc")
    assert h.is_hyprland() is True


def test_hyprctl_fuera_de_hyprland_no_ejecuta_nada(monkeypatch):
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.setattr(h.subprocess, "run", lambda *a, **k: pytest.fail("no debe ejecutar"))
    assert h._hyprctl("clients") is None


def test_hyprctl_sin_binario(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc")
    monkeypatch.setattr(h.shutil, "which", lambda _n: None)
    assert h._hyprctl("clients") is None


def test_hyprctl_ejecuta_con_timeout(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc")
    monkeypatch.setattr(h.shutil, "which", lambda _n: "/usr/bin/hyprctl")
    seen = {}

    def run(cmd, **kwargs):
        seen.update(cmd=cmd, **kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(h.subprocess, "run", run)
    assert h._hyprctl("clients", "-j").returncode == 0
    assert seen["cmd"] == ["/usr/bin/hyprctl", "clients", "-j"]
    assert seen["timeout"] == 2


def test_hyprctl_tolera_excepciones(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc")
    monkeypatch.setattr(h.shutil, "which", lambda _n: "/usr/bin/hyprctl")
    monkeypatch.setattr(h.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert h._hyprctl("clients") is None


def test_float_con_api_lua(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1", "floating": False}])
    h.float_alarm_window("AVISO")
    assert any(c[0] == "eval" and "window.float" in c[1] for c in f.calls)
    assert not any(c[0] == "dispatch" for c in f.calls)


def test_float_ya_flotante_no_hace_nada(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1", "floating": True}])
    h.float_alarm_window("AVISO")
    assert [c[0] for c in f.calls] == ["clients"]


def test_float_ventana_inexistente(fake):
    f = fake(clients=[{"title": "otra", "address": "0x9"}])
    h.float_alarm_window("AVISO")
    assert not any(c[0] in ("eval", "dispatch") for c in f.calls)


def test_float_respaldo_clasico_con_ventana_activa(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1"}], active="0x1", lua_ok=False)
    h.float_alarm_window("AVISO")
    assert ("dispatch", "setfloating", "activewindow") in f.calls


def test_float_respaldo_clasico_por_direccion(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1"}], active="0x2", lua_ok=False)
    h.float_alarm_window("AVISO")
    assert ("dispatch", "setfloating", "address:0x1") in f.calls
    assert ("dispatch", "setfloating", "activewindow") not in f.calls


def test_pin_no_se_aplica_dos_veces(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1", "pinned": True}])
    h.pin_alarm_window("AVISO")
    assert not any(c[0] in ("eval", "dispatch") for c in f.calls)


def test_pin_con_lua(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1"}])
    h.pin_alarm_window("AVISO")
    assert sum(1 for c in f.calls if c[0] in ("eval", "dispatch")) == 1


def test_center(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1"}])
    h.center_alarm_window("AVISO")
    assert any(c[0] == "eval" and "window.center" in c[1] for c in f.calls)
    f2 = fake(clients=[{"title": "AVISO", "address": "0x1"}], lua_ok=False)
    h.center_alarm_window("AVISO")
    assert ("dispatch", "centerwindow", "address:0x1") in f2.calls


def test_center_sin_ventana(fake):
    f = fake(clients=[])
    h.center_alarm_window("AVISO")
    assert [c[0] for c in f.calls] == ["clients"]


def test_resize(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1"}])
    assert h.resize_alarm_window("AVISO", 700, 500) is True
    assert any("x = 700, y = 500" in c[1] for c in f.calls if c[0] == "eval")


def test_resize_respaldo_y_fallo(fake):
    f = fake(clients=[{"title": "AVISO", "address": "0x1"}], active="0x1", lua_ok=False)
    assert h.resize_alarm_window("AVISO", 700, 500) is True
    assert ("dispatch", "resizeactive", "exact", "700", "500") in f.calls
    fake(clients=[{"title": "AVISO", "address": "0x1"}], active="0x2", lua_ok=False)
    assert h.resize_alarm_window("AVISO", 700, 500) is False
    fake(clients=[])
    assert h.resize_alarm_window("AVISO", 700, 500) is False


def test_respuestas_no_validas_de_hyprctl(monkeypatch):
    def bad(*args):
        return subprocess.CompletedProcess(args, 0, "no json", "")

    monkeypatch.setattr(h, "_hyprctl", bad)
    assert h._clients() == []
    assert h._active_address() is None

    monkeypatch.setattr(h, "_hyprctl", lambda *a: subprocess.CompletedProcess(a, 0, "{}", ""))
    assert h._clients() == []
    monkeypatch.setattr(h, "_hyprctl", lambda *a: subprocess.CompletedProcess(a, 1, "[]", ""))
    assert h._clients() == []
    assert h._active_address() is None
    monkeypatch.setattr(h, "_hyprctl", lambda *a: subprocess.CompletedProcess(a, 0, "[]", ""))
    assert h._active_address() is None


def test_lua_y_clasico_detectan_error(monkeypatch):
    monkeypatch.setattr(h, "_hyprctl", lambda *a: subprocess.CompletedProcess(a, 0, "error: x", ""))
    assert h._lua_call("x") is False
    assert h._classic("pin", "x") is False
    monkeypatch.setattr(h, "_hyprctl", lambda *a: None)
    assert h._lua_call("x") is False
    assert h._classic("pin", "x") is False
