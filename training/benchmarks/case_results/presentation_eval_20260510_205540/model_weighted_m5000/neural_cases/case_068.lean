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


/- benchmark 068: numina/Number Theory/number_theory_111868
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_068
/- ## 5.1.

$1_{16}{ }^{\circ}$. Prove that the divisibility of a natural number by 2 is equivalent to the last digit being even.

When in mathematics it is said that one statement is equivalent to another, in this case - one divisibility is equivalent to another, it means the following: from one divisibility follows the other, and from the other follows the first.

Instead of the word "equivalent," it is also said that the first divisibility is satisfied if and only if (or in the case and only in the case) the second is satisfied. -/
example (n : ℕ) : 2 ∣ n ↔ Even (n % 10) := by neural_grind
end split_active_068

