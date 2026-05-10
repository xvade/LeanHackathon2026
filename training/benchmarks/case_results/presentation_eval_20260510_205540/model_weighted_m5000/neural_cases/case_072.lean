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


/- benchmark 072: numina/unknown/algebra_8833
   grind_collect_splits=4 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_072
/- Solve the equation
$$\left(x^2 + 3x - 4\right)^3 + \left(2x^2 - 5x + 3\right)^3 = \left(3x^2 - 2x - 1\right)^3.$$ -/
example (x : ℝ) :
    (x ^ 2 + 3 * x - 4)^3 + (2 * x^2 - 5 * x + 3)^3 =
    (3 * x^2 - 2 * x - 1)^3 ↔
    x = -4 ∨ x = -1 / 3 ∨ x = 1 ∨ x = 3 / 2 := by neural_grind
end split_active_072

