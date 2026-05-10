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


/- benchmark 066: numina/Inequalities/inequalities_319875
   grind_collect_splits=15 multi_candidate_steps=7 max_pool_size=4
-/
section split_active_066
open Real Set
open scoped BigOperators

/- 4. The coordinates of point $M(x, y)$ satisfy $|x+y|<|x-y|$. Then the quadrant in which point $M$ is located is ( ).
(A) 1,3
(B) 2,4
(C) 1,2
(D) 3,4 -/
example (x y : ℝ) (h : abs (x + y) < abs (x - y)) :
    (x < 0 ∧ y > 0) ∨ (x > 0 ∧ y < 0) := by neural_grind
end split_active_066

