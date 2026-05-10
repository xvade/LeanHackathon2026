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


/- benchmark 057: numina/unknown/algebra_101
   grind_collect_splits=12 multi_candidate_steps=9 max_pool_size=6
-/
section split_active_057
/- Given $\frac{1}{x}+\frac{1}{y+z}=\frac{1}{2}$, $\frac{1}{y}+\frac{1}{z+x}=\frac{1}{3}$, $\frac{1}{z}+\frac{1}{x+y}=\frac{1}{4}$, then the value of $\frac{2}{x}+\frac{3}{y}+\frac{4}{z}$ is ( ).

A: $1$
B: $\frac{3}{2}$
C: $2$
D: $\frac{5}{2}$ -/
example {x y z : ℝ} (h1 : 1 / x + 1 / (y + z) = 1 / 2) (h2 : 1 / y + 1 / (z + x) = 1 / 3) (h3 : 1 / z + 1 / (x + y) = 1 / 4) : 2 / x + 3 / y + 4 / z = 2 := by neural_grind
end split_active_057

