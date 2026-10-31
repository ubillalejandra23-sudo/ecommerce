import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from src.router.graph import build_graph

load_dotenv()

log = logging.getLogger("api")

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


@app.post("/telegram", tags=["telegram"], include_in_schema=False)
def telegram(update: dict[str, Any]) -> dict:
    return {"ok": True}
