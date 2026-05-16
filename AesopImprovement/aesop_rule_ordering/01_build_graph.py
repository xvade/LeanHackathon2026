"""
Step 1: Build directed weighted graph from chosen/allowedUnsafeRules pairs.

Edge a --w--> b means: a was `chosen` while b appeared in `allowedUnsafeRules`,
in w distinct entries.  Self-edges (chosen == itself) are excluded.
"""
import json
from collections import defaultdict
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).parent
INPUT = ROOT.parent / "aesop_data_split" / "test_pairs.json"
OUTPUT = ROOT / "graph.gpickle"
OUTPUT_JSON = ROOT / "graph.json"


def main() -> None:
    pairs = json.loads(INPUT.read_text())

    G = nx.DiGraph()
    for p in pairs:
        chosen = p["chosen"]
        G.add_node(chosen)
        for other in p["allowedUnsafeRules"]:
            G.add_node(other)
            if other == chosen:
                continue
            if G.has_edge(chosen, other):
                G[chosen][other]["weight"] += 1
            else:
                G.add_edge(chosen, other, weight=1)

    nx.write_gml(G, OUTPUT.with_suffix(".gml"))
    OUTPUT_JSON.write_text(json.dumps({
        "nodes": sorted(G.nodes),
        "edges": [{"src": u, "dst": v, "weight": d["weight"]}
                  for u, v, d in G.edges(data=True)],
    }, indent=2))

    total_w = sum(d["weight"] for _, _, d in G.edges(data=True))
    chosen_set = {p["chosen"] for p in pairs}
    print(f"Pairs:               {len(pairs)}")
    print(f"Nodes:               {G.number_of_nodes()}")
    print(f"  ever chosen:       {len(chosen_set)}")
    print(f"  never chosen:      {G.number_of_nodes() - len(chosen_set)}")
    print(f"Edges:               {G.number_of_edges()}")
    print(f"Total edge weight:   {total_w}")
    print()
    print("Top 5 edges by weight:")
    top = sorted(G.edges(data=True), key=lambda e: -e[2]["weight"])[:5]
    for u, v, d in top:
        print(f"  {u.split('|')[-1]:35s} -> {v.split('|')[-1]:35s} : {d['weight']}")


if __name__ == "__main__":
    main()
