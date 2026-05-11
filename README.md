# LeanHackathon 2026: Neural Grind

This branch focuses on enhancing Lean 4's `grind` tactic through
neural-guided split ordering, trace extraction, and efficiency-aware training.

## Device Setup

This device already has a usable conda environment for neural-grind training
and export:

```bash
conda activate lean-ml
python -c 'import torch; print(torch.__version__, torch.cuda.is_available())'
```

For scripts that accept an explicit Python executable, use:

```bash
PYTHON=/home/aurasl/miniconda3/envs/lean-ml/bin/python
```

The AXLE-backed collection helpers require the optional `axle` package and
credentials in `training/.env`; the core neural-grind training/export path only
requires PyTorch.

## Using the Improved Tactic

### `neural_grind`

The `neural_grind` tactic replaces `grind`'s native split-candidate heuristic
with a lightweight MLP model that ranks branching options by predicted proof
efficiency.

**Import:**

```lean
import NeuralTactic
```

**Usage:**

```lean
example (h : P ∨ Q) (hp : P → R) (hq : Q → R) : R := by
  neural_grind
```

**Native inference path:**

```bash
c++ -DNEURAL_GRIND_STANDALONE -O3 -std=c++17 \
  NeuralTactic/native/model.cpp \
  -o training/experiments/exp09_heuristics/native_serve

GRIND_MODEL=training/experiments/exp09_heuristics/model.native.bin \
GRIND_SERVE=training/experiments/exp09_heuristics/native_serve \
GRIND_SERVE_NATIVE=1 \
lake env lean path/to/file.lean
```

**Python inference path:**

```bash
GRIND_MODEL=training/experiments/exp09_heuristics/model.pt \
GRIND_SERVE=training/experiments/exp09_heuristics/serve.py \
GRIND_PYTHON=/home/aurasl/miniconda3/envs/lean-ml/bin/python \
lake env lean path/to/file.lean
```

**Key environment variables:**

| Variable | Effect |
|---|---|
| `GRIND_MODEL` | Path to a PyTorch `.pt` checkpoint or native `.native.bin` weights |
| `GRIND_SERVE` | Path to `serve.py` or a native inference executable |
| `GRIND_SERVE_NATIVE` | Set to `1` when `GRIND_SERVE` is the native executable |
| `GRIND_PYTHON` | Python executable for Python server mode |
| `GRIND_NO_MODEL` | Set to `1` to disable the model and use stock `grind` split selection |
| `GRIND_MARGIN_MILLI` | Minimum logit margin, in milli-logits, required to trust the model |
| `GRIND_DECISION_LOG` | Optional JSONL file for per-decision diagnostics |

If the server is unavailable, the model returns no usable choice, or
`GRIND_NO_MODEL=1`, `neural_grind` falls back to `grind`'s native split
selection. The model changes split ordering only; it does not add axioms or
change Lean's kernel checking.

## Validation

Run the branch smoke check from the repo root:

```bash
PYTHON=/home/aurasl/miniconda3/envs/lean-ml/bin/python \
  training/smoke_neural_grind.sh
```

The smoke check trains a tiny model on a synthetic branching split, exports the
native weights, verifies the native server chooses the trained branch, and then
runs `neural_grind` on a small Lean theorem while checking that the model path
was exercised.

## Extraction

### Data Extraction
Our data collection process followed two primary strategies to capture a diverse range of mathematical contexts and theorem styles.

**Mathlib Data Collection:**
We collected data from Mathlib by systematically extracting theorems and their environmental contexts. This was achieved by parsing import statements, namespaces, and open statements to reconstruct the precise mathematical state. We utilized a custom tactic to execute `grind` across these theorems, extracting the goal states and proof traces to build a comprehensive map of successful automated proofs.

**External Dataset Integration:**
The second strategy involved leveraging several large-scale Lean datasets, collectively providing a vast search space for theorem automation:
- **NuminaMath Lean**: 104,155 competition-style theorems.
- **Lean Workbook**: 57,231 formal statements.
- **Herald**: 580,000 NL-FL statement pairs.
- **FineLeanCorpus**: 509,358 formalization entries.
- **LeanDojo-v2**: 120,000 statements

These datasets provide a vast collection of theorem statements that typically do not yet have accompanying proofs. From this pool, verified `grind` successes can be converted into split-decision traces for training.

This collection forms the core of our training data, representing a diverse "Winning Spine" for `grind` across different domains.


**Verification and Filtering:**
For `grind`, we tested each theorem to see if the tactic could autonomously close the goal. Successful cases were added to a JSONL dataset for training. This verification process was facilitated by **AXLE by axiom.ai**.

### Grind Trace Extraction
We instrumented the `grind` tactic to capture the internal state and decision-making process at every "split" (branching point) during proof search. This instrumentation allows us to record the precisely timed "snapshots" of the prover's state.

**The Trace Data:**
For every successful proof, we extract a JSON trace containing:
- **Goal Features**: Numerical summaries such as `assertedCount` (total known facts), `ematchRounds`, and `splitDepth`.
- **Candidate Pool**: The full set of available branching options (e.g., case splits on an `if-then-else` or an implication), including their origins (`ematch`, `ext`, `input`, etc.).
- **Environmental Context**: A "Pretty-Printed" version of the local context and the internal state of the E-graph (the robot's "brain").
- **Winning Spine**: We prune these traces to retain only the "Winning Spine"—the sequence of successful decisions that directly led to the proof, discarding any exploratory dead ends.

## Training

### Grind Training
To leverage the extracted trace data, we trained a lightweight neural model designed to predict the optimal next step in a `grind` proof search.

**Model Architecture:**
- **Type**: A 3-layer Multi-Layer Perceptron (MLP).
- **Size**: ~74,500 parameters
- **Input**: A 32-dimensional feature vector encoding the goal state, the specific candidate branch, and its relationship to the rest of the candidate pool.
- **Inference**: Optimized for speed, the model runs in a native C++ server with an inference time of **< 1ms**, enabling its use directly within the Lean tactic loop.

**Training Strategy:**
- **Objective**: The model is trained using Cross-Entropy Loss to maximize the score of the "Winning Spine" candidate within its original pool of alternatives.
- **Efficiency Weighting**: We apply a weighting formula ($W = 1 / \sqrt{\text{total\_splits}}$) to the training loss. This incentivizes the model to prioritize decisions from shorter, more efficient proofs, effectively learning "shortcuts" over the native heuristic's often exhaustive search.
- **Evaluation**: We maintain a stable benchmark of 75 problems (balanced across Mathlib, Workbook, and Numina) that are strictly excluded from the training set to measure the model's generalization and split-reduction capabilities.


## Project Note
This project serves as a focused investigation into the scaling potential of neural-guided proof search. Our primary interest was in projecting what the results would look like in the "actual end"—leveraging the full scale of the 53,000+ theorem dataset to move toward a highly efficient, zero-exploration automated prover.
