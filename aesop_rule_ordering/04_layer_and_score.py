"""
Step 4: Layer each weakly connected component and assign scores.

For each component:
  layer(v) = 0  if  v has no in-edges (within the component)
  layer(v) = 1 + max(layer(u) for u -> v)  otherwise.

Let N = number of distinct layers in the component.
Score(v) = (N - layer(v)) / (N + 1).
"""
import json
from collections import OrderedDict
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).parent
INPUT_GML = ROOT / "dag.gml"
OUTPUT = ROOT / "rule_scores.json"


def layers_for(component_subgraph: nx.DiGraph) -> dict:
    layer = {}
    for v in nx.topological_sort(component_subgraph):
        preds = list(component_subgraph.predecessors(v))
        layer[v] = 0 if not preds else max(layer[u] for u in preds) + 1
    return layer


def main() -> None:
    G = nx.read_gml(INPUT_GML)
    assert nx.is_directed_acyclic_graph(G)

    components = list(nx.weakly_connected_components(G))
    print(f"Weakly connected components: {len(components)}")

    scores: dict = {}
    component_info = []
    for i, comp in enumerate(components):
        sub = G.subgraph(comp).copy()
        layer = layers_for(sub)
        N = max(layer.values()) + 1
        for v, l in layer.items():
            scores[v] = (N - l) / (N + 1)
        component_info.append((i, len(comp), N, layer))
        print(f"  comp {i}: {len(comp)} nodes, {N} layer(s)")

    ordered = OrderedDict(sorted(scores.items(), key=lambda kv: -kv[1]))
    OUTPUT.write_text(json.dumps(ordered, indent=2, ensure_ascii=False))

    print()
    print(f"Wrote {len(scores)} rule scores to {OUTPUT}")
    print()
    print("Scores by layer (largest component shown in detail):")
    for i, size, N, layer in sorted(component_info, key=lambda c: -c[1]):
        print(f"\nComponent {i}: {size} nodes, {N} layers")
        by_layer: dict = {}
        for v, l in layer.items():
            by_layer.setdefault(l, []).append(v)
        for l in sorted(by_layer):
            score = (N - l) / (N + 1)
            print(f"  layer {l} (score {score:.4f}):")
            for v in sorted(by_layer[l]):
                print(f"    {v}")


if __name__ == "__main__":
    main()
