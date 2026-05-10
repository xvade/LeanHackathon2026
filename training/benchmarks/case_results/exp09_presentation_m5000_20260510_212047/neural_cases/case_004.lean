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


/- benchmark 004: mathlib/Data/biUnion_singleton_eq_self
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_004
namespace Finset

variable {α β γ : Type*} {s s₁ s₂ : Finset α} {t t₁ t₂ : α → Finset β}

variable [DecidableEq β]

example [DecidableEq α] : s.biUnion (singleton : α → Finset α) = s := by neural_grind

end Finset
end split_active_004

