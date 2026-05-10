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


/- benchmark 060: numina/unknown/algebra_3430
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_060
/- Given that $x_{1}$ and $x_{2}$ are the two real roots of the quadratic equation $x^{2}-8x+k=0$, and $\dfrac{1}{x_{1}}+\dfrac{1}{x_{2}}=\dfrac{2}{3}$. Find the value of $k$. -/
example {x1 x2 k : ℝ} (hx1 : x1^2 - 8 * x1 + k = 0) (hx2 : x2^2 - 8 * x2 + k = 0)
    (hroots : x1 ≠ x2) (hsum : 1 / x1 + 1 / x2 = 2 / 3) : k = 12 := by neural_grind
end split_active_060

