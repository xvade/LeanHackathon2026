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


/- benchmark 051: numina/Algebra/algebra_135946
   grind_collect_splits=8 multi_candidate_steps=2 max_pool_size=2
-/
section split_active_051
/- Find all real numbers $x, y, z$ satisfying:

$$
\left\{\begin{array}{l}
(x+1) y z=12 \\
(y+1) z x=4 \\
(z+1) x y=4
\end{array}\right.
$$ -/
example {x y z : ℝ} (h₀ : (x + 1) * y * z = 12) (h₁ : (y + 1) * z * x = 4)
    (h₂ : (z + 1) * x * y = 4) :
    (x = 2 ∧ y = -2 ∧ z = -2) ∨ (x = 1 / 3 ∧ y = 3 ∧ z = 3) := by neural_grind
end split_active_051

