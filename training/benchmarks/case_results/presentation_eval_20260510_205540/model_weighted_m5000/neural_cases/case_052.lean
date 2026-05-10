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


/- benchmark 052: numina/Inequalities/inequalities_205242
   grind_collect_splits=21 multi_candidate_steps=15 max_pool_size=6
-/
section split_active_052
/- Galochkin A.i.

Prove that if for numbers $a, b$ and $c$ the inequalities $|a-b| \geq|c|,|b-c| \geq|a|,|c-a| \geq|b|$ hold, then one of these numbers is equal to the sum of the other two. -/
example {a b c : ℝ} (h₀ : abs (a - b) ≥ abs c) (h₁ : abs (b - c) ≥ abs a)
    (h₂ : abs (c - a) ≥ abs b) :
    a = b + c ∨ b = a + c ∨ c = a + b := by neural_grind
end split_active_052

