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


/- benchmark 074: numina/Inequalities/inequalities_131719
   grind_collect_splits=12 multi_candidate_steps=7 max_pool_size=4
-/
section split_active_074
open Real Set

/- 1. Find all real numbers $x$ for which the inequality

$$
|||2-x|-x|-8| \leq 2008
$$

holds. -/
example (x : ℝ) :
    abs (abs (abs (2 - x) - x) - 8) ≤ 2008 ↔ x ≥ -1007 := by neural_grind
end split_active_074
