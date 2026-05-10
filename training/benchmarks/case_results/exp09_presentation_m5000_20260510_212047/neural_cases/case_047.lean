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


/- benchmark 047: workbook/workbook_30000_39999/lean_workbook_plus_32045
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_047
example (a b c : ℝ) (h₁ : a * (1/b) = 1) (h₂ : b * (1/c) = 1) : c * (1/a) = 1   := by neural_grind
end split_active_047

