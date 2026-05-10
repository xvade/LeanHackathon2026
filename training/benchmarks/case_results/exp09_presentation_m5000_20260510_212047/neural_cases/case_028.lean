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


/- benchmark 028: workbook/workbook_50000_59999/lean_workbook_plus_57616
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=4
-/
section split_active_028
example : ∀ A : Set (ℕ → ℝ), A = {x | ∀ n : ℕ, 0 ≤ x n} ↔ ∀ x : ℕ → ℝ, x ∈ A ↔ ∀ n : ℕ, 0 ≤ x n   := by neural_grind
end split_active_028

