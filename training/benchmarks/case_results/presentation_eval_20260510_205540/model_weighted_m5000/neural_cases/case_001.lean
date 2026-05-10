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


/- benchmark 001: mathlib/Data/insert_comm
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=7
-/
section split_active_001
open Multiset Subtype Function

namespace Finset

variable {α : Type*} {β : Type*}

variable [DecidableEq α] {s t : Finset α} {a b : α} {f : α → β}

example (a b : α) (s : Finset α) : insert a (insert b s) = insert b (insert a s) := by neural_grind

end Finset
end split_active_001

