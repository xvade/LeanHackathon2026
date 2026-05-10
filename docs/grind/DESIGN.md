# Neural Grind — Design Document

## What we are building

`grind` is Lean 4's SMT-style automation tactic. Its main decision point is
**which expression to case-split on** at each step. The split order can
dramatically affect proof length — a bad sequence of splits leads to exponential
blowup; a good one closes the goal quickly.

We are training a small neural ranker that scores each split candidate at
decision time and selects the best one. The ranker replaces grind's built-in
heuristic (fewest cases, lowest generation) with a learned policy.

---

## System overview

```
Mathlib theorems
      │
      ▼
grind_collect (Lean tactic, GrindExtraction package)
      │  emits one JSON record per theorem to stdout
      ▼
collect_verified.py / collect.py
      │  batch-runs Lean, aggregates JSONL
      ▼
training/data/verified_splits.jsonl
      │
      ▼
train.py  (supervised imitation of grind's choices)
      │           or
train_rl.py  (REINFORCE on proof success/failure)
      │
      ▼
model.pt  (SplitRanker checkpoint)
      │
      ▼
serve.py  (persistent subprocess, reads queries from stdin)
      ▲
      │  JSON over subprocess pipe
neural_collect / neural_grind  (Lean tactics, NeuralTactic package)
```

---

## Data format

### Collection output (`grind_collect` tactic, GrindExtraction schema)

One JSON line per theorem, written to stdout by `grind_collect`:

```json
{
  "theoremName": "batch_0000",
  "goalPP":      "¬Even n ↔ n % 2 = 1",
  "solved":      true,
  "splitDecisions": [
    {
      "step":         0,
      "goalFeatures": {
        "splitDepth":    0,
        "assertedCount": 5,
        "ematchRounds":  1,
        "splitTraceLen": 0,
        "numCandidates": 2
      },
      "statePP": [
        "m : ℤ",
        "n : ℤ",
        "h : (¬Even n) = ¬n % 2 = 1",
        "⊢ False"
      ],
      "grindState": [
        "(¬Even n) = ¬n % 2 = 1",
        "((¬Even n) = ¬n % 2 = 1) = True",
        "n % 2 + -1 ≤ 0",
        "..."
      ],
      "pool": [
        {
          "anchor":    "17211317105542075118",
          "exprText":  "Even n = (n % 2 = 0)",
          "numCases":  2,
          "isRec":     false,
          "source":    "ematch",
          "generation": 1
        },
        {
          "anchor":    "1901519565291932661",
          "exprText":  "(¬Even n) = ¬n % 2 = 1",
          "numCases":  2,
          "isRec":     false,
          "source":    "input",
          "generation": 0
        }
      ],
      "chosenAnchor": "17211317105542075118"
    }
  ]
}
```

**Field notes:**
- `pool` = all candidates grind considered; `chosenAnchor` = grind's actual choice
- `source` values: `input` (from the original goal), `ematch` (E-matching a
  lemma), `inj` (injectivity), `ext` (extensionality), `mbtc` (model-based
  theory combination), `beta`, `forallProp`, `existsProp`, `guard`
- `generation`: grind's internal counter — lower = this candidate entered earlier
  in the proof search. Grind uses this as its primary tiebreaker when numCases
  is equal, so lower generation is generally preferred.
- `statePP`: tactic proof state at the moment of the decision — what you would
  see in the infoview. Each hypothesis as `"name : type"`, goal as `"⊢ goal"`.
- `grindState`: all `grind.assert`, `grind.eqc`, and
  `grind.ematch.instance.assignment` trace events accumulated since proof start.
  These represent grind's internal knowledge at decision time.
- Anchors are serialized as decimal strings (UInt64).

### Normalized training schema

`normalize_record()` in `train.py` / `train_rl.py` translates both the
GrindExtraction schema (`solved`/`splitDecisions`/`pool`) and the older
NeuralTactic schema (`outcome`/`steps`/`candidates`) to a common format with
`outcome` and `steps`, so training scripts handle both sources transparently.

---

## Model architecture (`training/model.py`)

### Inputs (per split decision)

| Tensor | Shape | Description |
|--------|-------|-------------|
| `numeric` | (N, 17) | Per-candidate numeric features |
| `text_ids` | (N, L₁) | Trigram IDs for each candidate's `exprText` |
| `state_ids` | (L₂,) | Trigram IDs for joined `statePP` strings |
| `grind_ids` | (L₃,) | Trigram IDs for joined `grindState` strings (first 30 events) |

N = number of candidates (typically 2–10). `state_ids` and `grind_ids` are
optional; the model substitutes zeros when absent (e.g. during inference
when the Lean client does not yet send context).

### Numeric features (17-dim)

```
numCases        float   how many sub-goals this split creates (lower = better)
isRec           0/1     whether the expression is recursive
source_ematch   0/1  ┐
source_ext      0/1  │
source_mbtc     0/1  │  one-hot encoding of how the candidate
source_beta     0/1  ├  entered grind's search
source_forallProp 0/1│
source_existsProp 0/1│
source_input    0/1  │
source_inj      0/1  │
source_guard    0/1  ┘
generation      float   grind's internal generation counter (lower = older)
splitDepth      float   current split recursion depth
assertedCount   float   number of facts grind has asserted so far
ematchRounds    float   number of E-matching rounds completed
splitTraceLen   float   length of grind's current split trace
numCandidates   float   total candidates in this pool
```

### Architecture

```
candidate exprText  ──trigrams──► Embedding(65536, 512) ──mean-pool──► (N, 512)
                                                                            │
statePP (joined)    ──trigrams──► Embedding(65536, 512) ──mean-pool──►   (512,)
                                                          ──Linear──► ReLU──► (N, 128)
                                                                            │
grindState[:30]     ──trigrams──► Embedding(65536, 512) ──mean-pool──►   (512,)
(first 30 events)                                         ──Linear──► ReLU──► (N, 128)
                                                                            │
numeric             ──────────────────────────────────────────────────► (N, 17)
                                                                            │
                    cat ──────────────────────────────────────────────► (N, 785)
                    Linear(785, 256) → ReLU → Linear(256, 1) ──────────► (N,)
```

The shared embedding table is used for all three text inputs since they are all
in the same domain (Lean expressions and proof terms).

### Output

`(N,)` float scores. Higher = this candidate should be split on first.
During training: softmax cross-entropy (supervised) or log-prob × advantage (RL).
During inference: argmax selects the anchor to pass back to Lean.

---

## Key design decisions

### grindState: first K events, not last K

grindState events are in chronological order of derivation. The **first** events
are grind's foundational assertions about the problem structure (goal
decomposition, basic type equalities). Later events are cascading derived
equalities that follow from the early ones and tend to be noisier.

Truncating to the first `GRIND_STATE_MAX_EVENTS = 30` events keeps the
structural core and discards the downstream noise. "Last K" would give you
recent but potentially circular/redundant derivations.

### statePP and grindState are per-decision, not per-candidate

The proof state and grind's internal knowledge are the same for all candidates
at a given decision point. They are encoded once (shared context), projected
to 128-dim, and broadcast across all N candidates before the final MLP. This
is cheaper than encoding them per-candidate and is structurally correct.

### Pointwise scoring with optional cross-candidate extension

Currently each candidate is scored independently. This is a known limitation —
the model cannot reason about relative candidate quality (e.g. "prefer input
over ematch *when both are available*"). 

The intended fix (when more data is available) is either:
1. Pool-level aggregate statistics added to numeric features (~5 extra dims,
   zero architectural change): pool_min_numCases, pool_min_generation,
   fraction_input_source, candidate_rank_by_numCases, candidate_rank_by_generation
2. A single lightweight cross-attention layer over candidates before scoring

Option 1 is preferred first because it adds no parameters.

### Anchor comparison as strings

Anchors are UInt64 values serialized as decimal strings in the GrindExtraction
schema. All comparisons (`chosenAnchor == pool[i].anchor`) are done as string
comparisons to avoid precision loss when parsing large integers into Python
floats or 32-bit ints.

### Inference falls back gracefully without context

`state_ids` and `grind_ids` are optional in `model.forward()`. When absent
(the current Lean inference client does not yet send them), the context
branches produce zero vectors. This means a checkpoint trained with full
context degrades to numeric+text-only scoring at inference time rather than
crashing.

### Supervised imitation vs. RL

- **Supervised (`train.py`)**: train to imitate grind's own split choices on
  successful proofs. Labels are grind's heuristic decisions, so the model
  learns a smooth approximation of the heuristic. Useful for bootstrapping;
  cannot improve *over* the heuristic.
- **RL (`train_rl.py`)**: REINFORCE with per-epoch mean baseline. Reward =
  `reward_success / num_steps` for successful proofs (shorter = better),
  `reward_failure` for failures. Trains on *all* outcomes including failures,
  which provides contrastive signal the supervised approach lacks.

The intended workflow is supervised pre-training → RL fine-tuning.

---

## Data pipeline

### Source 1: pre-verified theorems (`collect_verified.py`)

Reads `training/grind_results_verified.jsonl` (747 Mathlib theorems verified
to be solvable by grind). Transforms each `lean_snippet` field:
- Strips `import Mathlib`, adds `import GrindExtraction`
- Replaces `grind` → `grind_collect`
- Wraps in `section`/`end` for namespace scoping
- Batches 20 snippets per `.lean` file, runs in parallel

Use `--only-plain` to skip the 182 theorems that use `grind` with hints (those
hints won't be present in `grind_collect`, so success rate drops).

### Source 2: Mathlib scan (`collect.py`)

Scans Mathlib files ranked by `grind` density, extracts theorem signatures,
generates `example ... := by grind_collect` blocks, runs under GrindExtraction.

### Output location

`training/data/verified_splits.jsonl` — canonical training dataset.

---

## Computational constraints

The model runs at every split decision during live proof search, called via a
subprocess pipe from the Lean process to `serve.py`. Round-trip latency budget
is single-digit milliseconds.

**Embedding table dominates**: 65,536 × 512 = 33M params ≈ 128MB per worker.
With 8 parallel Lean workers this is 1GB just for embeddings.

**Planned reduction** (not yet implemented — waiting for more data to validate):
- `TEXT_EMB_DIM`: 512 → 64 (embedding table: 128MB → 16MB, 8× faster)
- `CONTEXT_DIM`: 128 → 32
- `hidden`: 256 → 64
- Resulting total: ~4M params, ~16MB

This reduction is deferred until we have enough data to confirm that text
features actually help over numeric-only. If they do not help, drop text
entirely and run a ~1K-parameter numeric MLP.

---

## File map

```
training/
  features.py          feature extraction (numeric + trigrams + context)
  model.py             SplitRanker architecture
  train.py             supervised imitation training
  train_rl.py          REINFORCE policy gradient training
  serve.py             inference server (stdin/stdout JSON protocol)
  collect.py           Mathlib scan → batch collection
  collect_verified.py  pre-verified snippets → batch collection
  rl_loop.py           orchestrates collect → train → repeat
  grind_results_verified.jsonl   747 verified theorem metadata (input, not training data)
  data/
    verified_splits.jsonl        canonical training dataset (grind_collect schema)

GrindExtraction/
  GrindExtraction/Tracer.lean    grind_collect tactic (rich schema with context)

NeuralTactic/
  NeuralTactic/CollectTactic.lean  neural_collect tactic (GRIND_LOG-based, no @[extern])
  NeuralTactic/Tactic.lean         neural_grind tactic (@[extern], compiled only)
  NeuralTactic/SplitPolicy.lean    neuralSplitNext action (currently falls back to splitNext)
```
