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


/- benchmark 065: numina/Inequalities/inequalities_220639
   grind_collect_splits=12 multi_candidate_steps=7 max_pool_size=8
-/
section split_active_065
example (a b c : ℕ) (h₀ : a + b + c = 60) (h₁ : a ≤ b + c)
    (h₂ : b ≤ a + c) (h₃ : c ≤ a + b) (h₄ : |(a : ℤ) - b| ≥ 3) (h₅ : |(b : ℤ) - c| ≥ 3)
    (h₆ : |(c : ℤ) - a| ≥ 3) :
    min (min a b) c ∈ Finset.Icc 3 17 := by neural_grind
end split_active_065

