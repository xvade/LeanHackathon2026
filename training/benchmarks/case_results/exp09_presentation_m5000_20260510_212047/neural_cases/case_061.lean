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


/- benchmark 061: numina/NaN/algebra_272103
   grind_collect_splits=3 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_061
/- If $x$ and $y$ are positive real numbers with $\frac{1}{x+y}=\frac{1}{x}-\frac{1}{y}$, what is the value of $\left(\frac{x}{y}+\frac{y}{x}\right)^{2} ?$ -/
example (x y : ℝ) (hx : 0 < x) (hy : 0 < y) (h : 1 / (x + y) = 1 / x - 1 / y) :
    (x / y + y / x) ^ 2 = 5 := by neural_grind
end split_active_061

