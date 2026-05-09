#!/usr/bin/env python3
"""
Deep Sets ranking model — toy overfit on grind split decisions.

Architecture:
  tokenize(pp_string) → bag-of-chars/words feature
  score(goal, cand)   = dot(W_goal, phi(goal)) + dot(W_cand, phi(cand))

This is the linear case of Deep Sets (phi = bag-of-tokens, rho = linear).
For a 1M-param production model, replace phi with a transformer encoder and
rho with an MLP, keeping the same interface: text in, scalar score out.

Training signal:
  - Each contested split decision gives: pool of K candidate PPs + chosenIdx.
  - Loss: cross-entropy over softmax(scores) with label = chosenIdx.
  - Trivially overfits on the toy dataset.

Outputs:
  model.json       — human-readable weights
  native/model.cpp — C++ inference (for compiled FFI deployment)
  server.py        — Python inference server (for production socket deployment)

Usage:
    cd DataCollection
    lake env lean Main.lean 2>/dev/null | grep '^{' > data.jsonl
    python3 ../NeuralTactic/scripts/train.py data.jsonl
"""

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ── Feature extraction ────────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Split on whitespace and punctuation into sub-word tokens."""
    return re.findall(r"[a-zA-Zα-ωΑ-Ω₀-₉]+|[!@#$%^&*()_+=\[\]{}|;:',.<>?/\\`~-]|\d+", text)


def build_vocab(records: list[dict]) -> list[str]:
    vocab: set[str] = set()
    for r in records:
        vocab.update(tokenize(r["goalPP"]))
        for d in r.get("splitDecisions", []):
            for c in d["pool"]:
                vocab.update(tokenize(c["pp"]))
    return sorted(vocab)


def bow(text: str, vocab: list[str]) -> list[float]:
    idx = {t: i for i, t in enumerate(vocab)}
    v = [0.0] * len(vocab)
    for t in tokenize(text):
        if t in idx:
            v[idx[t]] += 1.0
    return v


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def softmax(scores: list[float]) -> list[float]:
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


# ── Training ──────────────────────────────────────────────────────────────────

def main(data_path: str) -> None:
    records = [json.loads(l) for l in Path(data_path).read_text().splitlines() if l.strip()]
    print(f"Loaded {len(records)} record(s)")

    # Only train on contested decisions (pool size > 1)
    training = []
    for r in records:
        for d in r.get("splitDecisions", []):
            if len(d["pool"]) > 1:
                training.append((r["goalPP"], [c["pp"] for c in d["pool"]], d["chosenIdx"]))

    if not training:
        print("No contested split decisions — nothing to train on.")
        return

    print(f"Contested split decisions: {len(training)}")
    for goal, pool, chosen in training:
        print(f"  goal: {goal}")
        for i, pp in enumerate(pool):
            print(f"    [{i}{'*' if i == chosen else ' '}] {pp}")

    vocab = build_vocab(records)
    V = len(vocab)
    print(f"\nVocabulary size: {V} tokens")

    # Initialize weights
    w_goal = [0.0] * V
    w_cand = [0.0] * V
    lr = 0.5

    # Gradient descent to overfit
    for epoch in range(5000):
        total_loss = 0.0
        for goal_text, pool_texts, chosen in training:
            g_bow = bow(goal_text, vocab)
            pool_bows = [bow(p, vocab) for p in pool_texts]
            scores = [dot(w_goal, g_bow) + dot(w_cand, cb) for cb in pool_bows]
            probs = softmax(scores)
            total_loss -= math.log(max(probs[chosen], 1e-12))
            for i, (prob, cb) in enumerate(zip(probs, pool_bows)):
                grad = prob - (1.0 if i == chosen else 0.0)
                for j in range(V):
                    w_goal[j] -= lr * grad * g_bow[j]
                    w_cand[j] -= lr * grad * cb[j]
        if epoch % 1000 == 0:
            print(f"  epoch {epoch:5d}  loss={total_loss:.4f}")

    # Training accuracy
    correct = sum(
        1 for goal_text, pool_texts, chosen in training
        if [dot(w_goal, bow(goal_text, vocab)) + dot(w_cand, bow(p, vocab)) for p in pool_texts].index(
            max(dot(w_goal, bow(goal_text, vocab)) + dot(w_cand, bow(p, vocab)) for p in pool_texts)
        ) == chosen
    )
    print(f"Training accuracy: {correct}/{len(training)}")

    # Save human-readable weights
    model = {"vocab": vocab, "w_goal": w_goal, "w_cand": w_cand}
    (ROOT / "model.json").write_text(json.dumps(model, indent=2))
    print(f"\nWrote model.json")

    # Generate C++ inference (for compiled FFI; operates on text via vocab lookup)
    _generate_cpp(vocab, w_goal, w_cand)

    # Generate Python server (for production socket deployment)
    _generate_server(vocab, w_goal, w_cand)


# ── C++ generation ────────────────────────────────────────────────────────────

def _generate_cpp(vocab: list[str], w_goal: list[float], w_cand: list[float]) -> None:
    V = len(vocab)
    vocab_strs = ", ".join(f'"{v}"' for v in vocab)
    w_goal_vals = ", ".join(f"{x:.17e}" for x in w_goal)
    w_cand_vals = ", ".join(f"{x:.17e}" for x in w_cand)

    cpp = f"""\
// AUTO-GENERATED by scripts/train.py
// Deep Sets linear ranker: score(goal, cand) = dot(W_GOAL, bow(goal)) + dot(W_CAND, bow(cand))
// Operates on raw text (C-strings); no Lean serialization needed.
#include <lean/lean.h>
#include <cstring>
#include <cctype>
#include <string>
#include <sstream>
#include <vector>

static const int VOCAB_SIZE = {V};
static const char* VOCAB[{V}] = {{ {vocab_strs} }};
static const double W_GOAL[{V}] = {{ {w_goal_vals} }};
static const double W_CAND[{V}] = {{ {w_cand_vals} }};

static std::vector<std::string> tokenize(const char* text) {{
    std::vector<std::string> tokens;
    std::string tok;
    for (const char* p = text; *p; p++) {{
        if (std::isalpha((unsigned char)*p) || std::isdigit((unsigned char)*p)) {{
            tok += *p;
        }} else {{
            if (!tok.empty()) {{ tokens.push_back(tok); tok.clear(); }}
            if (!std::isspace((unsigned char)*p)) tokens.push_back(std::string(1, *p));
        }}
    }}
    if (!tok.empty()) tokens.push_back(tok);
    return tokens;
}}

static double bow_dot(const char* text, const double* weights) {{
    auto tokens = tokenize(text);
    double score = 0.0;
    for (int v = 0; v < VOCAB_SIZE; v++) {{
        double count = 0.0;
        for (auto& t : tokens) if (t == VOCAB[v]) count += 1.0;
        score += weights[v] * count;
    }}
    return score;
}}

// Lean FFI: goal_str and cand_str are Lean Strings.
// Returns the ranking score as a double.
LEAN_EXPORT double lean_neural_score(lean_object* goal_str, lean_object* cand_str) {{
    const char* goal = lean_string_cstr(goal_str);
    const char* cand = lean_string_cstr(cand_str);
    return bow_dot(goal, W_GOAL) + bow_dot(cand, W_CAND);
}}
"""
    out = ROOT / "native" / "model.cpp"
    out.parent.mkdir(exist_ok=True)
    out.write_text(cpp)
    print(f"Wrote {out}")


# ── Python server generation ──────────────────────────────────────────────────

def _generate_server(vocab: list[str], w_goal: list[float], w_cand: list[float]) -> None:
    server = f"""\
#!/usr/bin/env python3
\"\"\"
Inference server for the Deep Sets split ranker.
Listens on a Unix socket; the Lean FFI C stub connects to it.

Protocol (per request):
  Client sends: goal_pp\\ncand_pp\\n
  Server sends: <score as float64 little-endian 8 bytes>

Replace the scoring logic here with a real PyTorch model call
(load from model.pt, run forward pass, return score).

Usage:
    python3 server.py &
    # then start Lean with neural_grind
\"\"\"
import re
import struct
import socket
import os

SOCKET_PATH = "/tmp/neural_grind.sock"

VOCAB = {vocab!r}
W_GOAL = {w_goal!r}
W_CAND = {w_cand!r}

def tokenize(text):
    return re.findall(r"[a-zA-Z\\u03b1-\\u03c9\\u0391-\\u03a9]+|[!@#$%^&*()_+=\\[\\]{{}}|;:',.<>?/\\\\`~-]|\\d+", text)

def bow(text, vocab):
    idx = {{t: i for i, t in enumerate(vocab)}}
    v = [0.0] * len(vocab)
    for t in tokenize(text):
        if t in idx:
            v[idx[t]] += 1.0
    return v

def score(goal_pp, cand_pp):
    # TODO: replace with: return model(goal_pp, cand_pp).item()
    g = bow(goal_pp, VOCAB)
    c = bow(cand_pp, VOCAB)
    return sum(a * b for a, b in zip(W_GOAL, g)) + sum(a * b for a, b in zip(W_CAND, c))

if os.path.exists(SOCKET_PATH):
    os.unlink(SOCKET_PATH)

with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
    srv.bind(SOCKET_PATH)
    srv.listen(1)
    print(f"Listening on {{SOCKET_PATH}}")
    while True:
        conn, _ = srv.accept()
        with conn:
            data = b""
            while b"\\n\\n" not in data:
                data += conn.recv(4096)
            parts = data.decode().split("\\n")
            goal_pp, cand_pp = parts[0], parts[1]
            s = score(goal_pp, cand_pp)
            conn.sendall(struct.pack("<d", s))
"""
    out = ROOT / "scripts" / "server.py"
    out.write_text(server)
    print(f"Wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <data.jsonl>")
        sys.exit(1)
    main(sys.argv[1])
