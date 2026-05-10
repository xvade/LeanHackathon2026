# Training Experiments

Tracking ablations and architecture variations for `SplitRanker`.

## Evaluation Protocol

All experiments use the same benchmark:
```bash
python3 training/benchmark.py --n 3 --workers 8 --timeout 60 --seed 42
```

Metrics recorded per experiment:
- **Train acc %** — argmax matches chosenAnchor on training set
- **Benchmark wins** — theorems where neural uses fewer splits than grind
- **Benchmark ties** — same split count
- **Benchmark losses** — grind uses fewer splits, or grind solves but neural fails
- **Split reduction %** — (grind_splits − neural_splits) / grind_splits on all-solved theorems

Training data: `training/data/verified_splits.jsonl`  
565 records · 1,405 split decisions · 850 multi-candidate (≥2 options)

Key fact: grind chooses `argmin(numCases)` in **89.6%** of multi-candidate decisions.
Any model that doesn't beat ~90% training accuracy isn't learning above the heuristic.

---

## Data Observations

| Stat | Value |
|------|-------|
| Multi-candidate steps | 850 |
| Source breakdown | ematch 83%, ext 12%, input 6%, other <1% |
| Pool size range | 2–17 (median ~4) |
| Generation range | 0–6 (mean 1.9) |
| Chosen == min numCases | 89.6% |
| Chosen == min(numCases, generation) | 14.8% (many ties → other tiebreakers) |

---

## Experiments

### EXP-00 — Pure Heuristic Baseline (no model)
**Status:** Not run  
**Hypothesis:** argmin(numCases, generation) replicate grind's own strategy  
**What changes:** `serve.py` modified to ignore model; sort candidates by (numCases, generation) and return first anchor  
**Purpose:** Floor. If a trained model can't beat this, something is wrong.  
**Notes:** Because chosen==min(numCases,generation) is only 14.8% in data, grind uses additional tiebreakers we don't have; this baseline may perform worse than our trained models.

---

### EXP-01 — Numeric Only
**Status:** Not run  
**Hypothesis:** Text features (exprText, statePP, grindState) add noise, not signal — the 17 numeric dims suffice  
**Architecture:** 17 → 256 → 256 → 1 (no embeddings, no context encoders)  
**What changes:**
- `features.py`: `batch_numeric` unchanged
- `model.py`: remove `emb`, `text_proj`, `state_proj`, `grind_proj`; `forward` takes only `numeric`
- `train.py` / `benchmark.py`: stop passing text tensors
  
**Command:**
```bash
python3 training/train.py --data training/data/verified_splits.jsonl \
  --out training/checkpoints/exp01_numeric_only.pt --epochs 40 --lr 1e-3
```

---

### EXP-02 — Numeric + Pool Aggregates (no text)
**Status:** Not run  
**Hypothesis:** The cross-candidate blindspot (not knowing "I'm the min-cases candidate") is the main gap; pool-level stats fix it without any text  
**Architecture:** (17 + 7 pool features) → 256 → 256 → 1  
**Pool features added per candidate:**
- `rank_numCases` — rank of this candidate by numCases within pool (0=lowest)
- `rank_generation` — rank by generation
- `is_min_cases` — 1.0 if this candidate has the minimum numCases
- `is_min_generation` — 1.0 if this has the minimum generation
- `pool_size` — total number of candidates
- `frac_same_cases` — fraction of pool with same numCases as this candidate
- `frac_input_source` — fraction of pool that has source=="input"

**What changes:** `features.py`: new `pool_augment(cands, goal)` function appended to `batch_numeric`  

**Command:**
```bash
python3 training/train.py --data training/data/verified_splits.jsonl \
  --out training/checkpoints/exp02_pool_aggregates.pt --epochs 40 --lr 1e-3
```

---

### EXP-03 — Current Model (reference)
**Status:** Complete  
**Architecture:** numeric(17) + exprText trigrams(512-emb) + statePP(128-ctx) + grindState(128-ctx) → 256 → 1  
**Benchmark:** 1 win / 25 tie / 3 loss  
**Split reduction:** +19.0% on contested theorems  
**Notes:** Trained on 565 records, 850 multi-candidate steps. Genuine failures: symm_symm, trans_prod_eq_prod_trans, compl_neighborFinset_sdiff_inter_eq (all Topology/Combinatorics).

---

### EXP-04 — Ablate grindState
**Status:** Not run  
**Hypothesis:** grindState text is proof-specific noise that doesn't generalize via trigrams; removing it improves generalization  
**Architecture:** numeric(17) + exprText(512-emb) + statePP(128-ctx) → 256 → 1 (drop grind_ids path)  
**What changes:** `model.py`: pass `grind_ids=None` always; zero out grind_proj path  
**Command:**
```bash
python3 training/train.py --data training/data/verified_splits.jsonl \
  --out training/checkpoints/exp04_no_grindstate.pt --epochs 40 --lr 1e-3
```

---

### EXP-05 — Ablate statePP
**Status:** Not run  
**Hypothesis:** statePP adds redundancy (goal is implicit in what candidates appeared); variable names are noise  
**Architecture:** numeric(17) + exprText(512-emb) + grindState(128-ctx) → 256 → 1  
**Command:**
```bash
python3 training/train.py --data training/data/verified_splits.jsonl \
  --out training/checkpoints/exp05_no_statePP.pt --epochs 40 --lr 1e-3
```

---

### EXP-06 — Ablate exprText
**Status:** Not run  
**Hypothesis:** Expression text trigrams are hurt by alpha-renaming; all signal is in numeric + context  
**Architecture:** numeric(17) + statePP(128-ctx) + grindState(128-ctx) → 256 → 1  
**Command:**
```bash
python3 training/train.py --data training/data/verified_splits.jsonl \
  --out training/checkpoints/exp06_no_exprtext.pt --epochs 40 --lr 1e-3
```

---

### EXP-07 — grindState as Counts Only
**Status:** Not run  
**Hypothesis:** What matters about grindState is *volume* (how much work grind has done), not expression content  
**Architecture:** numeric(17 + 3 count features) + exprText(512-emb) + statePP(128-ctx) → 256 → 1  
**grindState count features added to numeric:**
- `n_asserts` — count of `grind.assert` events since proof start
- `n_eqc` — count of `grind.eqc` events
- `n_ematch` — count of `grind.ematch.instance.assignment` events

**What changes:** `features.py`: parse grindState list for event type prefixes and add 3 counts to numeric vector  
**No Lean changes needed** — already have the grindState list, just count by prefix.

---

### EXP-08 — Numeric + Pool Aggregates + grindState Counts
**Status:** Not run  
**Hypothesis:** Combine the best cheap additions: pool aggregates (cross-candidate) + grindState counts (proof depth signal), skip all text  
**Architecture:** (17 + 7 pool + 3 grind counts) → 256 → 256 → 1  
**Purpose:** If this matches EXP-03, it means the text features in the current model contribute nothing.

---

### EXP-09 — Smaller Embedding (512 → 64)
**Status:** Not run  
**Motivation:** 512-dim embeddings trained on 850 examples is overparameterized; 65536 trigrams × 512 = 33M params just in the embedding table  
**Architecture:** Same as EXP-03 but `TEXT_EMB_DIM=64`, hidden=128  
**Expected benefit:** Less overfitting, faster inference in serve.py  
**Gate:** Only run once we have significantly more data (>5k multi-cand steps), otherwise underfitting risk.

---

### EXP-10 — Listwise Attention over Pool
**Status:** Not run (higher effort)  
**Motivation:** Pointwise scoring can't reason "I have the fewest cases of all 12 candidates"; attention over the pool encodes this naturally  
**Architecture:** Each candidate → feature vector (numeric + text) → small transformer (2 heads, 2 layers) over pool → per-candidate score  
**Gate:** Only worth building if pool aggregates (EXP-02) don't close the gap — that's the cheap version of the same fix.

---

## Results Table

| Exp | Description | Train Acc | Wins | Ties | Losses | Split Δ% | Notes |
|-----|-------------|-----------|------|------|--------|----------|-------|
| EXP-00 | Heuristic baseline | — | ? | ? | ? | — | to run |
| EXP-01 | Numeric only | ? | ? | ? | ? | — | to run |
| EXP-02 | Numeric + pool agg | ? | ? | ? | ? | — | to run |
| EXP-03 | Current (full) | ~100% | 1 | 25 | 3 | +19.0% | reference |
| EXP-04 | Ablate grindState | ? | ? | ? | ? | — | to run |
| EXP-05 | Ablate statePP | ? | ? | ? | ? | — | to run |
| EXP-06 | Ablate exprText | ? | ? | ? | ? | — | to run |
| EXP-07 | grindState counts | ? | ? | ? | ? | — | to run |
| EXP-08 | Num + pool + counts | ? | ? | ? | ? | — | to run |
| EXP-09 | Smaller emb (64) | ? | ? | ? | ? | — | needs more data |
| EXP-10 | Listwise attention | ? | ? | ? | ? | — | gate on EXP-02 |

---

## Running Order

Recommended sequence (each ~2 min train + 10 min benchmark):

1. **EXP-01** — numeric only (cheapest, sets the floor for text contribution)
2. **EXP-02** — pool aggregates (tests cross-candidate fix, no text)
3. **EXP-04, 05, 06** — ablations in parallel (identify which text modality hurts)
4. **EXP-07** — grindState counts (if ablation shows grindState text hurts)
5. **EXP-08** — combined best (numeric + pool + counts, no text)
6. **EXP-10** — listwise attention (if pool aggregates don't close gap)
