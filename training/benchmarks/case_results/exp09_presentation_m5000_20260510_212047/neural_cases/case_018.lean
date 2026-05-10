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


/- benchmark 018: mathlib/Data/subset_singleton_iff
   grind_collect_splits=5 multi_candidate_steps=4 max_pool_size=3
-/
section split_active_018
open Multiset Subtype Function

namespace Finset

variable {α : Type*} {β : Type*}

variable {s : Finset α} {a b : α}

example {s : Finset α} {a : α} : s ⊆ {a} ↔ s = ∅ ∨ s = {a} := by neural_grind

end Finset
end split_active_018

