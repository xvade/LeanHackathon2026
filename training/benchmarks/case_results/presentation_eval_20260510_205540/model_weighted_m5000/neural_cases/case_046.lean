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


/- benchmark 046: workbook/workbook_50000_59999/lean_workbook_plus_54147
   grind_collect_splits=5 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_046
example (M x: ℝ) (g : ℝ → ℝ) (h₁ : |g x - M| < |M| / 2) : |g x| > |M| / 2   := by neural_grind
end split_active_046

