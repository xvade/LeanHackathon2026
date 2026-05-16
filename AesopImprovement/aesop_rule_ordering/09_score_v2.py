"""
Step 9 (alternative scoring): break within-layer ties by total input weight.

Layers are computed exactly as in step 4.  Within a layer, nodes are sorted
by *ascending* total input weight (the sum of weights of edges that have
the node as destination).  A node with a lower input weight has been "beaten"
less often, so we assign it a higher score.

Score formula:
  base(L)  = (N - L) / (N + 1)                    # same as v1
  span     = 0.5 / (N + 1)                        # half the gap to next layer
  rank(v)  = position in ascending-input-weight order within the layer
             (0 = lowest input weight = best)
  score(v) = base(L) - (rank / (K - 1)) * span    # K = layer size

Properties:
  - Singleton layers keep the v1 score exactly.
  - The worst node in layer L scores  base(L) - span = (N - L - 0.5)/(N + 1),
    still strictly above the best of layer L + 1, which scores (N - L - 1)/(N + 1).
  - For an entire layer of size 1 (or all-tied input weights), v1 and v2
    coincide.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).parent


def short(name: str) -> str:
    return name.split("|")[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dag", default=str(ROOT / "dag.gml"))
    ap.add_argument("--out", default=str(ROOT / "rule_scores_v2.json"))
    args = ap.parse_args()

    G = nx.read_gml(args.dag)

    # Layers
    layer = {}
    for v in nx.topological_sort(G):
        preds = list(G.predecessors(v))
        layer[v] = 0 if not preds else max(layer[u] for u in preds) + 1
    N = max(layer.values()) + 1

    # Input weight per node
    input_weight = {
        v: sum(d["weight"] for _, _, d in G.in_edges(v, data=True))
        for v in G.nodes
    }

    by_layer = defaultdict(list)
    for v, l in layer.items():
        by_layer[l].append(v)

    scores = {}
    span = 0.5 / (N + 1)
    for l, nodes in by_layer.items():
        nodes_sorted = sorted(nodes, key=lambda v: (input_weight[v], v))
        K = len(nodes_sorted)
        base = (N - l) / (N + 1)
        for rank, v in enumerate(nodes_sorted):
            shift = (rank / (K - 1)) * span if K > 1 else 0.0
            scores[v] = base - shift

    ordered = dict(sorted(scores.items(), key=lambda kv: -kv[1]))
    Path(args.out).write_text(json.dumps(ordered, indent=2))
    print(f"Layers: {N}, span within layer: {span:.4f}")
    print(f"Wrote {args.out}\n")
    for l in sorted(by_layer):
        nodes_sorted = sorted(by_layer[l], key=lambda v: (input_weight[v], v))
        base = (N - l) / (N + 1)
        worst_in_layer = base - (span if len(nodes_sorted) > 1 else 0.0)
        print(f"Layer {l}  (size {len(nodes_sorted)}, "
              f"score range {worst_in_layer:.4f} … {base:.4f}):")
        for v in nodes_sorted:
            print(f"  in_weight={input_weight[v]:6.2f}  "
                  f"score={scores[v]:.4f}  {short(v)}")
        print()


if __name__ == "__main__":
    main()
