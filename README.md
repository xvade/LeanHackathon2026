# LeanHackathon 2026: Neural Automated Proof Search

This project focuses on enhancing Lean 4's automated tactics, specifically `grind` and `aesop`, through neural-guided proof search and efficiency-aware data collection.

## Using the Improved Tactics

### Improved `grind` — `neural_grind`

The `neural_grind` tactic replaces grind's native split-candidate heuristic with a lightweight MLP model (~1,00,000 parameters, <1ms inference) that ranks branching options by predicted proof efficiency.

**Import:**
```lean
import NeuralTactic
```

**Usage:**
```lean
example (h : P ∨ Q) (hp : P → R) (hq : Q → R) : R := by
  neural_grind
```

**Starting the inference server** (required once per session):

Native binary (fastest):
```bash
GRIND_NATIVE_WEIGHTS=training/experiments/exp09_heuristics/model.native.bin \
  ./NeuralTactic/native_serve
```

Or via Python:
```bash
python3 training/serve.py --model training/experiments/exp09_heuristics/model.pt
```

**Key environment variables** (all optional):

| Variable | Effect |
|---|---|
| `GRIND_NATIVE_WEIGHTS` | Path to `.native.bin` weights for the C++ server |
| `GRIND_MODEL` | Path to PyTorch `.pt` checkpoint (Python server) |
| `GRIND_SERVE` | Path to `serve.py` or native executable |
| `GRIND_SERVE_NATIVE` | Set to `1` when `GRIND_SERVE` is the native binary |
| `GRIND_NO_MODEL` | Set to `1` to disable model and use stock grind heuristic |
| `GRIND_MARGIN_MILLI` | Minimum logit margin (milli-logits) required to trust model ranking |
| `GRIND_DECISION_LOG` | Path to a JSONL file for per-decision diagnostic output |

If the server is unavailable or `GRIND_NO_MODEL=1`, `neural_grind` silently falls back to grind's native heuristic. Proofs that close with stock `grind` will also close with `neural_grind`; the model only changes split ordering, not soundness. To use stock `grind`, simply call `grind` as usual — the two tactics are independent.

---

### Improved `aesop` — `aesop_with_overrides`

`aesop_with_overrides` runs standard aesop but reassigns the success probabilities of unsafe rules before the search begins. The probabilities come from a graph-based topological scoring of ~53,000 empirical rule-application traces: rules that tended to be chosen earlier in successful proofs receive higher scores, so aesop tries them first.

**Import:**
```lean
import AesopWithOverrides
```

**Usage:**
```lean
example (s t : Finset α) (h : s ⊆ t) : s ∩ t = s := by
  aesop_with_overrides
```

**Setting the overrides file** (required; without it the tactic is identical to `aesop`):
```bash
export AESOP_OVERRIDES_JSON=/path/to/aesop_rule_ordering/aesop_overrides.json
```

The JSON file maps fully-qualified declaration names to floats in `[0, 1]`:
```json
{ "Exists": 0.833, "Or": 0.833, "Aesop.BuiltinRules.ext": 0.5 }
```

Only **unsafe** rules are affected — safe and norm rules use integer penalties and cannot have their success probabilities overridden.

**Custom `@[aesop ...]` attributes** work exactly as with stock `aesop`; the tactic accepts the same clauses (`add`, `erase`, `rule_sets`, `config`, `simp_config`). An `aesop_with_overrides?` variant (analogous to `aesop?`) is also available to emit a suggested proof script.

## Extraction

### Data Extraction
Our data collection process followed two primary strategies to capture a diverse range of mathematical contexts and theorem styles.

**Mathlib Data Collection:**
We collected data from Mathlib by systematically extracting theorems and their environmental contexts. This was achieved by parsing import statements, namespaces, and open statements to reconstruct the precise mathematical state. We utilized a custom tactic to execute `grind` and `aesop` across these theorems, extracting the goal states and proof traces to build a comprehensive map of Mathlib's successful automated proofs.

**External Dataset Integration:**
The second strategy involved leveraging several large-scale Lean datasets, collectively providing a vast search space for theorem automation:
- **NuminaMath Lean**: 104,155 competition-style theorems.
- **Lean Workbook**: 57,231 formal statements.
- **Herald**: 580,000 NL-FL statement pairs.
- **FineLeanCorpus**: 509,358 formalization entries.
- **LeanDojo-v2**: 120,000 statements

These datasets provide a vast collection of theorem statements that typically do not yet have accompanying proofs. From this pool, we have successfully verified and extracted proof traces for approximately **53,000 theorems** that work with either grind or aesop.

This collection forms the core of our training data, representing a diverse "Winning Spine" for both `grind` and `aesop` across different domains.


**Verification and Filtering:**
For `grind`, we tested each theorem to see if the tactic could autonomously close the goal. Successful cases were added to a JSONL dataset for training. This verification process was facilitated by **AXLE by axiom.ai**. 

For `aesop`, we employed a similar verification protocol but introduced a refinement step: we first attempted to solve the goal using `simp`. If `simp` failed but `aesop` subsequently succeeded, the theorem was added to our collection. This filtering ensures that our dataset prioritizes non-trivial proofs where `aesop`'s search capabilities provide unique value beyond standard simplification, reflecting its internal strategy of attempting simplification before proceeding with more complex search heuristics.

### Aesop Trace Extraction


### Grind Trace Extraction
We instrumented the `grind` tactic to capture the internal state and decision-making process at every "split" (branching point) during proof search. This instrumentation allows us to record the precisely timed "snapshots" of the prover's state.

**The Trace Data:**
For every successful proof, we extract a JSON trace containing:
- **Goal Features**: Numerical summaries such as `assertedCount` (total known facts), `ematchRounds`, and `splitDepth`.
- **Candidate Pool**: The full set of available branching options (e.g., case splits on an `if-then-else` or an implication), including their origins (`ematch`, `ext`, `input`, etc.).
- **Environmental Context**: A "Pretty-Printed" version of the local context and the internal state of the E-graph (the robot's "brain").
- **Winning Spine**: We prune these traces to retain only the "Winning Spine"—the sequence of successful decisions that directly led to the proof, discarding any exploratory dead ends.

## Training

### Aesop Training


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
