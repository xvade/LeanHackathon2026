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


/- benchmark 024: mathlib/Algebra/even_sub
   grind_collect_splits=3 multi_candidate_steps=3 max_pool_size=4
-/
section split_active_024
open Nat

namespace Int

variable {m n : ℤ}

example : Even (m - n) ↔ (Even m ↔ Even n) := by neural_grind

end Int
end split_active_024

