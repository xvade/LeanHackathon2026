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


/- benchmark 040: workbook/workbook_70000_79999/lean_workbook_plus_75593
   grind_collect_splits=17 multi_candidate_steps=17 max_pool_size=26
-/
section split_active_040
example (n : ℕ) (b : ℕ → ℕ) (h₁ : b 0 = 5) (h₂ : ∀ n, b (n + 1) - b n = (n + 6).choose 4) : b (n + 1) = b n + (n + 6).choose 4   := by neural_grind
end split_active_040

