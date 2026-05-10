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


/- benchmark 036: workbook/workbook_10000_19999/lean_workbook_plus_13598
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_036
example (a b : ℝ) (ha : a ≠ 0) : a^2 / (a^2 + a * b + b^2) = 1 / (1 + b / a + b^2 / a^2)   := by neural_grind
end split_active_036

