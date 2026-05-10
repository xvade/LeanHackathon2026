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


/- benchmark 044: workbook/workbook_80000_89999/lean_workbook_plus_82549
   grind_collect_splits=3 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_044
example (α β γ : ℝ) (h₁ : α * β + β * γ + γ * α = 0) (h₂ : α * β * γ = 1) : 1 / γ = 1 / -α + 1 / -β   := by neural_grind
end split_active_044

