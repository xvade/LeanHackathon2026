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


/- benchmark 019: mathlib/Data/insert_eq_of_mem
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_019
open Function

namespace Set

variable {α β : Type*} {s t : Set α} {a b : α}

example {a : α} {s : Set α} (h : a ∈ s) : insert a s = s := by neural_grind

end Set
end split_active_019

