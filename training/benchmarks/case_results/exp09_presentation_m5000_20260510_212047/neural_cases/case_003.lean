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


/- benchmark 003: mathlib/Data/image_union
   grind_collect_splits=6 multi_candidate_steps=4 max_pool_size=5
-/
section split_active_003
open Function Set

namespace Set

variable {α β γ : Type*} {ι : Sort*}

variable {f : α → β} {s t : Set α}

example (f : α → β) (s t : Set α) : f '' (s ∪ t) = f '' s ∪ f '' t := by neural_grind

end Set
end split_active_003

