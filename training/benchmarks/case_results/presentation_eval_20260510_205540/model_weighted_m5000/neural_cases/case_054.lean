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


/- benchmark 054: numina/Other/other_269148
   grind_collect_splits=12 multi_candidate_steps=11 max_pool_size=7
-/
section split_active_054
example :
   (|(1.01 : ℝ) - 1| < |(0.50 : ℝ) - 1| ∧
    |(1.01 : ℝ) - 1| < |(0.90 : ℝ) - 1| ∧
    |(1.01 : ℝ) - 1| < |(0.95 : ℝ) - 1| ∧
    |(1.01 : ℝ) - 1| < |(1.15 : ℝ) - 1|) := by neural_grind
end split_active_054

