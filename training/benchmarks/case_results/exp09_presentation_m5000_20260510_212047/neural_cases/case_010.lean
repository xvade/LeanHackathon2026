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


/- benchmark 010: mathlib/Algebra/odd_add'
   grind_collect_splits=3 multi_candidate_steps=3 max_pool_size=8
-/
section split_active_010
namespace Int

variable {m n : ℤ}

example : Odd (m + n) ↔ (Odd n ↔ Even m) := by neural_grind

end Int
end split_active_010

