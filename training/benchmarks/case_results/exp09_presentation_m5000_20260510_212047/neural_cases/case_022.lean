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


/- benchmark 022: mathlib/Order/Ioo_filter_lt
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=5
-/
section split_active_022
open Function OrderDual
open FinsetInterval

namespace Finset

variable {ι α : Type*} {a a₁ a₂ b b₁ b₂ c x : α}

variable [LinearOrder α]

variable [LocallyFiniteOrder α]

example (a b c : α) : {x ∈ Ioo a b | x < c} = Ioo a (min b c) := by neural_grind

end Finset
end split_active_022

