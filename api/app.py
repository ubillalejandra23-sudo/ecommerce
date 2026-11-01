import hmac
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from src.router.graph import build_graph

load_dotenv()

log = logging.getLogger("api")
# httpx registra la URL de cada request y la de Telegram lleva el token del bot.
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_API = "https://api.telegram.org"
MENSAJE_ERROR = "Tuve un problema para procesar tu mensaje. Intenta de nuevo en un momento."

DESCRIPCION = """
Router de un chat de ecommerce: lee el mensaje del cliente, decide a qué agente corresponde y devuelve la ruta
elegida, el motivo y la respuesta. La memoria de la conversación se guarda por `user_id`.

**Rutas posibles**

- `preventa`: intención de compra, productos, precios, tallas, stock, promociones y formas de pago antes de comprar.
- `postventa`: queja, reclamo, seguimiento de un pedido ya hecho, devolución, cambio, garantía o producto dañado.
- `generica`: cualquier cosa fuera del ecommerce (clima, chistes, preguntas generales) o saludos sin pedido.
"""

TAGS = [
    {"name": "salud", "description": "Estado del servicio."},
    {"name": "chat", "description": "Conversación con el router."},
    {"name": "telegram", "description": "Webhook de Telegram."},
]


class ChatRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        description="Identificador del usuario; se usa como thread_id para la memoria de la conversación.",
        examples=["cliente-123"],
    )
    texto: str = Field(
        min_length=1,
        description="Mensaje del cliente.",
        examples=["mi pedido 4521 llegó roto"],
    )


class ChatResponse(BaseModel):
    ruta: Literal["preventa", "postventa", "generica"] = Field(
        description="Agente al que el router envió el mensaje.", examples=["postventa"]
    )
    motivo: str = Field(
        description="Una frase: por qué el router eligió esa ruta.",
        examples=["El cliente reporta que un pedido ya realizado llegó dañado."],
    )
    respuesta: str = Field(
        description="Respuesta del agente elegido.",
        examples=["Soy el agente de postventa. Recibí: mi pedido 4521 llegó roto. Pronto podré ayudarte con tu pedido."],
    )


class Error(BaseModel):
    detail: str = Field(description="Descripción del error.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.graph = build_graph()  # se compila una sola vez, al arrancar
    yield


app = FastAPI(
    title="Ecommerce Router API",
    version="0.1.0",
    description=DESCRIPCION,
    openapi_tags=TAGS,
    lifespan=lifespan,
)


@app.get("/health", tags=["salud"], summary="Estado del servicio")
def health() -> dict:
    return {"ok": True, "modelo": os.getenv("MODELO")}


@app.post(
    "/chat",
    tags=["chat"],
    summary="Enviar un mensaje al router",
    response_model=ChatResponse,
    responses={
        200: {"description": "Mensaje enrutado: ruta elegida, motivo y respuesta del agente."},
        422: {"description": "Body inválido: falta `user_id` o `texto`, o están vacíos."},
        502: {"model": Error, "description": "El modelo de lenguaje falló o no está disponible."},
    },
)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    config = {"configurable": {"thread_id": body.user_id}}
    try:
        estado = request.app.state.graph.invoke({"mensaje": body.texto}, config)
    except Exception:
        error_id = uuid.uuid4().hex[:8]
        log.exception("Falló el grafo router (error_id=%s, user_id=%s)", error_id, body.user_id)
        raise HTTPException(
            status_code=502,
            detail=f"El modelo no pudo procesar el mensaje. Intenta de nuevo en un momento. (ref: {error_id})",
        )
    return ChatResponse(ruta=estado["ruta"], motivo=estado["motivo"], respuesta=estado["respuesta"])


def enviar_mensaje(chat_id: int, texto: str) -> None:
    """Envía un mensaje por Telegram. Nunca registra la URL: contiene el token."""
    try:
        r = httpx.post(
            f"{TELEGRAM_API}/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
            json={"chat_id": chat_id, "text": texto},
            timeout=15,
        )
        if r.is_error:
            log.error("Telegram rechazó sendMessage (status=%s, chat_id=%s)", r.status_code, chat_id)
    except httpx.HTTPError as e:
        log.error("No se pudo llamar a Telegram (%s, chat_id=%s)", type(e).__name__, chat_id)


def responder_telegram(graph, chat_id: int, texto: str) -> None:
    config = {"configurable": {"thread_id": str(chat_id)}}
    try:
        estado = graph.invoke({"mensaje": texto}, config)
        log.info("telegram chat_id=%s ruta=%s motivo=%s", chat_id, estado["ruta"], estado["motivo"])
        respuesta = estado["respuesta"]
    except Exception:
        log.exception("Falló el grafo router (telegram, chat_id=%s)", chat_id)
        respuesta = MENSAJE_ERROR
    enviar_mensaje(chat_id, respuesta)


@app.post("/telegram", tags=["telegram"], include_in_schema=False)
def telegram(
    update: dict[str, Any],
    background: BackgroundTasks,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    secreto = os.getenv("TELEGRAM_SECRET") or ""
    if not secreto or not hmac.compare_digest(x_telegram_bot_api_secret_token or "", secreto):
        raise HTTPException(status_code=403, detail="Forbidden")

    mensaje = update.get("message") or {}
    texto = mensaje.get("text")
    chat_id = (mensaje.get("chat") or {}).get("id")
    if texto and chat_id is not None:
        # El modelo puede tardar: se responde 200 a Telegram y se contesta al usuario después.
        background.add_task(responder_telegram, request.app.state.graph, chat_id, texto)
    return {"ok": True}
