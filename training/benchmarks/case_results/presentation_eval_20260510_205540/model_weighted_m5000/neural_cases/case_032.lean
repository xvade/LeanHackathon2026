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


/- benchmark 032: workbook/workbook_60000_69999/lean_workbook_plus_61780
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=3
-/
section split_active_032
example (x y z : ℝ)
  (h₀ : 0 < x ∧ 0 < y ∧ 0 < z)
  (h₁ : x^2 + y^2 = z^2)
  (h₂ : y^2 + z^2 = x^2)
  (h₃ : z^2 + x^2 = y^2) :
  (x^2 + y^2 + z^2) / x + (x^2 + y^2 + z^2) / y + (x^2 + y^2 + z^2) / z ≥ 2 * (x + y + z)   := by neural_grind
end split_active_032

