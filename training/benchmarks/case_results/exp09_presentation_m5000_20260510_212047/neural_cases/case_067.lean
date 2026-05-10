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


/- benchmark 067: numina/Algebra/algebra_218509
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_067
/- 2. A person travels by boat along the river Drim from Struga to Globocica and back. The distance between Struga and Globocica is $18 \mathrm{~km}$, and he traveled in total 5 hours. What is the speed of the river Drim, if the person traveled $4 \mathrm{~km}$ downstream and $2 \mathrm{~km}$ upstream in the same time? -/
example (v : ℝ) (h : v > 0) (h1 : 18 / (v + w) + 18 / (v - w) = 5)
    (h2 : 4 / (v + w) = 2 / (v - w)) :
    w = 2.7 := by neural_grind
end split_active_067

