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


/- benchmark 000: mathlib/Logic/swap_apply_ne_self_iff
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_000
open Function

namespace Equiv

variable {α α₁ α₂ β β₁ β₂ γ δ : Sort*}

variable [DecidableEq α]

example {a b x : α} : swap a b x ≠ x ↔ a ≠ b ∧ (x = a ∨ x = b) := by neural_grind

end Equiv
end split_active_000

