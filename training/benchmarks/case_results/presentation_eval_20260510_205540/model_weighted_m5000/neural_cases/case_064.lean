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


/- benchmark 064: numina/Inequalities/inequalities_190982
   grind_collect_splits=21 multi_candidate_steps=15 max_pool_size=6
-/
section split_active_064
/- 8, |
| :---: | :---: | :---: |
|  | Factorization |  |
|  | Proof by contradiction |  |

Prove that for no numbers $x, y, t$ can the three inequalities $|x|<|y-t|,|y|<|t-x|,|t|<|x-y|$ all be satisfied simultaneously. -/
example (x y t : ℝ) :
    ¬(abs x < abs (y - t) ∧ abs y < abs (t - x) ∧ abs t < abs (x - y)) := by neural_grind
end split_active_064

