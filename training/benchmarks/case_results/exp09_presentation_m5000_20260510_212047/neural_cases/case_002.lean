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


/- benchmark 002: mathlib/Algebra/even_sign_iff
   grind_collect_splits=4 multi_candidate_steps=4 max_pool_size=3
-/
section split_active_002
namespace Int

variable {m n : ℤ}

example {z : ℤ} : Even z.sign ↔ z = 0 := by neural_grind

end Int
end split_active_002

