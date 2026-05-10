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


/- benchmark 063: numina/Algebra/algebra_291117
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=6
-/
section split_active_063
open Real Set
open scoped BigOperators

/- 1. The weight of a car is 12 metric tons, its power is 15 horsepower, what is the maximum achievable speed (1) on a horizontal road where $\rho=\frac{1}{20}$;

(2) on a road that rises in the same conditions in the ratio $=1_{\overline{30}}$;

(3) if we load 4 more metric tons of cargo on it and take the previous two roads as a basis?[^0]


[^0]:    ${ }^{1}$ In this problem, $\rho$ is the coefficient of friction, and $e$ is the sine of the angle of inclination. -/

example :
  let weight₁ := 1200; -- 汽车重量(kgf)
  let weight₂ := 1600; -- 增加4吨后的重量(kgf)
  let power := 15 * 75; -- 功率(kg·m/s)
  let ρ := 1/20;       -- 摩擦系数
  let e := 1/30;       -- 坡道倾角正弦值
  
  {(v₁, v₂, v₃, v₄) : ℝ × ℝ × ℝ × ℝ | 
    ρ * weight₁ * v₁ = power ∧                       -- 水平道路
    (ρ + e) * weight₁ * v₂ = power ∧                 -- 上坡道路
    ρ * weight₂ * v₃ = power ∧                       -- 增加负载后水平道路
    (ρ + e) * weight₂ * v₄ = power                   -- 增加负载后上坡道路
  } =
  {(18.75, 11.25, 14.0625, 8.4375)}
  := by neural_grind
end split_active_063

