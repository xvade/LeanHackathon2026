/-
Fixed split-active benchmark generated from training/data/split_active_benchmark.jsonl.
Proof tactic: neural_grind
Timing variant: trace.grind.split disabled
Do not edit individual examples by hand; regenerate from the JSONL if the benchmark changes.
-/
import Mathlib
import NeuralTactic

set_option maxHeartbeats 400000
set_option linter.unusedVariables false
set_option trace.grind.split false


/- benchmark 035: workbook/workbook_20000_29999/lean_workbook_plus_29828
   grind_collect_splits=23 multi_candidate_steps=15 max_pool_size=5
-/
section split_active_035
example (x y : ℝ) (hx : abs (x + y) + abs (x - y + 1) = 2) : 5 / 6 ≤ abs (2 * x - y) + abs (3 * y - x) ∧ abs (2 * x - y) + abs (3 * y - x) ≤ 21 / 2   := by neural_grind
end split_active_035

