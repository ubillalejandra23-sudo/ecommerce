import argparse
import importlib
import sys

from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("agente")
    p.add_argument("mensaje", nargs="?", default="")
    p.add_argument("--saltos", action="store_true", help="imprime los nodos por los que pasó el grafo")
    p.add_argument("--diagrama", action="store_true", help="imprime el Mermaid del grafo sin ejecutarlo")
    p.add_argument("--thread", default="cli", help="thread_id para la memoria")
    args = p.parse_args()

    graph = importlib.import_module(f"src.{args.agente}.graph").graph

    if args.diagrama:
        print(graph.get_graph().draw_mermaid())
        return

    config = {"configurable": {"thread_id": args.thread}}
    saltos = []
    for update in graph.stream({"mensaje": args.mensaje}, config, stream_mode="updates"):
        saltos.extend(update.keys())

    estado = graph.get_state(config).values
    if args.saltos:
        print(" → ".join(saltos))
    print(f"ruta: {estado.get('ruta')}")
    print(f"motivo: {estado.get('motivo')}")
    print(f"respuesta: {estado.get('respuesta')}")


if __name__ == "__main__":
    main()
