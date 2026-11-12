from __future__ import annotations

import json

import pytest

from calendar_alarm import oauth_client as oc


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_sin_credenciales_no_esta_configurado(no_bundled_client):
    assert oc.client_config() is None
    assert oc.is_configured() is False


def test_constantes_del_modulo_tienen_prioridad(monkeypatch, no_bundled_client):
    monkeypatch.setattr(oc, "CLIENT_ID", "const-id")
    monkeypatch.setattr(oc, "CLIENT_SECRET", "const-secret")
    monkeypatch.setenv(oc.ENV_ID, "env-id")
    monkeypatch.setenv(oc.ENV_SECRET, "env-secret")
    config = oc.client_config()
    assert config == {
        "installed": {
            "client_id": "const-id",
            "client_secret": "const-secret",
            "auth_uri": oc.AUTH_URI,
            "token_uri": oc.TOKEN_URI,
        }
    }
    assert oc.is_configured()


def test_constante_incompleta_no_cuenta(monkeypatch, no_bundled_client):
    monkeypatch.setattr(oc, "CLIENT_ID", "solo-id")
    assert oc.client_config() is None


def test_variables_de_entorno(monkeypatch, no_bundled_client):
    monkeypatch.setenv(oc.ENV_ID, "  env-id ")
    monkeypatch.setenv(oc.ENV_SECRET, " env-secret  ")
    installed = oc.client_config()["installed"]  # type: ignore[index]
    assert installed["client_id"] == "env-id"
    assert installed["client_secret"] == "env-secret"
    assert installed["token_uri"] == oc.TOKEN_URI


@pytest.mark.parametrize("missing", [oc.ENV_ID, oc.ENV_SECRET])
def test_variables_de_entorno_incompletas(monkeypatch, no_bundled_client, missing):
    monkeypatch.setenv(oc.ENV_ID, "id")
    monkeypatch.setenv(oc.ENV_SECRET, "secret")
    monkeypatch.delenv(missing)
    assert oc.client_config() is None


def test_archivo_de_entorno_tiene_prioridad_sobre_id_y_secret(
    monkeypatch, tmp_path, no_bundled_client
):
    path = write(tmp_path / "c.json", {"installed": {"client_id": "file-id", "client_secret": "s"}})
    monkeypatch.setenv(oc.ENV_FILE, str(path))
    monkeypatch.setenv(oc.ENV_ID, "env-id")
    monkeypatch.setenv(oc.ENV_SECRET, "env-secret")
    assert oc.client_config()["installed"]["client_id"] == "file-id"  # type: ignore[index]


def test_archivo_de_entorno_invalido_cae_a_id_y_secret(monkeypatch, tmp_path, no_bundled_client):
    monkeypatch.setenv(oc.ENV_FILE, str(tmp_path / "no-existe.json"))
    monkeypatch.setenv(oc.ENV_ID, "env-id")
    monkeypatch.setenv(oc.ENV_SECRET, "env-secret")
    assert oc.client_config()["installed"]["client_id"] == "env-id"  # type: ignore[index]


def test_archivo_tipo_web_se_normaliza_a_installed(tmp_path):
    path = write(tmp_path / "w.json", {"web": {"client_id": "w", "client_secret": "s"}})
    assert oc._read_client_file(path) == {"installed": {"client_id": "w", "client_secret": "s"}}


@pytest.mark.parametrize(
    "content",
    [
        "no json",
        "[]",
        '{"otro": {}}',
        '{"installed": {"client_secret": "s"}}',
        '{"installed": "x"}',
    ],
)
def test_archivos_no_validos(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    assert oc._read_client_file(path) is None


def test_archivo_inexistente(tmp_path):
    assert oc._read_client_file(tmp_path / "nada.json") is None


def test_recurso_empaquetado_como_ultima_opcion(monkeypatch, tmp_path, no_bundled_client):
    path = write(tmp_path / "google_client.json", {"installed": {"client_id": "bundled"}})
    monkeypatch.setattr(oc, "asset_path", lambda rel: path if rel == oc.CLIENT_FILE else None)
    assert oc.client_config()["installed"]["client_id"] == "bundled"  # type: ignore[index]
