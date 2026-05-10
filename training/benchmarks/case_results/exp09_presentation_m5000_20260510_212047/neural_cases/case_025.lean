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


/- benchmark 025: workbook/workbook_30000_39999/lean_workbook_plus_32662
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_025
example (x : ℝ) (hx : x + 1/x = 21) : x^4 + 1/(x^4) = 192719   := by neural_grind
end split_active_025

