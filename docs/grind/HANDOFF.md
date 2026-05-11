# Neural Grind Handoff

Date: 2026-05-10

This is the comprehensive handoff for the current `neural_grind` work. The
active plan is `NEURAL_GRIND_PLAN.md`.

Generated benchmark run directories under `training/benchmarks/case_results/`
are intentionally not checked in. Re-run the benchmark scripts to recreate
those outputs locally.

The repo is intentionally dirty. Do not reset or revert unrelated changes. Some
data files are generated artifacts, and some data-generation jobs may still be
running or appending to source files. Prefer writing derived outputs under new
paths instead of modifying source data in place.

## Objective

The goal is to make real `neural_grind` faster than real `grind` on Lean
compilation while preserving proof success.

Primary metric:

- trace-free end-to-end Lean batch timing on real tactics

Secondary diagnostics:

- compile success/failure
- per-problem timing
- split count where tracing is enabled
- model override rate and fallback rate
- offline ranking agreement

Do not treat similarity to `grind`, `grind_collect`, or `neural_collect` as the
main success metric. Collection tactics are for data and diagnostics.

## Current Benchmark

Fixed benchmark source:

- `training/data/split_active_benchmark.jsonl`

Lean benchmark files:

- `training/benchmarks/split_active.lean`
- `training/benchmarks/split_active_neural_grind.lean`
- `training/benchmarks/split_active_timing_grind.lean`
- `training/benchmarks/split_active_timing_neural_grind.lean`

Benchmark shape:

- 75 total problems
- 25 `mathlib`
- 25 `workbook`
- 25 `numina`
- every problem has at least one `grind_collect` split
- every problem has at least one multi-candidate split

Preferred batch timing command:

```bash
REPEAT=3 TIMEOUT=90 bash training/benchmarks/run_split_active_timing.sh both
```

Use trace-free timing files for speed claims. Use traced files only for
attribution and split-count diagnostics.

## Data Hygiene

The current benchmark should remain fixed. Training data should exclude it.

Relevant files:

- `training/DATA_SPLITS.md`
- `training/collect_benchmark_traces.py`
- `training/filter_training_data.py`
- `training/make_clean_training_data.sh`
- `training/experiments/train_clean_model.sh`

Generate clean data:

```bash
bash training/make_clean_training_data.sh
```

Current clean snapshot:

- benchmark traces: `training/data/split_active_benchmark_traces.jsonl`
- combined clean data: `training/data/clean/train_splits.jsonl`
- `verified_splits.jsonl`: kept 537, dropped 28
- `workbook_splits.jsonl`: kept 4140, dropped 26
- `numina_finelean_splits.jsonl`: kept 3837, dropped 38
- `numina_finelean_v2_splits.jsonl`: kept 7929, dropped 49
- second-pass leak check over clean files dropped 0 records

Important caveat:

- existing experiment `model.pt` files were trained before benchmark exclusion
  was explicit
- treat those results as historical diagnostics
- retrain clean models before making held-out claims

Clean exp08 has now been retrained:

- model: `training/experiments/exp08_num_pool_counts/model_clean.pt`
- native weights:
  `training/experiments/exp08_num_pool_counts/model_clean.native.bin`
- training data: `training/data/clean/train_splits.jsonl`
- decision steps: 15697
- final training accuracy: 93.0%
- trainer was changed to batch examples by candidate-pool size, which makes the
  CUDA run fast enough to use interactively

Future workbook collection:

- `training/collect_workbook.py` now preserves source metadata for future split
  records
- older workbook split records do not have original IDs, so current filtering
  uses benchmark goal fingerprints

## `neural_grind` Controls

Main file:

- `NeuralTactic/NeuralTactic/SplitPolicy.lean`

Runtime controls:

- `GRIND_NO_MODEL=1`: use `neural_grind` tactic loop but delegate splits to
  native `Action.splitNext`
- `GRIND_MODEL=<path>`: model checkpoint or native weight file
- `GRIND_SERVE=<path>`: Python or native inference server
- `GRIND_SERVE_NATIVE=1`: launch `GRIND_SERVE` directly instead of through
  Python
- `GRIND_MARGIN_MILLI=<n>`: only override fallback when model top-1/top-2
  margin is at least `n`
- `GRIND_INCLUDE_EXPR_TEXT=1`: opt into candidate expression pretty-printing
- `GRIND_DECISION_LOG=<path>`: optional JSONL decision log with action,
  reason, margin, and threshold for each split decision

Production defaults:

- candidate `exprText` is off unless explicitly enabled
- rejected model decisions fall back to native `Action.splitNext`
- missing/unusable model responses fall back to native `Action.splitNext`

Build check:

```bash
cd NeuralTactic && lake build
```

This passed after the current changes.

## Benchmark Harnesses

### Python Attribution Harness

File:

- `training/benchmark.py`

Use it for:

- per-problem success/failure
- per-problem errors
- split diagnostics
- quick model debugging

Important options:

- `--benchmark-file training/data/split_active_benchmark.jsonl`
- `--neural-no-model`
- `--no-trace-splits`
- `--margin-milli`
- `--include-expr-text`

Elapsed time is now the primary metric in the Python output, but the direct
Lean batch runner is preferred for final speed claims.

### Direct Lean Batch Timing

File:

- `training/benchmarks/run_split_active_timing.sh`

This runs `lake env lean` directly on full Lean benchmark files and records
`/usr/bin/time` output. This is the preferred throughput benchmark.

Example:

```bash
GRIND_NO_MODEL=1 REPEAT=3 TIMEOUT=90 \
  bash training/benchmarks/run_split_active_timing.sh both
```

### Experiment Matrix

Files:

- `training/experiments/experiments.tsv`
- `training/experiments/run_timing_matrix.sh`
- per-experiment `run.sh` shims under `training/experiments/exp*/run.sh`

Run enabled rows:

```bash
REPEAT=3 TIMEOUT=90 bash training/experiments/run_timing_matrix.sh
```

Run all rows, including disabled historical ablations:

```bash
RUN_DISABLED=1 REPEAT=1 TIMEOUT=90 bash training/experiments/run_timing_matrix.sh
```

Run one row:

```bash
ONLY=exp08_native_m500 REPEAT=3 TIMEOUT=90 \
  bash training/experiments/run_timing_matrix.sh
```

Results go under ignored `training/experiments/results/<stamp>/`.

## Native C++ Inference

Files:

- `NeuralTactic/native/model.cpp`
- `training/export_exp08_native.py`
- `training/experiments/exp08_num_pool_counts/model.native.bin`

Current implementation:

- standalone persistent C++ subprocess server
- same stdin/stdout protocol as Python `serve.py`
- Lean launches it with `GRIND_SERVE_NATIVE=1`

Build/export:

```bash
/home/ec2-user/miniconda3/envs/leanhack/bin/python3 training/export_exp08_native.py
c++ -DNEURAL_GRIND_STANDALONE -O3 -std=c++17 NeuralTactic/native/model.cpp \
  -o training/experiments/exp08_num_pool_counts/native_serve
```

The matrix runner builds `native_serve` automatically for `serve=native:exp08`.

The earlier in-process `@[extern]` path was abandoned for now because
`lake env lean` tactic execution could not resolve the package-local native
symbol reliably. Revisit only if subprocess overhead becomes a bottleneck.

Important native fix:

- native C++ originally parsed candidate anchors through `double`
- large 64-bit Lean anchors lost precision, so native model choices did not
  match Lean candidate anchors
- affected native rows were effectively fallback-only before the fix
- `NeuralTactic/native/model.cpp` now parses anchors as decimal `uint64_t`
- ignore native timing results before this fix when interpreting model quality

## Current Results

No-model control:

- full 75-problem benchmark passes
- split parity with `grind`
- direct batch timing roughly equal to `grind`
- conclusion: custom tactic loop is not the bottleneck

Enabled matrix before native C++:

- `no_model`: ok, roughly equal to `grind`
- ungated cheap models fail on the fixed benchmark
- Python margin-gated exp08 passes but is about 12-13% slower

Enabled matrix with native C++:

- `exp08_native_m100`: ok, about 1-3% slower than `grind` in single-run tests
- `exp08_native_m500`: ok, about 1-3% slower than `grind` in single-run tests
- conclusion: Python/PyTorch subprocess overhead was a major issue, but the
  current model still does not save enough search to beat `grind`

All-artifact matrix:

- `exp03_current` with candidate text passes but is much too slow
- most old disabled ablations fail or time out
- old text/context paths are not production candidates as-is

Clean exp08 matrix:

- single-run summary:
  `training/experiments/results/clean_exp08_001/summary.tsv`
- first repeated native summary:
  `training/experiments/results/clean_exp08_native_repeat_001/summary.tsv`
  should be treated as fallback-contaminated because it predates the native
  anchor parsing fix
- corrected repeated native summary:
  `training/experiments/results/clean_exp08_native_repeat_fixed_001/summary.tsv`
- ungated `exp08_clean`: fail, 19.11s before failure
- ungated failures:
  `mathlib/Topology/trans_prod_eq_prod_trans`,
  `workbook/lean_workbook_plus_13598`
- Python `exp08_clean_m100`: ok, 19.09s, -24.85% vs grind
- Python `exp08_clean_m500`: ok, 19.21s, -25.64% vs grind
- native `exp08_clean_native_m100`: ok, corrected 3-run average 14.877s,
  -3.60% vs grind
- native `exp08_clean_native_m500`: ok, corrected 3-run average 14.820s,
  -3.20% vs grind
- wider native margin sweep:
  `training/experiments/results/clean_exp08_native_margin_sweep_001/summary.tsv`
- repeated strict-margin summary:
  `training/experiments/results/clean_exp08_native_margin_repeat_001/summary.tsv`
- native `exp08_clean_native_m5000`: ok, 3-run average 14.700s,
  -2.01% vs grind, with 531 model overrides and 939 margin fallbacks over
  3 runs
- native `exp08_clean_native_m10000`: ok, 3-run average 14.613s,
  -1.41% vs grind, with 459 model overrides and 1005 margin fallbacks over
  3 runs
- neural-policy experiment scaffold:
  `training/experiments/neural_policy/`
- this scaffold has one folder per experiment and is intended to be launched
  in parallel; it evaluates ungated per-case Lean success, not margin fallback
- use `TORCH_DEVICE=cuda:0` / `TORCH_DEVICE=cuda:1` or
  `TORCH_DEVICE_LIST="cuda:0 cuda:1"` for these experiments; the runners now
  preflight CUDA before loading training data

Completed neural-policy EXP-1 run:

- run id: `policy_parallel_gpu_20260510_173100`
- suite: `training/experiments/neural_policy/`
- first attempt `policy_parallel_20260510_172034` failed all 12 experiments
  before training because CUDA was not visible in the sandboxed launch path
- patched the suite to use `TORCH_DEVICE` / `TORCH_DEVICE_LIST` and CUDA
  preflight checks instead of relying on the generic `DEVICE` variable
- GPU preflight succeeded outside the sandbox for both `cuda:0` and `cuda:1`
- the successful run launched all 12 experiments; the first two were initially
  launched by the queued runner, then the queue parent was stopped and the
  remaining 10 were launched concurrently with the same run id
- do not start another run with this same id unless you intentionally want to
  overwrite or mix logs/results
- all 12 experiments completed on the fixed 75-problem held-out benchmark
- summaries are under
  `training/experiments/neural_policy/experiments/*/results/ungated_cases_policy_parallel_gpu_20260510_173100/summary.tsv`
- models and native weights are under each experiment's `outputs/` directory

Hidden-width sweep:

- added clean-data exp08 variants at hidden widths 128, 64, and 32
- ran them through the existing neural-policy suite with the same CUDA
  preflight and result layout as the earlier exp08 experiments
- all three variants solved 74/75 held-out cases
- the same regression remained: `mathlib/Topology/trans_prod_eq_prod_trans`
- same-case timing improved as width shrank, but even the 32-wide model was
  still slower than `grind`
- conclusion: smaller models are worth testing, but width reduction alone does
  not yet beat `grind`

Held-out success and timing:

- benchmark: `training/data/split_active_benchmark.jsonl`
- clean training manifest:
  `training/data/clean/manifest.json`
- grind per-case baseline:
  `training/benchmarks/case_results/grind_cases_001/summary.tsv`
- grind solved 75/75, mean 4.031s per case, summed real time 302.29s
- neural timing below compares only the cases each model solved against the
  same-case grind timing

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

Timing caveats:

- this run used per-case `lake env lean` execution with `JOBS=4`
- neural rows had `DECISION_LOG=1`, so decision logging is included in the
  timing
- the 12 experiments were evaluated concurrently, so CPU contention may have
  inflated wall-clock time
- all-case averages for low-solve experiments are not meaningful because failed
  cases can exit early
- final speed claims should come from repeated trace-free whole-corpus timing,
  not this parallel case runner

Always-override diagnostics:

- Python always-override:
  `training/experiments/results/clean_exp08_python_always_decisions_001/summary.tsv`
  failed after 16.05s
- Python decision log: 525 model overrides and 3 no-candidate fallbacks
- native always-override after the anchor fix:
  `training/experiments/results/clean_exp08_native_decisions_fixed_001/summary.tsv`
  failed after 14.78s
- native failure: `mathlib/Topology/trans_prod_eq_prod_trans`, e-matching
  round limit
- native m100/m500 decision log over 3 runs: 612 model overrides and 960
  margin fallbacks per threshold

Interpretation:

- native C++ made the experiment meaningful
- the next bottleneck is model quality and override policy
- clean exp08 is safe with margin fallback but still slower than `grind`
- always override is unsafe; the neural policy can drive successful `grind`
  examples into limit failures
- strict margin gates approach fallback speed by abstaining more, but still do
  not create net speedups with the current model
- the next step should change the objective, data weighting, or abstention
  policy; simply retraining the same imitation model was not enough
- the recent hidden-width sweep suggests model-size reduction helps a little,
  but is not sufficient by itself

## Experiment Direction

The expanded experiment program is in `NEURAL_GRIND_PLAN.md`. The most important
near-term tracks are:

1. Clean baseline rebuild
2. Data mixture and weighting
3. Model-size reduction and compression
4. Cost-aware imitation
5. Calibration and abstention
6. Failure-contrast training
7. Rich teacher and distillation
8. Outcome-aware fine-tuning
9. Local branch-cost labels
10. Pool-level cheap models
11. Cheap internal counters
12. Runtime overhead reduction
13. Benchmark expansion

The key principle is that imitation alone is unlikely to beat `grind` by much.
To be faster, the model must either:

- choose fewer or cheaper branches than `grind`
- avoid expensive wrong paths
- abstain almost perfectly when it has no useful improvement
- add less overhead than the search it saves

## Recommended Next Execution

1. Use `DECISION_LOG=1` on timing runs. The matrix runner now writes per-row
   decision logs into the result directory and records the path in
   `summary.tsv`.

2. Run the data-mixture sweep before building more complex models. It is the
   cheapest way to find whether the current architecture is data-limited or
   objective-limited.

3. After size reduction, implement cost-aware imitation and failure-contrast
   training.

4. Re-test clean native rows after each objective/data change with
   `REPEAT >= 3`.

## Files To Know

Core Lean:

- `NeuralTactic/NeuralTactic/SplitPolicy.lean`
- `NeuralTactic/NeuralTactic/CollectTactic.lean`
- `NeuralTactic/native/model.cpp`

Benchmark and data:

- `training/data/split_active_benchmark.jsonl`
- `training/data/clean/train_splits.jsonl`
- `training/DATA_SPLITS.md`
- `training/benchmarks/run_split_active_timing.sh`

Training and serving:

- `training/experiments/exp08_num_pool_counts/train.py`
- `training/experiments/exp08_num_pool_counts/serve.py`
- `training/export_exp08_native.py`
- `training/experiments/train_clean_model.sh`

Experiment orchestration:

- `training/experiments/experiments.tsv`
- `training/experiments/run_timing_matrix.sh`

Docs:

- `NEURAL_GRIND_PLAN.md`
- `NEURAL_GRIND_HANDOFF.md`

## Operational Notes

- Do not stop running data-generation processes unless explicitly asked.
- Do not edit source data files in place while collectors may be appending.
- Use `training/data/clean/` for derived training snapshots.
- Use `REPEAT >= 3` before interpreting small timing differences.
- Any model row that fails compilation is a real regression.
- Any rejected model decision should fall back to native `Action.splitNext`.
- Avoid production features requiring pretty-printing unless a benchmark proves
  the cost is worth it.
