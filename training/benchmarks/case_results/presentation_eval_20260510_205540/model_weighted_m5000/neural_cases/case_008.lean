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


/- benchmark 008: mathlib/Order/Iic_union_Icc
   grind_collect_splits=7 multi_candidate_steps=5 max_pool_size=7
-/
section split_active_008
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example (h : min c d ≤ b) : Iic b ∪ Icc c d = Iic (max b d) := by neural_grind

end Set
end split_active_008

