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


/- benchmark 006: mathlib/Data/support_subset_iff
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_006
open Finset Function

namespace Finsupp

variable {α β ι M N O G H : Type*}

variable [Zero M]

example {s : Set α} {f : α →₀ M} :
    ↑f.support ⊆ s ↔ ∀ a ∉ s, f a = 0 := by neural_grind

end Finsupp
end split_active_006

