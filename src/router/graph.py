import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from src.router import prompts

load_dotenv()


class Decision(BaseModel):
    ruta: Literal["preventa", "postventa", "generica"] = Field(description="A qué agente va el mensaje.")
    motivo: str = Field(description="Una frase: por qué esa ruta.")


class Estado(TypedDict, total=False):
    mensaje: str
    ruta: str
    motivo: str
    respuesta: str
    messages: Annotated[list, add_messages]


def router(state: Estado) -> dict:
    llm = ChatAnthropic(model=os.getenv("MODELO")).with_structured_output(Decision)
    nuevo = HumanMessage(state["mensaje"])
    decision = llm.invoke([SystemMessage(prompts.PROMPT_ROUTER), *state.get("messages", []), nuevo])
    return {"ruta": decision.ruta, "motivo": decision.motivo, "messages": [nuevo]}


def _responder(texto: str) -> dict:
    return {"respuesta": texto, "messages": [AIMessage(texto)]}


def agente_preventa(state: Estado) -> dict:
    return _responder(prompts.PROMPT_PREVENTA.format(mensaje=state["mensaje"]))


def agente_postventa(state: Estado) -> dict:
    return _responder(prompts.PROMPT_POSTVENTA.format(mensaje=state["mensaje"]))


def respuesta_generica(state: Estado) -> dict:
    return _responder(prompts.PROMPT_GENERICA)


def elegir_nodo(state: Estado) -> str:
    return {
        "preventa": "agente_preventa",
        "postventa": "agente_postventa",
        "generica": "respuesta_generica",
    }[state["ruta"]]


def build_graph():
    g = StateGraph(Estado)
    g.add_node("router", router)
    g.add_node("agente_preventa", agente_preventa)
    g.add_node("agente_postventa", agente_postventa)
    g.add_node("respuesta_generica", respuesta_generica)
    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router", elegir_nodo,
        ["agente_preventa", "agente_postventa", "respuesta_generica"],
    )
    for nodo in ("agente_preventa", "agente_postventa", "respuesta_generica"):
        g.add_edge(nodo, END)
    return g.compile(checkpointer=MemorySaver())


graph = build_graph()
