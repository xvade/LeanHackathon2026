# `solve_workbook.py` — Lean-Workbook-Plus problems solvable by `grind`

Tries every problem in the `lean_workbook_plus` split of
[`internlm/Lean-Workbook`](https://huggingface.co/datasets/internlm/Lean-Workbook)
against AXLE. For each one, it replaces `:= by sorry` with `:= by grind`,
ships the snippet to AXLE for elaboration, and only keeps the cases where
AXLE returns `okay=True`. If plain `grind` fails, it falls back to
`grind only`, then `grind [simp]` (cascade), and the first variant that
closes the goal is recorded.

The output file `workbook_grind_solved_verified.jsonl` is the
AXLE-verified subset — each row's `solved_formal_statement` actually
elaborates and `grind` actually closes the goal.

## Output schema (one JSON record per line)

| field                       | what it is                                                  |
| --------------------------- | ----------------------------------------------------------- |
| `id`                        | `lean_workbook_plus_<n>` from the upstream dataset          |
| `split`                     | always `"lean_workbook_plus"`                               |
| `natural_language_statement`| original problem text (LaTeX-y)                             |
| `answer`                    | the canonical answer if the dataset has one (often `null`)  |
| `tags`                      | upstream topic tags                                         |
| `original_formal_statement` | the original `theorem ... := by sorry`                      |
| `grind_call`                | which variant won: `grind`, `grind only`, `grind [simp]`    |
| `solved_formal_statement`   | the original statement with `sorry` swapped for `grind_call`|
| `axle_environment`          | the AXLE env string used (e.g. `lean-4.29.0`)               |
| `elapsed_s`                 | seconds AXLE spent elaborating                              |

To turn one record into a runnable `.lean` file:

```text
import Mathlib

<solved_formal_statement>
```

## Reproducing the file

1. Install the AXLE Python client:
   ```
   pip install axiom-axle
   ```
2. Copy `.env.example` to `.env` and fill in your `AXLE_API_KEY`. The
   environment value (`AXLE_ENVIRONMENT=lean-4.29.0`) is the most recent
   AXLE Lean toolchain that exists at time of writing — bump as new ones
   are released.
3. Download the upstream dataset into `data/`:
   ```
   mkdir -p data
   curl -L -o data/lean_workbook.json \
     https://huggingface.co/datasets/internlm/Lean-Workbook/resolve/main/lean_workbook.json
   ```
4. Run:
   ```
   python -u solve_workbook.py
   ```
   Progress streams to stdout; solved records append to
   `workbook_grind_solved_verified.jsonl` as they're found. Re-running is
   safe — already-solved ids are skipped.

`python -u solve_workbook.py 200` runs only the first 200 problems
(useful for a smoke test).

## Knobs in the script

- `CONCURRENCY` — number of in-flight AXLE requests (default 8).
- `TIMEOUT_S` — per-attempt timeout in seconds (default 30). A problem
  that times out on plain `grind` will still be retried with `grind only`
  and `grind [simp]`, so worst-case wall time per problem is ~3×.
- `VARIANTS` — the cascade order. Add or remove entries to change which
  grind invocations are tried, in what order.

## Numbers from the published run

- Total problems tried: **82,876**
- Solved: **4,169** (5.0%)
- AXLE environment: `lean-4.29.0`
- Almost all wins are plain `by grind`; cascade variants rarely add new
  solves but cost roughly nothing on already-failing problems because
  `grind` returns failure quickly.
