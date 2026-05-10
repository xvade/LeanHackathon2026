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


/- benchmark 016: mathlib/Topology/trans_prod_eq_prod_trans
   grind_collect_splits=6 multi_candidate_steps=6 max_pool_size=13
-/
section split_active_016
open Topology Filter unitInterval Set Function
open ContinuousMap

namespace Path

variable {X Y : Type*} [TopologicalSpace X] [TopologicalSpace Y] {x y z : X} {ι : Type*}

variable (γ : Path x y)

variable {a₁ a₂ a₃ : X} {b₁ b₂ b₃ : Y}

example (γ₁ : Path a₁ a₂) (δ₁ : Path a₂ a₃) (γ₂ : Path b₁ b₂)
    (δ₂ : Path b₂ b₃) : (γ₁.prod γ₂).trans (δ₁.prod δ₂) = (γ₁.trans δ₁).prod (γ₂.trans δ₂) := by neural_grind

end Path
end split_active_016

