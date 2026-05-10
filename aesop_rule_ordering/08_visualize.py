"""
Step 8: Render the rule-dominance DAG produced by the pipeline.

Layout:
  - Nodes positioned by their assigned layer (top = layer 0 = best score).
  - Within a layer, nodes are placed by their average y of out-neighbours
    (helps reduce edge crossings).
  - Node colour = score (viridis), node size constant for readability.
  - Edge width log-proportional to weight; arrowed to indicate direction.
  - Short labels: just the trailing declaration name (after the final "|").
"""
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
import numpy as np

ROOT = Path(__file__).parent
DAG_GML = ROOT / "dag.gml"
SCORES = ROOT / "rule_scores.json"
OUT_PNG = ROOT / "rule_dag.png"
OUT_SVG = ROOT / "rule_dag.svg"


def short(name: str) -> str:
    decl = name.split("|")[-1]
    decl = decl.removeprefix("Aesop.BuiltinRules.")
    decl = decl.removeprefix("Aesop.BuiltinRule.")
    return decl


def main() -> None:
    G = nx.read_gml(DAG_GML)
    scores = json.loads(SCORES.read_text())

    # Recover layers: layer = max-predecessor + 1, source = 0.
    layer = {}
    for v in nx.topological_sort(G):
        preds = list(G.predecessors(v))
        layer[v] = 0 if not preds else max(layer[u] for u in preds) + 1
    N_layers = max(layer.values()) + 1
    print(f"Nodes: {G.number_of_nodes()}, edges: {G.number_of_edges()}, layers: {N_layers}")

    # Group nodes by layer
    by_layer = defaultdict(list)
    for v, l in layer.items():
        by_layer[l].append(v)

    # Order each layer to keep heavier-incoming nodes near their sources.
    # Heuristic: sort each layer by out-degree (within the DAG) descending,
    # tie-break by name for determinism.  Keeps applyHyps & friends central.
    for l in by_layer:
        by_layer[l].sort(key=lambda v: (-G.out_degree(v), v))

    # Assign positions: x in [-1, 1] spread across layer width, y from layer.
    pos = {}
    for l, nodes in by_layer.items():
        n = len(nodes)
        if n == 1:
            xs = [0.0]
        else:
            xs = np.linspace(-1.0, 1.0, n)
        for x, v in zip(xs, nodes):
            pos[v] = (x, -l)  # y = -layer so that layer 0 is at top

    # ----- draw -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(20, 11))
    ax.set_facecolor("#fafafa")

    # Color nodes by score
    score_vals = np.array([scores[v] for v in G.nodes])
    cmap = plt.cm.viridis
    norm = plt.Normalize(vmin=score_vals.min(), vmax=score_vals.max())

    # Edges with log-scaled width
    weights = np.array([d["weight"] for _, _, d in G.edges(data=True)], dtype=float)
    widths = 0.4 + 2.5 * np.log1p(weights) / np.log1p(weights.max())

    # Draw edges first (light grey)
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color="#888888",
        alpha=0.55,
        width=widths,
        arrows=True,
        arrowsize=12,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.06",
        node_size=1500,
    )

    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=score_vals,
        cmap=cmap,
        vmin=norm.vmin, vmax=norm.vmax,
        node_size=1500,
        edgecolors="black",
        linewidths=0.8,
    )

    # Labels
    labels = {v: short(v) for v in G.nodes}
    nx.draw_networkx_labels(
        G, pos, ax=ax, labels=labels,
        font_size=7.4,
        font_color="black",
    )

    # Layer band annotations on the left
    layer_scores = {l: (N_layers - l) / (N_layers + 1) for l in range(N_layers)}
    for l in range(N_layers):
        ax.text(-1.18, -l, f"layer {l}\nscore {layer_scores[l]:.4f}",
                fontsize=10, ha="right", va="center",
                color="#333333", weight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#cccccc"))

    # Colour bar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.025, pad=0.01)
    cbar.set_label("score = (N − layer) / (N + 1)", rotation=270, labelpad=18)

    # Title and meta
    ax.set_title(
        f"Rule-dominance DAG used by aesop_with_overrides\n"
        f"{G.number_of_nodes()} rules, {G.number_of_edges()} edges, "
        f"{N_layers} layers — derived from {len(json.loads((ROOT.parent / 'aesop_data_split' / 'test_pairs.json').read_text()))} test pairs",
        fontsize=13, pad=14,
    )
    ax.set_axis_off()

    # Edge legend
    handles = [
        mpatches.Patch(color="#888888", label=f"edge a→b: a was chosen while b was an unsafe alternative"),
        mpatches.Patch(color="white", ec="black", label="node colour = score (yellow = best, purple = worst)"),
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.03),
              fontsize=9, frameon=False, ncol=2)

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=160, bbox_inches="tight")
    plt.savefig(OUT_SVG, bbox_inches="tight")
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_SVG}")


if __name__ == "__main__":
    main()
