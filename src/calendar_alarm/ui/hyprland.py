from __future__ import annotations

import json
import os
import shutil
import subprocess


def is_hyprland() -> bool:
    return bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))


def _hyprctl(*args: str) -> subprocess.CompletedProcess[str] | None:
    if not is_hyprland():
        return None
    executable = shutil.which("hyprctl")
    if executable is None:
        return None
    try:
        return subprocess.run(
            [executable, *args], capture_output=True, text=True, timeout=2, check=False
        )
    except Exception:
        return None


def _lua(dispatcher: str, address: str) -> bool:
    """Hyprland >= 0.5x (API Lua): hl.dispatch(hl.dsp.window.<dispatcher>(...))."""
    return _lua_call(f'hl.dispatch(hl.dsp.window.{dispatcher}({{ window = "address:{address}" }}))')


def _lua_call(code: str) -> bool:
    result = _hyprctl("eval", code)
    return result is not None and result.returncode == 0 and not result.stdout.startswith("error")


def _classic(command: str, *args: str) -> bool:
    """Hyprland clásico (y respaldo): hyprctl dispatch <command> <args>."""
    result = _hyprctl("dispatch", command, *args)
    return result is not None and not result.stdout.startswith("error")


def _clients() -> list[dict]:
    result = _hyprctl("clients", "-j")
    if result is None or result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _active_address() -> str | None:
    result = _hyprctl("activewindow", "-j")
    if result is None or result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return data.get("address") if isinstance(data, dict) else None


def _find_client(title: str) -> dict | None:
    for client in _clients():
        if client.get("title") == title:
            return client
    return None


def _ensure_state(title: str, prop: str, lua_name: str, classic_name: str) -> None:
    """Aplica un dispatcher booleano (float/pin) solo si aún no está aplicado.

    `pin` es un toggle en Hyprland: llamarlo dos veces desfijaría la ventana.
    Además se comprueba el resultado real antes de probar el siguiente método,
    para no repetir una acción ya efectiva.
    """
    client = _find_client(title)
    if client is None or client.get(prop):
        return
    address = client.get("address") or ""

    if address and _lua(lua_name, address):
        client = _find_client(title)
        if client is not None and client.get(prop):
            return

    # Respaldo para versiones clásicas. Se prefiere `activewindow` únicamente
    # si la ventana activa es la nuestra, para no tocar ventanas ajenas.
    if address and _active_address() == address:
        _classic(classic_name, "activewindow")
        client = _find_client(title)
        if client is not None and client.get(prop):
            return
    if address:
        _classic(classic_name, f"address:{address}")


def float_alarm_window(title: str) -> None:
    _ensure_state(title, "floating", "float", "setfloating")


def center_alarm_window(title: str) -> None:
    client = _find_client(title)
    address = (client or {}).get("address") or ""
    if not address:
        return
    if _lua("center", address):
        return
    _classic("centerwindow", f"address:{address}")


def resize_alarm_window(title: str, width: int, height: int) -> bool:
    """Ajusta el tamaño exacto de la ventana flotante.

    Qt no consigue redimensionar una ventana ya flotante en Hyprland
    (Wayland no propaga el resize), así que se hace vía hyprctl.
    Devuelve False si no se pudo (el llamante puede usar Qt como respaldo).
    """
    client = _find_client(title)
    address = (client or {}).get("address") or ""
    if not address:
        return False

    if _lua_call(
        f'hl.dispatch(hl.dsp.window.resize({{ window = "address:{address}", '
        f"x = {int(width)}, y = {int(height)}, relative = false }}))"
    ):
        return True

    if _active_address() == address:
        return _classic("resizeactive", "exact", str(int(width)), str(int(height)))
    return False


def pin_alarm_window(title: str) -> None:
    _ensure_state(title, "pinned", "pin", "pin")
