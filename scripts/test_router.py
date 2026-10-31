import json
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8")

from src.router.graph import graph  # noqa: E402


def main():
    casos = json.loads((RAIZ / "tests" / "casos_router.json").read_text(encoding="utf-8"))
    filas, fallados = [], []
    for caso in casos:
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        estado = graph.invoke({"mensaje": caso["mensaje"]}, config)
        ok = estado["ruta"] == caso["esperado"]
        filas.append((caso["mensaje"], caso["esperado"], estado["ruta"], "✔" if ok else "✘", estado["motivo"]))
        if not ok:
            fallados.append(filas[-1])

    print(f"{'MENSAJE':<58} {'ESPERADO':<10} {'OBTENIDO':<10} OK  MOTIVO")
    for m, e, o, s, mot in filas:
        print(f"{m[:56]:<58} {e:<10} {o:<10} {s}   {mot}")

    total, aciertos = len(filas), len(filas) - len(fallados)
    print(f"\nAciertos: {aciertos}/{total} ({aciertos / total:.0%})")
    if fallados:
        print("Fallados:")
        for m, e, o, _, mot in fallados:
            print(f"  - {m!r}: esperado {e}, obtenido {o} ({mot})")


if __name__ == "__main__":
    main()
