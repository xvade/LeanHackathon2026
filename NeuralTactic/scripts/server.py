#!/usr/bin/env python3
"""
Inference server for the Deep Sets split ranker.
Listens on a Unix socket; the Lean FFI C stub connects to it.

Protocol (per request):
  Client sends: goal_pp\ncand_pp\n
  Server sends: <score as float64 little-endian 8 bytes>

Replace the scoring logic here with a real PyTorch model call
(load from model.pt, run forward pass, return score).

Usage:
    python3 server.py &
    # then start Lean with neural_grind
"""
import re
import struct
import socket
import os

SOCKET_PATH = "/tmp/neural_grind.sock"

VOCAB = ['!', '&', '(', ')', '=', 'a', 'b', 'c', 'else', 'false', 'if', 'p', 'q', 'then', 'true', '|']
W_GOAL = [-4.007753330592667e-16, -1.3554499048770013e-14, -1.4676844808936274e-14, -1.4676844808936274e-14, -1.209107683766697e-14, -1.4676844808936274e-14, -1.4676844808936274e-14, 4.900756449960353e-15, -4.730374078554256e-15, -6.777249524385007e-15, -4.730374078554256e-15, 0.0, 0.0, -4.730374078554256e-15, -7.797148343646754e-15, -5.964595950393864e-15]
W_CAND = [5.10883874520873, 0.0, 1.5038260264921832, 1.5038260264921832, -4.806683624955372, -1.2016709062388649, -1.2016709062388649, 2.4503782249801764e-15, -7.338422404468137e-15, -2.4033418124777115, -7.338422404468137e-15, 0.0, 0.0, -7.338422404468137e-15, -1.2016709062388635, 0.0]

def tokenize(text):
    return re.findall(r"[a-zA-Z\u03b1-\u03c9\u0391-\u03a9]+|[!@#$%^&*()_+=\[\]{}|;:',.<>?/\\`~-]|\d+", text)

def bow(text, vocab):
    idx = {t: i for i, t in enumerate(vocab)}
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
    print(f"Listening on {SOCKET_PATH}")
    while True:
        conn, _ = srv.accept()
        with conn:
            data = b""
            while b"\n\n" not in data:
                data += conn.recv(4096)
            parts = data.decode().split("\n")
            goal_pp, cand_pp = parts[0], parts[1]
            s = score(goal_pp, cand_pp)
            conn.sendall(struct.pack("<d", s))
