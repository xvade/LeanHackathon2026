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


/- benchmark 055: numina/Inequalities/inequalities_223947
   grind_collect_splits=21 multi_candidate_steps=15 max_pool_size=6
-/
section split_active_055
/- 11. Prove: For any real numbers $x, y, z$, the following three inequalities cannot all hold simultaneously: $|x|<|y-z|$, $|y|<|z-x|$, $|z|<|x-y|$. -/
example (x y z : ℝ) :
    ¬(|x| < |y - z| ∧ |y| < |z - x| ∧ |z| < |x - y|) := by neural_grind
end split_active_055

