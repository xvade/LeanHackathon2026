# Unified Training Pipeline Plan

## The Problem

Two separate pipelines exist that need to be connected:

- **GrindExtraction** — a working, sophisticated Lean tool that instruments grind's
  split mechanism to record oracle split decisions. Currently outputs a simple format
  (`{pp, chosenIdx}`) that doesn't match what the training scripts expect.

- **training/** — a full ML pipeline (MLP model, supervised + RL training, Mathlib-scale
  data collection via `collect.py`) that expects a richer format
  (`{anchor, exprText, numCases, isRec, source, goalFeatures, chosenAnchor}`)
  written to `GRIND_LOG` by a `Logging.lean` that doesn't currently exist.

The training data in `training/data/` was collected by an earlier version of the code.
Right now there's no way to generate more of it.

---

## Step 1: Extend GrindExtraction to output the training format

Modify `GrindExtraction/GrindExtraction/Tracer.lean`:

- **`CandidateInfo`** — add `anchor : UInt64`, `numCases : Nat`, `isRec : Bool`, `source : String`
  - All already available from `SplitCandidateWithAnchor` (`.anchor`, `.numCases`, `.isRec`, `.c.source`)

- **`SplitDecision`** — replace `chosenIdx : Nat` with `chosenAnchor : UInt64`
  - Currently we match on pretty-printed text to find the chosen candidate;
    instead match on anchor directly

- **`CollectSample`** — add `goalFeatures` per step
  - `splitDepth` = `goal.split.num` (public field)
  - `assertedCount` = `goal.facts.size` (public field)
  - `ematchRounds` = `goal.ematch.num` (public field)
  - `splitTraceLen` = `goal.split.trace.length` (public field)
  - `numCandidates` = `anchors.candidates.size`

- **Output format** — restructure JSON to match training schema:
  ```json
  {
    "proofId": <hash of theorem name>,
    "outcome": "success" | "failure",
    "steps": [
      {
        "step": 0,
        "goalFeatures": { "splitDepth": 0, "assertedCount": 3, ... },
        "candidates": [{ "anchor": 123, "exprText": "...", "numCases": 2, "isRec": false, "source": "ematch" }],
        "chosenAnchor": 123
      }
    ]
  }
  ```

- **`grind_collect` tactic** — no interface change needed, just richer internal recording

---

## Step 2: Scale up data collection via Mathlib

Two options (either works):

**Option A — Use `collect.py` with a thin Logging shim**

Implement `NeuralTactic/NeuralTactic/Logging.lean` as a thin wrapper around the
extended GrindExtraction logic:
- When `GRIND_LOG` env var is set, accumulate decisions inside `neuralSplitNext`
  and write the JSONL record to that file at tactic end
- `collect.py` already handles batching, parallelism, and aggregation

**Option B — Run `grind_collect` directly on Mathlib**

Write a script that:
1. Finds Mathlib theorems proved by `grind` (same grep as `collect.py` already does)
2. Generates batch `.lean` files using `grind_collect` instead of `neural_grind`
3. Runs `lake env lean` on each batch
4. Captures stdout (already JSONL from `IO.println`)

Option B is safer for now since GrindExtraction already works and won't have
the `Logging.lean` / FFI dependency issues.

---

## Step 3: Train the MLP model

With data in the training format:

```bash
cd NeuralTactic
python3 training/train.py --data training/data/collected_new.jsonl --out training/model.pt
```

The `training/train.py` script is already complete — it reads the JSONL,
builds trigram + numeric features, trains the MLP, saves `model.pt`.

---

## Step 4: Hook the model up to `neural_grind`

Two sub-options depending on how ambitious:

**Option A — Minimal: update `scripts/server.py` weights**

The current `SplitPolicy.lean` already calls `scoreCandidate(goalPP, candPP) : Float`
via Unix socket. Update `scripts/server.py` to load `model.pt` and serve float scores
using the trained MLP (instead of the hardcoded bag-of-words weights).

- Lean side: no changes needed
- Server side: replace hardcoded weights with `model.forward(...)` call
- Works with existing `score_client.c`
- Limitation: goalFeatures won't be used (passes zeros); only text features active

**Option B — Full: switch to anchor-based JSON protocol**

Update `SplitPolicy.lean` and a new C stub to speak the training format:
- Send `{goalFeatures, candidates}` JSON to `training/serve.py`
- Receive `chosenAnchor` integer back
- Look up the matching `SplitCandidateWithAnchor` and call `splitCore` on it
- Uses the full model including numeric features

---

## Step 5: Test

Run `neural_grind` on some theorems and verify it:
1. Builds without errors
2. Actually calls the model (check `GRIND_MODEL` / server is running)
3. Closes goals that `grind` can also close

---

## Step 6 (Stretch): RL loop

Once the supervised model works:

```bash
python3 training/rl_loop.py --iters 5 --out training/data/rl_new/
```

This uses the existing `collect.py` + `train_rl.py` infrastructure to run
REINFORCE iterations — collecting rollouts with the current model, rewarding
successes, and updating weights. The goal is to find proof paths that
grind's heuristic misses.

---

## Summary of what needs to be written

| File | Change |
|------|--------|
| `GrindExtraction/GrindExtraction/Tracer.lean` | Extend data format (anchor, source, goalFeatures) |
| `GrindExtraction/Main.lean` | Add Mathlib imports + more theorems (or script generates them) |
| `collect_grind.sh` (new) | Script to run `grind_collect` on Mathlib at scale |
| `NeuralTactic/scripts/server.py` | Load `model.pt`, serve MLP scores |
| `NeuralTactic/NeuralTactic/Logging.lean` | (Optional, for Option B) Write decisions to GRIND_LOG |
| `NeuralTactic/native/score_client.c` | (Optional, for Option B) JSON protocol |
| `NeuralTactic/NeuralTactic/SplitPolicy.lean` | (Optional, for Option B) Send full features |
