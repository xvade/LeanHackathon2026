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


/- benchmark 059: numina/Algebra/algebra_97650
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_059
/- Real numbers $x$ and $y$ satisfy $x + y = 4$ and $x \cdot y = -2$. What is the value of 
\[x + \frac{x^3}{y^2} + \frac{y^3}{x^2} + y?\]
$\textbf{(A)}\ 360\qquad\textbf{(B)}\ 400\qquad\textbf{(C)}\ 420\qquad\textbf{(D)}\ 440\qquad\textbf{(E)}\ 480$ -/
example {x y : ℝ} (h₀ : x + y = 4) (h₁ : x * y = -2) :
    x + x^3 / y^2 + y^3 / x^2 + y = 440 := by neural_grind
end split_active_059

