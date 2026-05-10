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


/- benchmark 069: numina/Other/other_71584
   grind_collect_splits=3 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_069
/- A harmonic progression is a sequence of numbers such that their reciprocals are in arithmetic progression.
Let $S_n$ represent the sum of the first $n$ terms of the harmonic progression; for example $S_3$ represents the sum of the first three terms.  If the first three terms of a harmonic progression are $3,4,6$, then:
$ \textbf{(A)}\ S_4=20 \qquad\textbf{(B)}\ S_4=25\qquad\textbf{(C)}\ S_5=49\qquad\textbf{(D)}\ S_6=49\qquad\textbf{(E)}\ S_2=\frac12 S_4 $ -/
example (a d : ℚ) (h₀ : a > 0) (h₁ : d > 0)
    (h₂ : 1 / a = 1 / 3 + d) (h₃ : 1 / (a + d) = 1 / 4 + d)
    (h₄ : 1 / (a + 2 * d) = 1 / 6 + d) :
    ∑ i ∈ Finset.range 4, (1 / (a + i * d)) = 25 := by neural_grind
end split_active_069

