import json
import uuid
from pathlib import Path

import pytest

from src.router.graph import graph

CASOS = json.loads((Path(__file__).parent / "casos_router.json").read_text(encoding="utf-8"))
MINIMO_ACIERTOS = 13  # el modelo no es determinista: no se exigen los 15

resultados: list[bool] = []


@pytest.mark.parametrize("caso", CASOS, ids=[c["mensaje"] for c in CASOS])
def test_ruta(caso):
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    estado = graph.invoke({"mensaje": caso["mensaje"]}, config)
    resultados.append(estado["ruta"] == caso["esperado"])


def test_umbral_de_aciertos():
    # Se ejecuta después de los casos parametrizados (orden de definición).
    assert len(resultados) == len(CASOS)
    assert sum(resultados) >= MINIMO_ACIERTOS, f"{sum(resultados)}/{len(CASOS)} aciertos"
