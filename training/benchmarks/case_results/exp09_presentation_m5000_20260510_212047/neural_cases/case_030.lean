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


/- benchmark 030: workbook/workbook_10000_19999/lean_workbook_plus_10625
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_030
example (a b : ℝ) (h : |a| ≤ b) : -b ≤ a ∧ a ≤ b   := by neural_grind
end split_active_030

