"""
Step 3: Remove remaining cycles to obtain a DAG.

Strategy:
  - Find SCCs.  Every singleton SCC is already acyclic.
  - For each non-trivial SCC, solve the minimum-weight feedback arc set
    via an ILP linear-ordering formulation:
        binary  p[u, v]  for ordered pair (u, v):  p[u, v] = 1 iff u precedes v
        anti-symmetry:    p[u, v] + p[v, u] = 1
        transitivity:     p[u, v] + p[v, w] + p[w, u] <= 2
        objective:        minimize sum w(u, v) * p[v, u]   (backward edges removed)
    With  S = |SCC|, the ILP has  S * (S - 1)  variables and  O(S^3)
    transitivity constraints.  We cap the SCC size at 25 nodes; anything
    larger falls back to the Eades-Lin-Smyth heuristic.
"""
import json
import time
from itertools import permutations
from pathlib import Path

import networkx as nx
import pulp

ROOT = Path(__file__).parent
INPUT_GML = ROOT / "graph_no2cyc.gml"
OUTPUT = ROOT / "dag.gml"
OUTPUT_JSON = ROOT / "dag.json"

ILP_SIZE_CAP = 25
ILP_TIME_LIMIT = 300  # seconds


def ilp_min_fas(scc_nodes, edges):
    """Return list of edges to remove for minimum-weight FAS on this SCC."""
    nodes = list(scc_nodes)
    n = len(nodes)
    prob = pulp.LpProblem("min_fas", pulp.LpMinimize)
    p = {(u, v): pulp.LpVariable(f"p_{i}_{j}", cat="Binary")
         for i, u in enumerate(nodes) for j, v in enumerate(nodes) if u != v}

    # Antisymmetry
    for i, u in enumerate(nodes):
        for v in nodes[i + 1:]:
            prob += p[u, v] + p[v, u] == 1

    # Transitivity (no 3-cycles in the order)
    for u, v, w in permutations(nodes, 3):
        prob += p[u, v] + p[v, w] + p[w, u] <= 2

    # Objective: minimise weight of backward edges.  Edge u -> v is "backward"
    # when v precedes u in the ordering, i.e. p[v, u] = 1.
    prob += pulp.lpSum(w * p[v, u] for (u, v), w in edges.items())

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=ILP_TIME_LIMIT)
    status = prob.solve(solver)
    if pulp.LpStatus[status] not in ("Optimal", "Not Solved"):
        raise RuntimeError(f"ILP status: {pulp.LpStatus[status]}")

    removed = [(u, v) for (u, v) in edges if pulp.value(p[v, u]) > 0.5]
    return removed


def els_min_fas(scc_nodes, edges):
    """Eades-Lin-Smyth weighted heuristic.  O(V + E)."""
    remaining = set(scc_nodes)
    sub = {(u, v): w for (u, v), w in edges.items()
           if u in remaining and v in remaining}
    out_adj = {v: set() for v in remaining}
    in_adj = {v: set() for v in remaining}
    for u, v in sub:
        out_adj[u].add(v)
        in_adj[v].add(u)

    s1, s2 = [], []
    while remaining:
        progress = True
        while progress:
            progress = False
            for v in list(remaining):
                if not (out_adj[v] & remaining):
                    s2.append(v)
                    remaining.remove(v)
                    progress = True
                elif not (in_adj[v] & remaining):
                    s1.append(v)
                    remaining.remove(v)
                    progress = True
        if not remaining:
            break
        best = max(remaining, key=lambda v:
                   sum(sub[(v, w)] for w in out_adj[v] & remaining)
                   - sum(sub[(w, v)] for w in in_adj[v] & remaining))
        s1.append(best)
        remaining.remove(best)

    order = s1 + list(reversed(s2))
    pos = {v: i for i, v in enumerate(order)}
    return [(u, v) for (u, v) in sub if pos[u] > pos[v]]


def main() -> None:
    G = nx.read_gml(INPUT_GML)
    edges = {(u, v): d["weight"] for u, v, d in G.edges(data=True)}

    sccs = [c for c in nx.strongly_connected_components(G) if len(c) > 1]
    print(f"Non-trivial SCCs: {len(sccs)}")
    for i, c in enumerate(sccs):
        in_scc = {(u, v): w for (u, v), w in edges.items() if u in c and v in c}
        print(f"  SCC {i}: {len(c)} nodes, {len(in_scc)} internal edges, "
              f"weight {sum(in_scc.values()):.3f}")

    removed_all = []
    for scc in sccs:
        sub_edges = {(u, v): w for (u, v), w in edges.items()
                     if u in scc and v in scc}
        if len(scc) <= ILP_SIZE_CAP:
            print(f"  Solving SCC of size {len(scc)} via ILP…")
            t0 = time.monotonic()
            removed = ilp_min_fas(scc, sub_edges)
            print(f"    ILP done in {time.monotonic() - t0:.2f}s, removed {len(removed)} edges")
        else:
            print(f"  SCC of size {len(scc)} too big for ILP, using ELS heuristic")
            removed = els_min_fas(scc, sub_edges)
        removed_all.extend(removed)

    H = nx.DiGraph()
    H.add_nodes_from(G.nodes)
    removed_set = set(removed_all)
    for u, v, d in G.edges(data=True):
        if (u, v) not in removed_set:
            H.add_edge(u, v, weight=d["weight"])

    assert nx.is_directed_acyclic_graph(H), "Result still has cycles!"

    nx.write_gml(H, OUTPUT)
    OUTPUT_JSON.write_text(json.dumps({
        "nodes": sorted(H.nodes),
        "edges": [{"src": u, "dst": v, "weight": d["weight"]}
                  for u, v, d in H.edges(data=True)],
        "removed": [{"src": u, "dst": v, "weight": edges[(u, v)]}
                    for (u, v) in removed_all],
    }, indent=2))

    removed_w = sum(edges[(u, v)] for (u, v) in removed_all)
    print()
    print(f"Edges removed: {len(removed_all)}  (total weight {removed_w:.3f})")
    print(f"Edges kept:    {H.number_of_edges()}")
    print(f"Result is a DAG: {nx.is_directed_acyclic_graph(H)}")
    if removed_all:
        print()
        print("Removed edges:")
        for (u, v) in removed_all:
            print(f"  {u.split('|')[-1]:35s} -> {v.split('|')[-1]:35s} : {edges[(u, v)]:.3f}")


if __name__ == "__main__":
    main()
