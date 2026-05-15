#!/bin/bash
# Quick reference for data generation workflow

cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════╗
║           Neural Grind: Data Generation Quick Reference               ║
╚═══════════════════════════════════════════════════════════════════════╝

## SETUP (one-time)

# 1. Install AXLE client
pip install axiom-axle

# 2. Configure credentials
cp training/.env.example training/.env
# Edit training/.env with your AXLE_API_KEY

# 3. Download all datasets
cd training/data
bash download_datasets.sh
cd ..

## PHASE 1: VERIFY WITH GRIND (via AXLE)

Run these in parallel (different terminals):

  # Terminal 1: Lean Workbook (82k theorems, ~5% success = 4,169 solved)
  python3 solve_multi_source.py --source lean_workbook

  # Terminal 2: NuminaMath (104k theorems)
  python3 solve_multi_source.py --source numina_lean

  # Terminal 3: Herald (580k theorems - very large!)
  python3 solve_multi_source.py --source herald --limit 10000  # sample first

  # Terminal 4: FineLeanCorpus (509k theorems)
  python3 solve_multi_source.py --source finelean

Resume: Just re-run the same command; it skips already-solved IDs.

Outputs: *_grind_solved_verified.jsonl files

## PHASE 2: EXTRACT SPLIT DECISIONS (grind_collect)

After verification completes for a source:

  python3 collect_verified.py \
    --input workbook_grind_solved_verified.jsonl \
    --out data/workbook_splits.jsonl

  python3 collect_verified.py \
    --input numina_grind_solved_verified.jsonl \
    --out data/numina_splits.jsonl

  # ... repeat for herald, finelean

Outputs: training/data/*_splits.jsonl files with split traces

## PHASE 3: COMBINE TRAINING DATA

After extracting splits from all sources:

  bash make_clean_training_data.sh

This:
  - Deduplicates across sources
  - Removes benchmark problems (so they stay clean)
  - Writes combined file: data/clean/train_splits.jsonl

## PHASE 4: TRAIN MODEL

  python3 train.py --data data/clean/train_splits.jsonl

Or benchmark existing model:

  python3 benchmark.py --n 3 --workers 8 --timeout 60

## MONITORING PROGRESS

Check verification progress:
  wc -l *.jsonl  # Count solved per source
  tail -f *.jsonl  # Watch latest solves

Expected success rates:
  - Lean Workbook: ~5% (4,169 / 82,876)
  - NuminaMath: unknown (test first with --limit)
  - Herald: unknown (test first with --limit)
  - FineLeanCorpus: unknown (test first with --limit)

## TROUBLESHOOTING

Q: Script crashes with "AXLE credentials not found"
A: Make sure training/.env exists and has AXLE_API_KEY set

Q: AXLE requests timeout or fail
A: Increase TIMEOUT_S in solve_multi_source.py (or temporarily reduce CONCURRENCY)

Q: Resume from middle of verification
A: Re-run same command; already-solved IDs are automatically skipped

Q: Only test a small subset
A: Use --limit flag:
   python3 solve_multi_source.py --source numina_lean --limit 100

## CUSTOMIZATION

Edit solve_multi_source.py top-level constants:
  CONCURRENCY = 32      # parallel AXLE requests
  TIMEOUT_S = 30.0      # seconds per attempt
  VARIANTS = [...]      # grind variants to try (cascade order)

Add new datasource:
  1. Determine field names (id, formal_statement, metadata)
  2. Add entry to DATASOURCES dict with three extractor functions
  3. Ensure input file has correct path and format
  4. Run: python3 solve_multi_source.py --source <name>

EOF
