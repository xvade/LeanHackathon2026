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


/- benchmark 070: numina/Inequalities/inequalities_115987
   grind_collect_splits=45 multi_candidate_steps=27 max_pool_size=6
-/
section split_active_070
/- 9・173 Let $x, y, z$ be real numbers, prove:
$$
|x|+|y|+|z| \leqslant |x+y-z|+|x-y+z|+|-x+y+z| \text {. }
$$ -/
example (x y z : ℝ) :
    abs x + abs y + abs z ≤ abs (x + y - z) + abs (x - y + z) + abs (-x + y + z) := by neural_grind
end split_active_070

