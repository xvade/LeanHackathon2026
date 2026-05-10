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


/- benchmark 058: numina/Number Theory/algebra_635522
   grind_collect_splits=3 multi_candidate_steps=3 max_pool_size=157
-/
section split_active_058
set_option maxHeartbeats 800000
example (n1 n2 n3 a1 a2 a3 a4 d1 d2 d3 d4 : ℕ) (h1 : 0 < a1) (h2 : a1 < a2) (h3 : a2 < a3) (h4 : a3 < a4) (h5 : a4 ≤ 9) (hn1 : n1 = 1000 * a1 + 100 * a2 + 10 * a3 + a4) (hn2 : n2 = 1000 * a4 + 100 * a3 + 10 * a2 + a1) (hn3 : n3 = 1000 * d1 + 100 * d2 + 10 * d3 + d4) (hd1 : 0 < d1 ∧ d1 < 10) (hd2 : 0 < d2 ∧ d2 < 10) (hd3 : 0 < d3 ∧ d3 < 10) (hd4 : 0 < d4 ∧ d4 < 10) (h : (d1, d2, d3, d4) ∈ ({(a1, a2, a3, a4), (a1, a2, a4, a3), (a1, a3, a2, a4), (a1, a4, a2, a3), (a1, a3, a4, a2), (a1, a4, a3, a2), (a2, a1, a3, a4), (a2, a1, a4, a3), (a3, a1, a2, a4), (a4, a1, a2, a3), (a3, a1, a4, a2), (a4, a1, a3, a2), (a3, a2, a1, a4), (a4, a2, a1, a3), (a2, a3, a1, a4), (a2, a4, a1, a3), (a4, a3, a1, a2), (a3, a4, a1, a2), (a4, a2, a3, a1), (a3, a2, a4, a1), (a4, a3, a2, a1), (a3, a4, a2, a1), (a2, a3, a4, a1), (a2, a4, a3, a1)} : Finset (ℕ × ℕ × ℕ × ℕ))) (hsum : n1 + n2 + n3 = 6798) : min (min n1 n2) n3 = 1234 := by neural_grind
end split_active_058

