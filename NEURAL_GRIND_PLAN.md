# Neural Grind Plan

This is the working plan for improving `neural_grind`. The priority is no
longer offline agreement with `grind`; the priority is whether real
`neural_grind` improves real Lean compilation behavior compared with real
`grind`.

## Goal

Make `neural_grind` reliably better than `grind` on split-heavy proof search:

- preserve or improve compile success rate
- reduce split count where split traces are available
- reduce end-to-end compile time only after inference overhead is controlled
- avoid regressions where `grind` succeeds and `neural_grind` fails

Offline top-1 agreement with `grind` is now a diagnostic only. It is not the
success metric.

## Current Baseline

The current production benchmark is `training/benchmark.py`. It compares the
real tactics:

- `grind`
- `neural_grind`

It samples from:

- `mathlib`: `training/data/raw/grind_results_verified.jsonl`
- `workbook`: `training/data/raw/workbook_grind_solved_verified.jsonl`
- `numina`: `training/data/raw/numina_finelean_grind_verified.jsonl`
- `numina-v2`: `training/data/raw/numina_finelean_grind_v2.jsonl`

Example command:

```bash
/home/ec2-user/miniconda3/envs/leanhack/bin/python3 training/benchmark.py \
  --sources mathlib,workbook,numina \
  --n 1 \
  --max-per-source 12 \
  --workers 4 \
  --timeout 90 \
  --model training/experiments/exp08_num_pool_counts/model.pt \
  --serve training/experiments/exp08_num_pool_counts/serve.py
```

Recent result on 32 sampled problems:

```text
Neural wins : 0 / 32
Ties        : 30 / 32
Grind wins  : 2 / 32
Both failed : 0 / 32

By source:
  mathlib   n=12 tie=10 grind=2
  numina    n=11 tie=11
  workbook  n= 9 tie= 9

Comparable traced splits:
  grind=11 neural=11 reduction=+0.0%
```

The known regressions are:

- `mathlib/Combinatorics/compl_neighborFinset_sdiff_inter_eq`
- `mathlib/Topology/symm_symm`

These should be treated as high-priority failure cases.

## Benchmark Direction

We need two benchmark modes.

### Attribution Mode

Run each theorem independently through both tactics.

Purpose:

- identify exact regressions
- capture per-problem errors
- inspect split-count deltas

This is the current behavior of `training/benchmark.py`.

### Throughput Mode

Run larger batched Lean files using real `grind` and real `neural_grind`.

Purpose:

- measure compile throughput
- amortize import overhead
- better estimate speed once inference is moved out of Python

This should not use `grind_collect` or `neural_collect` as the primary
comparison. Collection tactics remain useful for data generation and analysis,
not for production benchmarking.

## Production Feature Contract

`neural_grind` should only depend on features that are cheap to compute at every
split decision inside Lean.

### Tier 0: No Model

Run the custom tactic loop with a grind-compatible fallback policy.

Purpose:

- measure overhead of replacing the split action
- establish a no-model control

### Tier 1: Cheap Numeric Features

Features:

- `numCases`
- `isRec`
- `source`
- `generation`
- `splitDepth`
- `assertedCount`
- `ematchRounds`
- `splitTraceLen`
- `numCandidates`

These are already available from grind structures and should be cheap.

### Tier 2: Cheap Pool Features

Tier 1 plus pool-relative features:

- rank by `numCases`
- rank by `generation`
- is minimum `numCases`
- is minimum `generation`
- pool size
- fraction with same `numCases`
- fraction with source `input`

This is the current best family of cheap features.

### Tier 3: Cheap Internal Counters

Only include these if they can be computed without pretty-printing or trace
formatting.

Possible examples:

- number of asserted facts
- number of equivalence classes
- number of e-matching rounds or assignments
- direct counters already present in grind state

Do not include formatted `grindState` strings in production unless measurement
shows the overhead is acceptable.

### Tier 4: Expensive Context

These are teacher-only by default:

- `exprText`
- `statePP`
- formatted `grindState`
- any feature that requires pretty-printing expressions or proof state

They can guide training, diagnostics, distillation, and data analysis, but they
should not be part of the deployed feature vector unless benchmarks prove they
are worth the overhead.

## Inference Runtime

The deployed model should not call Python.

Current Python subprocess inference is too expensive for per-split production
use. For the cheap numeric/pool models, the network is tiny enough to run
directly in C++:

- export trained weights to a compact file or generated C++ source
- compute features in Lean
- pass a dense float array to a native extension
- return candidate scores or the selected anchor

Initial target: native C++ inference for the Tier 2 numeric/pool MLP.

This will let us separate model quality from Python/PyTorch/JSON overhead.

## Experiment Program

The current native exp08 result is a baseline, not the destination. Beating
`grind` on wall-clock time requires the model to save more search work than it
adds in feature extraction and inference overhead. The no-model control shows
the tactic loop itself can be essentially neutral, and native C++ inference
reduces Python overhead enough that model quality now matters.

Experiments must be evaluated on clean held-out benchmark data. Historical
`model.pt` files were trained before the benchmark exclusion was made explicit,
so they are diagnostics only until retrained.

### Acceptance Criteria

Claim a model is better than `grind` only if it satisfies all of these:

- same or better compile success on the fixed split-active benchmark
- no known `grind`-succeeds / `neural_grind`-fails regression
- repeated timing, preferably `REPEAT >= 3`, shows a stable wall-clock win
- speed win holds on trace-free Lean batch timing, not only Python harness
- any extra feature cost is measured separately from model quality

Near-term target: get a native model to at least 3-5% faster than `grind` on
the fixed benchmark without losing proofs. Larger wins probably require outcome
or cost-aware training rather than plain imitation.

### EXP-0: Clean Baseline Rebuild

Retrain the current cheap experiments on:

- `training/data/clean/train_splits.jsonl`
- optionally source-specific clean slices for Mathlib, workbook, Numina, and
  Numina v2

Rows to rebuild first:

- cheap numeric clone
- numeric plus pool clone
- native exp08 export
- margin-gated native exp08

Purpose:

- remove benchmark leakage from the current model artifacts
- establish a clean baseline before adding new training objectives
- determine whether more data helps or hurts the current cheap feature family

### EXP-1: Data Mixture and Weighting

Train the same cheap Tier 2 model under different clean data mixtures:

- workbook only
- Mathlib only
- Numina/FineLean only
- all clean sources uniformly mixed
- split-active examples oversampled
- high-pool-size and high-split-depth examples oversampled
- source-balanced batches instead of raw concatenation

Purpose:

- identify which source distribution predicts the benchmark best
- avoid a large easy-data pool swamping the rare decisions that matter
- find whether the fixed benchmark is more Mathlib-like, workbook-like, or
  Numina-like in model behavior

### EXP-2: Cost-Aware Imitation

Plain imitation treats every split decision equally. For speed, later and more
branching decisions should matter more.

Train cheap models with weighted cross-entropy where weight depends on:

- number of candidates in the pool
- split depth
- remaining split count in the proof
- source theorem elapsed time
- whether the decision occurs in known regression or timeout-prone examples

Purpose:

- bias learning toward decisions with real runtime impact
- keep the deployed feature vector cheap while changing only the loss

### EXP-3: Calibration and Abstention

A model that is wrong rarely but badly can lose the whole proof. Continue using
native fallback to `Action.splitNext`, but train and tune abstention explicitly.

Experiments:

- sweep margin thresholds more finely than 100/500 milli-logits
- train with confidence penalties or label smoothing
- evaluate top-2 margin, entropy, and score gap as fallback signals
- compare always-override, margin-override, and learned-abstain policies
- track override rate separately from compile time

Purpose:

- find the highest safe override rate
- make speed improvements come from confident useful deviations, not random
  imitation noise

### EXP-4: Failure-Contrast Training

Build hard-negative datasets from real bad choices:

- cases where ungated models fail but `grind` succeeds
- cases where a model increases split count or timing
- cases where old text/context models choose a different path that is worse

Train cheap students to avoid those choices using:

- negative preference loss
- pairwise chosen-vs-bad ranking
- mixed objective: grind imitation plus hard-negative penalty

Purpose:

- reduce regressions before making the model more aggressive
- teach the model not just what `grind` did, but what observed bad policies did
  wrong

### EXP-5: Rich Teacher

Train a slow teacher with expensive context:

- Tier 1 and Tier 2 numeric features
- `exprText`
- `statePP`
- formatted `grindState`
- optional raw trace/event summaries

Teacher evaluation:

- offline ranking quality
- whether it fixes known hard cases
- per-problem compile behavior only as a diagnostic, not production timing

Purpose:

- determine whether expensive context contains useful signal
- create a better ranking target than raw `grind` imitation
- inform which cheap counters should be exposed at runtime

### EXP-6: Teacher-Student Distillation

Train cheap Tier 2 or Tier 3 students from the rich teacher:

- KL divergence to teacher soft rankings
- cross-entropy to teacher argmax
- mixed teacher + grind imitation objective
- temperature sweep for softened labels
- optional source-specific teachers

Purpose:

- transfer context-derived signal into a production-safe model
- keep runtime inputs free of `exprText`, `statePP`, and formatted
  `grindState`

### EXP-7: Outcome-Aware Fine-Tuning

Move beyond imitation by training from proof outcomes.

Candidate approaches:

- REINFORCE or bandit fine-tune from real `neural_grind` runs
- DAgger-style collection: run current model, fall back to grind, learn from
  disagreements and failures
- reward for success, penalty for regressions, small reward for fewer splits
- timing reward only after native inference is used
- separate safety model for "do not override here"

Purpose:

- learn choices that are faster than `grind`, not merely similar to `grind`
- directly optimize the metric we care about

### EXP-8: Local Branch-Cost Labels

For selected split decisions, evaluate more than the `grind`-chosen branch
order and label candidates by observed downstream cost.

Possible labels:

- candidate whose first branch closes fastest
- candidate with lowest total split count downstream
- candidate with lowest timeout/failure risk
- candidate that minimizes total elaboration time in a bounded local search

Purpose:

- create supervised labels that can improve beyond grind imitation
- use expensive exploration offline while keeping deployment cheap

### EXP-9: Pool-Level Models

The current MLP scores candidates mostly pointwise. Test small pool-level
models over cheap features:

- pairwise preference scorer
- DeepSets-style pool summary
- tiny self-attention over candidates
- linear/rule-based baseline for interpretability

Constraints:

- C++ export required before timing claims
- strict size budget so inference overhead remains below the observed native
  exp08 overhead

Purpose:

- let the model reason about relative candidate quality
- improve decisions in large candidate pools where pointwise scoring is weak

### EXP-10: Cheap Internal Counters

Expose cheap direct counters from grind internals without pretty-printing.

Candidate counters:

- asserted fact count by category
- equivalence-class count
- e-matching instance counts
- candidate source histogram
- generation histogram
- number of pending split candidates by source

Purpose:

- recover some context signal without `statePP` or formatted `grindState`
- test whether Tier 3 features improve speed enough to justify collection cost

### EXP-11: Runtime Overhead Reduction

Native subprocess inference is close, but still not free. Measure and reduce
runtime overhead independently from model quality.

Experiments:

- native server vs Python server on the same model
- generated C++ weights vs binary weight loading
- persistent server startup amortization
- simplified line protocol instead of JSON if serialization shows up in timing
- in-process Lean/native route if we can make symbol loading reliable
- quantized or smaller model variants
- feature extraction microbenchmarks for each feature tier

Purpose:

- ensure small model improvements are not hidden by avoidable overhead
- define the maximum model size we can afford

### EXP-12: Benchmark Expansion

Keep the current 75-problem fixed benchmark because it has useful split-active
properties. Add separate suites rather than replacing it:

- larger held-out split-active benchmark built with the same criteria
- source-specific suites: Mathlib, workbook, Numina/FineLean
- stress suite with large candidate pools and many splits
- regression suite from every model failure
- timing-stability suite for repeated runs

Purpose:

- avoid overfitting the fixed benchmark
- understand where a model wins or loses
- keep one stable target while broadening confidence

## Immediate Roadmap

1. Done: treat current model results as historical because they predate clean
   benchmark exclusion.

2. Done: retrain clean exp08 from `training/data/clean/train_splits.jsonl`,
   export to native C++, and run the existing matrix with `REPEAT=3`.

3. Done: add clean experiment rows for `model_clean.pt` and native clean
   weights so clean and historical results are visible side by side.

4. Done: run EXP-1 data mixture sweeps using the same cheap Tier 2
   architecture on the held-out split-active benchmark.

5. Partly done: add instrumentation to report override rate and fallback rate
   for margin-gated rows. Per-problem timing deltas are still open.

6. Next: run trace-free whole-corpus batch timing for the promising EXP-1
   models. The current EXP-1 timing numbers are case-level, parallel, and
   decision-logged, so they are useful diagnostics but not final speed claims.

7. Next: run a model-width sweep on the strongest clean exp08 mix to see how
   far size reduction alone can cut native inference overhead.

8. Implement EXP-2 cost-aware imitation and EXP-3 calibration sweeps.

9. Build the first hard-negative dataset from failed ungated rows and run
   EXP-4 failure-contrast training.

10. Train the rich teacher and distill a cheap student only after the clean
    cheap baselines are measured, so the benefit is attributable.

11. Start outcome-aware fine-tuning once the native clean model is stable enough
    that timing feedback is meaningful.

## Progress Notes

### 2026-05-10

Completed:

- fixed split-active benchmark corpus: `training/data/split_active_benchmark.jsonl`
- single Lean benchmark corpus: `training/benchmarks/split_active.lean`
- clean training-data pipeline:
  `training/collect_benchmark_traces.py`,
  `training/filter_training_data.py`, and
  `training/make_clean_training_data.sh`
- no-model control mode: `GRIND_NO_MODEL=1`, delegating exactly to native
  `Action.splitNext`
- cheap production path skips candidate expression pretty-printing by default
- opt-in expression text: `GRIND_INCLUDE_EXPR_TEXT=1`
- margin-gated model override: `GRIND_MARGIN_MILLI=<n>`
- server protocol now returns `anchor margin_milli`
- Python benchmark now reports elapsed time as the primary metric
- trace-free Lean batch timing files:
  `training/benchmarks/split_active_timing_grind.lean` and
  `training/benchmarks/split_active_timing_neural_grind.lean`
- command-line batch timing runner:
  `training/benchmarks/run_split_active_timing.sh`

No-model fixed-benchmark result:

- command: `python3 training/benchmark.py --benchmark-file training/data/split_active_benchmark.jsonl --neural-no-model --workers 4 --timeout 120`
- 75 problems, all native `grind` runs solved
- `neural_grind` no-model: 0 wins, 75 ties, 0 grind wins
- 0 grind-solved / neural-failed regressions
- comparable solved traced splits: grind=489, neural=489, reduction=+0.0%
- elapsed wall time: 154.4s

Trace-free Lean batch timing result:

- command: `GRIND_NO_MODEL=1 REPEAT=1 bash training/benchmarks/run_split_active_timing.sh both`
- direct `lake env lean` over the full 75-problem corpus
- `grind`: 14.49s real, 20.13s user, 1.75s sys
- `neural_grind` no-model: 14.49s real, 20.25s user, 1.67s sys

Experiment matrix result:

- command: `REPEAT=1 STAMP=enabled_matrix_001 bash training/experiments/run_timing_matrix.sh`
- summary: `training/experiments/results/enabled_matrix_001/summary.tsv`
- grind baseline: 14.43s
- `no_model`: ok, 14.54s, -0.76% vs grind
- `exp01_numeric_only`: fail, 15.92s before failure, -10.33% vs grind
- `exp08_num_pool_counts`: fail, 16.33s before failure, -13.17% vs grind
- `exp08_num_pool_counts_m100`: ok, 16.17s, -12.06% vs grind
- `exp08_num_pool_counts_m500`: ok, 16.23s, -12.47% vs grind

C++ inference result:

- native exp08 weights: `training/experiments/exp08_num_pool_counts/model.native.bin`
- native server source: `NeuralTactic/native/model.cpp` compiled with
  `-DNEURAL_GRIND_STANDALONE`
- export script: `training/export_exp08_native.py`
- command: `REPEAT=1 TIMEOUT=60 STAMP=enabled_matrix_native_001 bash training/experiments/run_timing_matrix.sh`
- summary: `training/experiments/results/enabled_matrix_native_001/summary.tsv`
- grind baseline: 14.46s
- `no_model`: ok, 14.47s, -0.07% vs grind
- Python `exp08_num_pool_counts_m100`: ok, 16.39s, -13.35% vs grind
- Python `exp08_num_pool_counts_m500`: ok, 16.31s, -12.79% vs grind
- native `exp08_native_m100`: ok, 14.66s, -1.38% vs grind
- native `exp08_native_m500`: ok, 14.69s, -1.59% vs grind

All existing experiment artifacts result:

- command: `RUN_DISABLED=1 REPEAT=1 TIMEOUT=90 STAMP=all_experiments_001 bash training/experiments/run_timing_matrix.sh`
- summary: `training/experiments/results/all_experiments_001/summary.tsv`
- grind baseline: 14.42s
- `no_model`: ok, 14.39s, +0.21% vs grind
- `exp01_numeric_only`: fail, 16.11s before failure, -11.72% vs grind
- `exp08_num_pool_counts`: fail, 16.31s before failure, -13.11% vs grind
- Python `exp08_num_pool_counts_m100`: ok, 16.25s, -12.69% vs grind
- Python `exp08_num_pool_counts_m500`: ok, 16.26s, -12.76% vs grind
- native `exp08_native_m100`: ok, 14.85s, -2.98% vs grind
- native `exp08_native_m500`: ok, 14.82s, -2.77% vs grind
- `exp02_pool_aggregates`: fail, timed out at 90.02s
- `exp03_current`: ok, 33.40s, -131.62% vs grind
- `exp04_no_grindstate`: fail, timed out at 90.02s
- `exp05_no_statePP`: fail, timed out at 90.02s
- `exp06_no_exprtext`: fail, 16.37s before failure, -13.52% vs grind
- `exp07_grindstate_counts`: fail, timed out at 90.02s

Clean data snapshot:

- command: `bash training/make_clean_training_data.sh`
- benchmark traces: `training/data/split_active_benchmark_traces.jsonl`
- clean combined training file: `training/data/clean/train_splits.jsonl`
- `verified_splits.jsonl`: kept 537, dropped 28
- `workbook_splits.jsonl`: kept 4140, dropped 26
- `numina_finelean_splits.jsonl`: kept 3837, dropped 38
- `numina_finelean_v2_splits.jsonl`: kept 7929, dropped 49
- second-pass leak check over the clean files dropped 0 records
- current historical experiment models were trained before this split was made
  explicit, so they should be retrained before treating benchmark scores as
  clean test-set results

Clean exp08 retrain result:

- command: `CUDA_VISIBLE_DEVICES=1 bash training/experiments/train_clean_model.sh exp08_num_pool_counts`
- trainer was batched by candidate-pool size so CUDA is used effectively
- clean training data: `training/data/clean/train_splits.jsonl`
- loaded 15697 multi-candidate decision steps
- model: `training/experiments/exp08_num_pool_counts/model_clean.pt`
- native weights:
  `training/experiments/exp08_num_pool_counts/model_clean.native.bin`
- final training accuracy: 93.0%
- single-run matrix:
  `training/experiments/results/clean_exp08_001/summary.tsv`
- repeated native matrix:
  `training/experiments/results/clean_exp08_native_repeat_001/summary.tsv`
- ungated `exp08_clean`: fail, 19.11s before failure
- ungated failures:
  `mathlib/Topology/trans_prod_eq_prod_trans`,
  `workbook/lean_workbook_plus_13598`
- Python `exp08_clean_m100`: ok, 19.09s, -24.85% vs grind
- Python `exp08_clean_m500`: ok, 19.21s, -25.64% vs grind
- native `exp08_clean_native_m100`: ok, 3-run average 15.793s,
  -2.37% vs grind
- native `exp08_clean_native_m500`: ok, 3-run average 15.633s,
  -1.34% vs grind
- correction: those first native clean timings were contaminated by a native
  C++ anchor parsing bug. Anchors were parsed through floating point, so large
  64-bit anchors did not match Lean candidate anchors and the native rows were
  effectively falling back to `Action.splitNext`.

Native anchor fix and always-override result:

- fixed `NeuralTactic/native/model.cpp` to parse candidate anchors as `UInt64`
  decimal integers, not doubles
- added `GRIND_DECISION_LOG=<path>` to log split-policy decisions as JSONL
- native always-override now behaves like Python always-override and fails
  on `mathlib/Topology/trans_prod_eq_prod_trans`
- Python always-override diagnostic:
  `training/experiments/results/clean_exp08_python_always_decisions_001/summary.tsv`
  failed after 16.05s, with 525 model overrides and 3 no-candidate fallbacks
- native always-override diagnostic:
  `training/experiments/results/clean_exp08_native_decisions_fixed_001/summary.tsv`
  failed after 14.78s, with 540 model overrides before failure
- margin rows after the anchor fix:
  `training/experiments/results/clean_exp08_native_repeat_fixed_001/summary.tsv`
- native `exp08_clean_native_m100`: ok, 3-run average 14.877s,
  -3.60% vs grind
- native `exp08_clean_native_m500`: ok, 3-run average 14.820s,
  -3.20% vs grind
- m100/m500 decision log over 3 runs: 612 model overrides and 960 margin
  fallbacks per threshold
- wider native margin sweep:
  `training/experiments/results/clean_exp08_native_margin_sweep_001/summary.tsv`
- repeated best strict-margin rows:
  `training/experiments/results/clean_exp08_native_margin_repeat_001/summary.tsv`
- native `exp08_clean_native_m5000`: ok, 3-run average 14.700s,
  -2.01% vs grind, with 531 model overrides and 939 margin fallbacks over
  3 runs
- native `exp08_clean_native_m10000`: ok, 3-run average 14.613s,
  -1.41% vs grind, with 459 model overrides and 1005 margin fallbacks over
  3 runs
- `training/experiments/run_timing_matrix.sh` now supports
  `DECISION_LOG=1`, which writes per-row decision logs into the result
  directory and records them in `summary.tsv`
- added a no-run experiment scaffold for neural-policy-first evaluation:
  `training/experiments/neural_policy/`
- the scaffold creates one folder per exp08 policy experiment and evaluates
  ungated per-case Lean success when launched, so the primary metric is the
  neural policy's own solve rate rather than fallback-safe whole-file success
- the neural-policy runners use `TORCH_DEVICE` / `TORCH_DEVICE_LIST` and
  preflight requested CUDA devices before loading data

Hidden-width sweep:

- added three clean-data exp08 variants with hidden widths 128, 64, and 32
- all three variants solved 74/75 held-out cases
- the same failed case remained `mathlib/Topology/trans_prod_eq_prod_trans`
- same-case timing stayed slower than grind, with the 32-wide model closest
  but still not enough to win

Neural-policy EXP-1 held-out run:

- run id: `policy_parallel_gpu_20260510_173100`
- all 12 exp08 policy experiments were launched under
  `training/experiments/neural_policy/experiments/*`
- evaluation is ungated per-case Lean compilation, not margin fallback
- every row was evaluated on the 75-problem held-out split-active benchmark
- clean training data excludes benchmark goal fingerprints
- result summaries:
  `training/experiments/neural_policy/experiments/*/results/ungated_cases_policy_parallel_gpu_20260510_173100/summary.tsv`
- grind per-case baseline:
  `training/benchmarks/case_results/grind_cases_001/summary.tsv`
- grind solved 75/75, mean 4.031s per case, summed real time 302.29s

| Experiment | Test result | Mean solved-case time | Delta vs grind on same solved cases |
| --- | ---: | ---: | ---: |
| `exp08_all_clean` | 61/75 ok | 4.080s | +1.17% slower |
| `exp08_balanced_sources` | 62/75 ok | 4.087s | +1.10% slower |
| `exp08_high_depth_oversample` | 74/75 ok | 4.212s | +4.66% slower |
| `exp08_high_pool_oversample` | 74/75 ok | 4.246s | +5.49% slower |
| `exp08_label_smoothing_005` | 74/75 ok | 4.277s | +6.27% slower |
| `exp08_mathlib_numina` | 74/75 ok | 4.230s | +5.10% slower |
| `exp08_mathlib_only` | 73/75 ok, 1 timeout | 4.189s | +4.16% slower |
| `exp08_mathlib_workbook` | 74/75 ok | 4.237s | +5.28% slower |
| `exp08_numina_only` | 74/75 ok | 4.226s | +4.99% slower |
| `exp08_pool_depth_weighted` | 74/75 ok | 4.220s | +4.85% slower |
| `exp08_workbook_numina` | 74/75 ok | 4.243s | +5.42% slower |
| `exp08_workbook_only` | 74/75 ok | 4.238s | +5.29% slower |

Timing caveat:

- these are per-case `lake env lean` timings with `JOBS=4` and
  `DECISION_LOG=1`
- the evaluations were launched in parallel across experiments, so CPU load
  can affect wall time
- all-case averages for low-solve rows are misleading because failed cases can
  exit early
- use repeated trace-free full-file timing before claiming a model is faster
  than `grind`

Interpretation:

- `GRIND_NO_MODEL=1` is now a clean behavior-control baseline.
- The direct batch runner is the preferred timing check for whole-corpus speed;
  the Python harness remains useful for per-problem diagnostics and failures.
- Margin fallback now delegates to native `Action.splitNext`; rejected model
  decisions should behave like grind.
- Python subprocess inference was the dominant problem for the passing model
  rows. The native exp08 server removes nearly all of that overhead, bringing
  margin-gated exp08 from about 12-13% slower to about 1.5% slower than grind
  in the single-run matrix.
- Among all existing artifacts, the best deployed model candidate is the native
  margin-gated exp08 row. The old richer text/context experiment that passes
  (`exp03_current`) is much too slow for production timing, and most old
  ablations either fail or time out.
- Future training should use `training/data/clean/train_splits.jsonl` or a
  narrower benchmark-excluded clean source. Source split files should remain
  append-only inputs while collectors are running.
- Clean exp08 is safer with margin fallback but still does not beat `grind`.
  Always override is unsafe, and margin fallback still uses the model hundreds
  of times without enough search savings to pay for native inference overhead.
  A very strict margin gate approaches fallback speed, but then it mostly
  abstains; the current model is not creating enough positive search savings.
  The next experiments need to change training objective, data weighting, or
  abstention policy rather than only retraining the same imitation model.

## Open Questions

- Can useful grind internal counters be accessed directly without trace
  formatting?
- What is the exact fallback policy that most closely matches grind's default
  split ordering?
- Should the deployed model return scores for all candidates or only a selected
  anchor?
- How large can the C++ model be before per-split overhead matters?
- Which benchmark suite best predicts real hackathon usefulness: Mathlib,
  workbook, Numina/FineLean, or a split-active mixture?
