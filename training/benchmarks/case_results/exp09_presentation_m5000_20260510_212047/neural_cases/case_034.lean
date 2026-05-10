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


/- benchmark 034: workbook/workbook_30000_39999/lean_workbook_plus_31182
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_034
example (x y: ℝ) : (x + 1) * (y + 1) ≥ 4 * Real.sqrt (x * y) ↔ x * y + x + y + 1 ≥ 4 * Real.sqrt (x * y)   := by neural_grind
end split_active_034

