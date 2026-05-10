"""
Step 2: Collapse trivial 2-cycles.

For each pair (a -> b: n,  b -> a: k):
  - if n >= k: replace both with single edge a -> b of weight n / k.
  - if n <  k: replace both with single edge b -> a of weight k / n.
"""
import json
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).parent
INPUT_GML = ROOT / "graph.gml"
OUTPUT = ROOT / "graph_no2cyc.gml"
OUTPUT_JSON = ROOT / "graph_no2cyc.json"


def main() -> None:
    G = nx.read_gml(INPUT_GML)
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes)

    seen = set()
    two_cycles = 0
    for u, v, data in G.edges(data=True):
        if (u, v) in seen:
            continue
        n = data["weight"]
        if G.has_edge(v, u):
            k = G[v][u]["weight"]
            if n >= k:
                H.add_edge(u, v, weight=n / k)
            else:
                H.add_edge(v, u, weight=k / n)
            seen.add((u, v))
            seen.add((v, u))
            two_cycles += 1
        else:
            H.add_edge(u, v, weight=float(n))
            seen.add((u, v))

    nx.write_gml(H, OUTPUT)
    OUTPUT_JSON.write_text(json.dumps({
        "nodes": sorted(H.nodes),
        "edges": [{"src": u, "dst": v, "weight": d["weight"]}
                  for u, v, d in H.edges(data=True)],
    }, indent=2))

    weights = [d["weight"] for _, _, d in H.edges(data=True)]
    print(f"2-cycles collapsed: {two_cycles}")
    print(f"Edges before: {G.number_of_edges()}  ->  after: {H.number_of_edges()}")
    print(f"Weight range:  [{min(weights):.3f}, {max(weights):.3f}]")
    print(f"Total weight:  {sum(weights):.3f}")
    print()
    print("Top 5 edges by weight after collapse:")
    top = sorted(H.edges(data=True), key=lambda e: -e[2]["weight"])[:5]
    for u, v, d in top:
        print(f"  {u.split('|')[-1]:35s} -> {v.split('|')[-1]:35s} : {d['weight']:.3f}")


if __name__ == "__main__":
    main()
