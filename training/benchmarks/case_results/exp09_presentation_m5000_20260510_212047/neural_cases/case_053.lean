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


/- benchmark 053: numina/unknown/algebra_4744
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_053
/- Solve the equation: $\frac{1}{x^{2}+3x}+ \frac{1}{x^{2}+9x+18}+ \frac{1}{x^{2}+15x+54}= \frac{3}{2x+18}$, $x=$ ___          ___ . -/
example (x : ℝ) (hx : x^2 + 3 * x ≠ 0 ∧ x^2 + 9 * x + 18 ≠ 0 ∧ x^2 + 15 * x + 54 ≠ 0) :
    1 / (x^2 + 3 * x) + 1 / (x^2 + 9 * x + 18) + 1 / (x^2 + 15 * x + 54) = 3 / (2 * x + 18) ↔ x = 2 := by neural_grind
end split_active_053

