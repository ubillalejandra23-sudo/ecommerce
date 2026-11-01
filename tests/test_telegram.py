import pytest
from fastapi.testclient import TestClient

from api import app as api_app

SECRETO = "secreto-de-prueba"
HEADERS = {"X-Telegram-Bot-Api-Secret-Token": SECRETO}


class GrafoFalso:
    def invoke(self, entrada, config):
        return {"ruta": "generica", "motivo": "prueba", "respuesta": f"eco: {entrada['mensaje']}"}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    enviados = []
    monkeypatch.setattr(api_app, "enviar_mensaje", lambda chat_id, texto: enviados.append((chat_id, texto)))
    with TestClient(api_app.app) as c:
        api_app.app.state.graph = GrafoFalso()
        c.enviados = enviados
        yield c


def update(texto="hola", chat_id=42):
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, "text": texto}}


def test_secreto_incorrecto_da_403(cliente):
    r = cliente.post("/telegram", json=update(), headers={"X-Telegram-Bot-Api-Secret-Token": "otro"})
    assert r.status_code == 403 and cliente.enviados == []


def test_sin_secreto_da_403(cliente):
    assert cliente.post("/telegram", json=update()).status_code == 403


def test_responde_al_chat(cliente):
    r = cliente.post("/telegram", json=update("hola", 42), headers=HEADERS)
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert cliente.enviados == [(42, "eco: hola")]


def test_ignora_updates_sin_texto(cliente):
    sin_texto = {"update_id": 2, "message": {"chat": {"id": 42}, "sticker": {}}}
    assert cliente.post("/telegram", json=sin_texto, headers=HEADERS).status_code == 200
    assert cliente.post("/telegram", json={"update_id": 3}, headers=HEADERS).status_code == 200
    assert cliente.enviados == []
