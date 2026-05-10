# Data Splits

The fixed benchmark is:

- `training/data/split_active_benchmark.jsonl`

Keep this file stable unless we intentionally change the benchmark. Training
data must exclude these problems.

Current benchmark shape:

- 75 total problems
- 25 `mathlib`, 25 `workbook`, 25 `numina`
- every problem has at least 1 `grind_collect` split
- every problem has at least 1 multi-candidate split

## Clean Training Snapshot

Generate a clean training snapshot with:

```bash
bash training/make_clean_training_data.sh
```

This writes derived files under `training/data/clean/` and does not modify any
source data file. That matters because some data-generation jobs may still be
writing to source JSONL files.

The script:

1. collects benchmark traces into
   `training/data/split_active_benchmark_traces.jsonl`
2. fingerprints benchmark goals
3. filters source split files into `training/data/clean/`
4. writes `training/data/clean/train_splits.jsonl` as the combined clean
   training file

Use the combined clean file for future model training unless a specific
experiment needs a narrower data source.

For an existing experiment directory, train a clean model without overwriting
the historical `model.pt` with:

```bash
bash training/experiments/train_clean_model.sh exp08_num_pool_counts
```

By default this writes `model_clean.pt` and `train_clean.log` inside the
experiment directory.

Current clean snapshot:

```text
verified_splits.jsonl:           kept=537  dropped=28  total=565
workbook_splits.jsonl:           kept=4140 dropped=26  total=4166
numina_finelean_splits.jsonl:    kept=3837 dropped=38  total=3875
numina_finelean_v2_splits.jsonl: kept=7929 dropped=49  total=7978
```

A second pass over `training/data/clean/` dropped 0 records, so the current
snapshot has no remaining benchmark goal fingerprints under this check.

## Current Caveat

Historical models in `training/experiments/` were trained before this split was
made explicit. Treat their benchmark results as historical diagnostics until
the models are retrained from `training/data/clean/train_splits.jsonl` or from
another explicitly benchmark-excluded dataset.
