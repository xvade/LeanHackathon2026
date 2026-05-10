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


/- benchmark 027: workbook/workbook_70000_79999/lean_workbook_plus_77164
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_027
example (r₀ r₁ α : ℝ)
  (h₀ : 0 < r₀ ∧ 0 < r₁)
  (h₁ : 0 < α ∧ α ≤ π ∧ α ≠ π / 2)
  (h₂ : r₁ = r₀ * (1 - Real.sin α) / (1 + Real.sin α))
  (h₃ : 0 < Real.sin α ∧ Real.sin α ≠ 1) :
  r₁ / r₀ = (1 - Real.sin α) / (1 + Real.sin α)   := by neural_grind
end split_active_027

