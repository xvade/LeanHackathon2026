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


/- benchmark 073: numina/Algebra/algebra_325177
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_073
/- Example 3 Solve the equation
$$
\frac{1}{6 x-5}-\frac{1}{5 x+4}=\frac{1}{5 x-4}-\frac{1}{4 x+5} .
$$ -/
example (x : ℝ) (hx : 6*x-5≠0 ∧ 5*x+4≠0 ∧ 5*x-4≠0 ∧ 4*x+5≠0) :
    1/(6*x-5) - 1/(5*x+4) = 1/(5*x-4) - 1/(4*x+5) ↔ x=9 ∨ x=0 ∨ x=1 := by neural_grind
end split_active_073

