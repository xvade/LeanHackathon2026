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


/- benchmark 005: mathlib/Data/image_erase
   grind_collect_splits=5 multi_candidate_steps=3 max_pool_size=4
-/
section split_active_005
open Multiset
open Function

namespace Finset

variable {α β γ : Type*}

variable [DecidableEq β]

variable {f g : α → β} {s : Finset α} {t : Finset β} {a : α} {b c : β}

example [DecidableEq α] {f : α → β} (hf : Injective f) (s : Finset α) (a : α) :
    (s.erase a).image f = (s.image f).erase (f a) := by neural_grind

end Finset
end split_active_005

