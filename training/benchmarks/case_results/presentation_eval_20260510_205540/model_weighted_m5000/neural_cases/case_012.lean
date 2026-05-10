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


/- benchmark 012: mathlib/Order/min_lt_min_left_iff
   grind_collect_splits=8 multi_candidate_steps=4 max_pool_size=3
-/
section split_active_012
variable {α : Type u} {β : Type v}

variable [LinearOrder α] [LinearOrder β] {f : α → β} {s : Set α} {a b c d : α}

example : min a c < min b c ↔ a < b ∧ a < c := by neural_grind
end split_active_012

