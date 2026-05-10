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


/- benchmark 050: numina/Inequalities/inequalities_181071
   grind_collect_splits=7 multi_candidate_steps=5 max_pool_size=4
-/
section split_active_050
open Real Set
open scoped BigOperators

/- 11.31 $|x+1|>2|x+2|$.

Translate the above text into English, keeping the original text's line breaks and format, and output the translation result directly.

11.31 $|x+1|>2|x+2|$. -/
example (x : ℝ) : |x + 1| > 2 * |x + 2| ↔
    x ∈ Ioo (-3) (-5 / 3) := by neural_grind
end split_active_050

