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


/- benchmark 015: mathlib/Order/Ioo_inter_Ioo
   grind_collect_splits=8 multi_candidate_steps=6 max_pool_size=7
-/
section split_active_015
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example : Ioo a₁ b₁ ∩ Ioo a₂ b₂ = Ioo (a₁ ⊔ a₂) (b₁ ⊓ b₂) := by neural_grind

end Set
end split_active_015

