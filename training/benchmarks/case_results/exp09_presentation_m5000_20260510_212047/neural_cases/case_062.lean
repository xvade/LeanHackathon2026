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


/- benchmark 062: numina/Algebra/algebra_242442
   grind_collect_splits=5 multi_candidate_steps=2 max_pool_size=2
-/
section split_active_062
/- Problem 5. Solve the system of equations

$$
\left\{\begin{array}{l}
x^{2}=(y-z)^{2}-3 \\
y^{2}=(z-x)^{2}-7 \\
z^{2}=(x-y)^{2}+21
\end{array}\right.
$$ -/
example {x y z : ℝ}
    (h1 : x^2 = (y - z)^2 - 3) (h2 : y^2 = (z - x)^2 - 7) (h3 : z^2 = (x - y)^2 + 21) :
    (x = -1 ∧ y = -3 ∧ z = -5) ∨ (x = 1 ∧ y = 3 ∧ z = 5) := by neural_grind
end split_active_062

