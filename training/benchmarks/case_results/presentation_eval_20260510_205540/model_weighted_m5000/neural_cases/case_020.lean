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


/- benchmark 020: mathlib/Order/compl_Ioc
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=6
-/
section split_active_020
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example : (Ioc a b)ᶜ = Iic a ∪ Ioi b := by neural_grind

end Set
end split_active_020

