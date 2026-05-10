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

/- benchmark 000: mathlib/Logic/swap_apply_ne_self_iff
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_000
open Function

namespace Equiv

variable {α α₁ α₂ β β₁ β₂ γ δ : Sort*}

variable [DecidableEq α]

example {a b x : α} : swap a b x ≠ x ↔ a ≠ b ∧ (x = a ∨ x = b) := by neural_grind

end Equiv
end split_active_000

/- benchmark 001: mathlib/Data/insert_comm
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=7
-/
section split_active_001
open Multiset Subtype Function

namespace Finset

variable {α : Type*} {β : Type*}

variable [DecidableEq α] {s t : Finset α} {a b : α} {f : α → β}

example (a b : α) (s : Finset α) : insert a (insert b s) = insert b (insert a s) := by neural_grind

end Finset
end split_active_001

/- benchmark 002: mathlib/Algebra/even_sign_iff
   grind_collect_splits=4 multi_candidate_steps=4 max_pool_size=3
-/
section split_active_002
namespace Int

variable {m n : ℤ}

example {z : ℤ} : Even z.sign ↔ z = 0 := by neural_grind

end Int
end split_active_002

/- benchmark 003: mathlib/Data/image_union
   grind_collect_splits=6 multi_candidate_steps=4 max_pool_size=5
-/
section split_active_003
open Function Set

namespace Set

variable {α β γ : Type*} {ι : Sort*}

variable {f : α → β} {s t : Set α}

example (f : α → β) (s t : Set α) : f '' (s ∪ t) = f '' s ∪ f '' t := by neural_grind

end Set
end split_active_003

/- benchmark 004: mathlib/Data/biUnion_singleton_eq_self
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_004
namespace Finset

variable {α β γ : Type*} {s s₁ s₂ : Finset α} {t t₁ t₂ : α → Finset β}

variable [DecidableEq β]

example [DecidableEq α] : s.biUnion (singleton : α → Finset α) = s := by neural_grind

end Finset
end split_active_004

/- benchmark 005: mathlib/Data/image_erase
   grind_collect_splits=5 multi_candidate_steps=3 max_pool_size=4
-/
section split_active_005
open Multiset
open Function

namespace Finset

variable {α β γ : Type*}

variable [DecidableEq β]

variable {f g : α → β} {s : Finset α} {t : Finset β} {a : α} {b c : β}

example [DecidableEq α] {f : α → β} (hf : Injective f) (s : Finset α) (a : α) :
    (s.erase a).image f = (s.image f).erase (f a) := by neural_grind

end Finset
end split_active_005

/- benchmark 006: mathlib/Data/support_subset_iff
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_006
open Finset Function

namespace Finsupp

variable {α β ι M N O G H : Type*}

variable [Zero M]

example {s : Set α} {f : α →₀ M} :
    ↑f.support ⊆ s ↔ ∀ a ∉ s, f a = 0 := by neural_grind

end Finsupp
end split_active_006

/- benchmark 007: mathlib/Order/Iic_diff_Ioc
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=6
-/
section split_active_007
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example : Iic b \ Ioc a b = Iic (a ⊓ b) := by neural_grind

end Set
end split_active_007

/- benchmark 008: mathlib/Order/Iic_union_Icc
   grind_collect_splits=7 multi_candidate_steps=5 max_pool_size=7
-/
section split_active_008
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example (h : min c d ≤ b) : Iic b ∪ Icc c d = Iic (max b d) := by neural_grind

end Set
end split_active_008

/- benchmark 009: mathlib/Logic/xor_not_not
   grind_collect_splits=3 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_009
open Function

variable {a b : Prop}

example : Xor' (¬a) (¬b) ↔ Xor' a b := by neural_grind
end split_active_009

/- benchmark 010: mathlib/Algebra/odd_add'
   grind_collect_splits=3 multi_candidate_steps=3 max_pool_size=8
-/
section split_active_010
namespace Int

variable {m n : ℤ}

example : Odd (m + n) ↔ (Odd n ↔ Even m) := by neural_grind

end Int
end split_active_010

/- benchmark 011: mathlib/Order/Ico_union_Ico
   grind_collect_splits=30 multi_candidate_steps=25 max_pool_size=11
-/
section split_active_011
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example (h₁ : min a b ≤ max c d) (h₂ : min c d ≤ max a b) :
    Ico a b ∪ Ico c d = Ico (min a c) (max b d) := by neural_grind

end Set
end split_active_011

/- benchmark 012: mathlib/Order/min_lt_min_left_iff
   grind_collect_splits=8 multi_candidate_steps=4 max_pool_size=3
-/
section split_active_012
variable {α : Type u} {β : Type v}

variable [LinearOrder α] [LinearOrder β] {f : α → β} {s : Set α} {a b c d : α}

example : min a c < min b c ↔ a < b ∧ a < c := by neural_grind
end split_active_012

/- benchmark 013: mathlib/Algebra/natAbs_odd
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=8
-/
section split_active_013
namespace Int

variable {m n : ℤ}

example : Odd n.natAbs ↔ Odd n := by neural_grind

end Int
end split_active_013

/- benchmark 014: mathlib/Order/Ico_diff_Ico_left
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=6
-/
section split_active_014
open Function OrderDual
open FinsetInterval

namespace Finset

variable {ι α : Type*} {a a₁ a₂ b b₁ b₂ c x : α}

variable [LinearOrder α]

variable [LocallyFiniteOrder α]

example (a b c : α) : Ico a b \ Ico a c = Ico (max a c) b := by neural_grind

end Finset
end split_active_014

/- benchmark 015: mathlib/Order/Ioo_inter_Ioo
   grind_collect_splits=8 multi_candidate_steps=6 max_pool_size=7
-/
section split_active_015
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example : Ioo a₁ b₁ ∩ Ioo a₂ b₂ = Ioo (a₁ ⊔ a₂) (b₁ ⊓ b₂) := by neural_grind

end Set
end split_active_015

/- benchmark 016: mathlib/Topology/trans_prod_eq_prod_trans
   grind_collect_splits=6 multi_candidate_steps=6 max_pool_size=13
-/
section split_active_016
open Topology Filter unitInterval Set Function
open ContinuousMap

namespace Path

variable {X Y : Type*} [TopologicalSpace X] [TopologicalSpace Y] {x y z : X} {ι : Type*}

variable (γ : Path x y)

variable {a₁ a₂ a₃ : X} {b₁ b₂ b₃ : Y}

example (γ₁ : Path a₁ a₂) (δ₁ : Path a₂ a₃) (γ₂ : Path b₁ b₂)
    (δ₂ : Path b₂ b₃) : (γ₁.prod γ₂).trans (δ₁.prod δ₂) = (γ₁.trans δ₁).prod (γ₂.trans δ₂) := by neural_grind

end Path
end split_active_016

/- benchmark 017: mathlib/Data/prod_diff_prod
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=9
-/
section split_active_017
open Function

namespace Set

variable {α β γ δ : Type*} {s s₁ s₂ : Set α} {t t₁ t₂ : Set β} {a : α} {b : β}

example : s ×ˢ t \ s₁ ×ˢ t₁ = s ×ˢ (t \ t₁) ∪ (s \ s₁) ×ˢ t := by neural_grind

end Set
end split_active_017

/- benchmark 018: mathlib/Data/subset_singleton_iff
   grind_collect_splits=5 multi_candidate_steps=4 max_pool_size=3
-/
section split_active_018
open Multiset Subtype Function

namespace Finset

variable {α : Type*} {β : Type*}

variable {s : Finset α} {a b : α}

example {s : Finset α} {a : α} : s ⊆ {a} ↔ s = ∅ ∨ s = {a} := by neural_grind

end Finset
end split_active_018

/- benchmark 019: mathlib/Data/insert_eq_of_mem
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_019
open Function

namespace Set

variable {α β : Type*} {s t : Set α} {a b : α}

example {a : α} {s : Set α} (h : a ∈ s) : insert a s = s := by neural_grind

end Set
end split_active_019

/- benchmark 020: mathlib/Order/compl_Ioc
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=6
-/
section split_active_020
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example : (Ioc a b)ᶜ = Iic a ∪ Ioi b := by neural_grind

end Set
end split_active_020

/- benchmark 021: mathlib/Data/biUnion_inter
   grind_collect_splits=4 multi_candidate_steps=2 max_pool_size=4
-/
section split_active_021
namespace Finset

variable {α β γ : Type*} {s s₁ s₂ : Finset α} {t t₁ t₂ : α → Finset β}

variable [DecidableEq β]

example (s : Finset α) (f : α → Finset β) (t : Finset β) :
    s.biUnion f ∩ t = s.biUnion fun x ↦ f x ∩ t := by neural_grind

end Finset
end split_active_021

/- benchmark 022: mathlib/Order/Ioo_filter_lt
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=5
-/
section split_active_022
open Function OrderDual
open FinsetInterval

namespace Finset

variable {ι α : Type*} {a a₁ a₂ b b₁ b₂ c x : α}

variable [LinearOrder α]

variable [LocallyFiniteOrder α]

example (a b c : α) : {x ∈ Ioo a b | x < c} = Ioo a (min b c) := by neural_grind

end Finset
end split_active_022

/- benchmark 023: mathlib/Order/Ioc_union_Ioc_symm
   grind_collect_splits=4 multi_candidate_steps=4 max_pool_size=7
-/
section split_active_023
open Function

namespace Set

variable {α : Type*} [LinearOrder α] {a a₁ a₂ b b₁ b₂ c d : α}

example : Ioc a b ∪ Ioc b a = Ioc (min a b) (max a b) := by neural_grind

end Set
end split_active_023

/- benchmark 024: mathlib/Algebra/even_sub
   grind_collect_splits=3 multi_candidate_steps=3 max_pool_size=4
-/
section split_active_024
open Nat

namespace Int

variable {m n : ℤ}

example : Even (m - n) ↔ (Even m ↔ Even n) := by neural_grind

end Int
end split_active_024

/- benchmark 025: workbook/workbook_30000_39999/lean_workbook_plus_32662
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_025
example (x : ℝ) (hx : x + 1/x = 21) : x^4 + 1/(x^4) = 192719   := by neural_grind
end split_active_025

/- benchmark 026: workbook/workbook_00000_09999/lean_workbook_plus_141
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_026
example (c d : ℝ) : (c + d) * Real.sqrt (c^4 - d^4) / (c^4 - d^4) = Real.sqrt (c^4 - d^4) / ((c^2 + d^2) * (c - d))   := by neural_grind
end split_active_026

/- benchmark 027: workbook/workbook_70000_79999/lean_workbook_plus_77164
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_027
example (r₀ r₁ α : ℝ)
  (h₀ : 0 < r₀ ∧ 0 < r₁)
  (h₁ : 0 < α ∧ α ≤ π ∧ α ≠ π / 2)
  (h₂ : r₁ = r₀ * (1 - Real.sin α) / (1 + Real.sin α))
  (h₃ : 0 < Real.sin α ∧ Real.sin α ≠ 1) :
  r₁ / r₀ = (1 - Real.sin α) / (1 + Real.sin α)   := by neural_grind
end split_active_027

/- benchmark 028: workbook/workbook_50000_59999/lean_workbook_plus_57616
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=4
-/
section split_active_028
example : ∀ A : Set (ℕ → ℝ), A = {x | ∀ n : ℕ, 0 ≤ x n} ↔ ∀ x : ℕ → ℝ, x ∈ A ↔ ∀ n : ℕ, 0 ≤ x n   := by neural_grind
end split_active_028

/- benchmark 029: workbook/workbook_30000_39999/lean_workbook_plus_37542
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_029
example (x : ℝ) : x^2 + 5*x + 6 = 0 ↔ x = -3 ∨ x = -2   := by neural_grind
end split_active_029

/- benchmark 030: workbook/workbook_10000_19999/lean_workbook_plus_10625
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_030
example (a b : ℝ) (h : |a| ≤ b) : -b ≤ a ∧ a ≤ b   := by neural_grind
end split_active_030

/- benchmark 031: workbook/workbook_00000_09999/lean_workbook_plus_402
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_031
example (p q r a b : ℝ)
  (h₀ : p + q + r = 1 / a)
  (h₁ : p * q + q * r + r * p = b / a) :
  a * b = (p * q + q * r + r * p) / (p + q + r)^2   := by neural_grind
end split_active_031

/- benchmark 032: workbook/workbook_60000_69999/lean_workbook_plus_61780
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=3
-/
section split_active_032
example (x y z : ℝ)
  (h₀ : 0 < x ∧ 0 < y ∧ 0 < z)
  (h₁ : x^2 + y^2 = z^2)
  (h₂ : y^2 + z^2 = x^2)
  (h₃ : z^2 + x^2 = y^2) :
  (x^2 + y^2 + z^2) / x + (x^2 + y^2 + z^2) / y + (x^2 + y^2 + z^2) / z ≥ 2 * (x + y + z)   := by neural_grind
end split_active_032

/- benchmark 033: workbook/workbook_10000_19999/lean_workbook_plus_14091
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_033
example (x : ℝ) (hx : 0 < x) (h : 3 * x / Real.sqrt (3 * x + 10) = Real.sqrt (3 * x + 1) - 1) : x = 0 ∨ x = 5   := by neural_grind
end split_active_033

/- benchmark 034: workbook/workbook_30000_39999/lean_workbook_plus_31182
   grind_collect_splits=1 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_034
example (x y: ℝ) : (x + 1) * (y + 1) ≥ 4 * Real.sqrt (x * y) ↔ x * y + x + y + 1 ≥ 4 * Real.sqrt (x * y)   := by neural_grind
end split_active_034

/- benchmark 035: workbook/workbook_20000_29999/lean_workbook_plus_29828
   grind_collect_splits=23 multi_candidate_steps=15 max_pool_size=5
-/
section split_active_035
example (x y : ℝ) (hx : abs (x + y) + abs (x - y + 1) = 2) : 5 / 6 ≤ abs (2 * x - y) + abs (3 * y - x) ∧ abs (2 * x - y) + abs (3 * y - x) ≤ 21 / 2   := by neural_grind
end split_active_035

/- benchmark 036: workbook/workbook_10000_19999/lean_workbook_plus_13598
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_036
example (a b : ℝ) (ha : a ≠ 0) : a^2 / (a^2 + a * b + b^2) = 1 / (1 + b / a + b^2 / a^2)   := by neural_grind
end split_active_036

/- benchmark 037: workbook/workbook_40000_49999/lean_workbook_plus_48321
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_037
example (x : ℝ) : x^3 - 6 * x^2 + 9 * x - 4 = 0 ↔ x = 1 ∨ x = 1 ∨ x = 4   := by neural_grind
end split_active_037

/- benchmark 038: workbook/workbook_30000_39999/lean_workbook_plus_38012
   grind_collect_splits=4 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_038
example (x y : ℝ)
  (h₀ : 0 ≤ x)
  (h₁ : 0 ≤ y) :
  Real.sqrt x ^ 2 = x ∧ Real.sqrt y ^ 2 = y   := by neural_grind
end split_active_038

/- benchmark 039: workbook/workbook_80000_89999/lean_workbook_plus_80913
   grind_collect_splits=7 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_039
example (a : ℝ) (x y : ℝ) (ha : a > 0) (hx : |x - 1| < a / 3) (hy : |y - 2| < a / 3) : |2 * x + y - 4| < a   := by neural_grind
end split_active_039

/- benchmark 040: workbook/workbook_70000_79999/lean_workbook_plus_75593
   grind_collect_splits=17 multi_candidate_steps=17 max_pool_size=26
-/
section split_active_040
example (n : ℕ) (b : ℕ → ℕ) (h₁ : b 0 = 5) (h₂ : ∀ n, b (n + 1) - b n = (n + 6).choose 4) : b (n + 1) = b n + (n + 6).choose 4   := by neural_grind
end split_active_040

/- benchmark 041: workbook/workbook_10000_19999/lean_workbook_plus_14540
   grind_collect_splits=5 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_041
example (x y : ℝ) : |y| - |x| ≤ |x - y|   := by neural_grind
end split_active_041

/- benchmark 042: workbook/workbook_60000_69999/lean_workbook_plus_62899
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_042
example (P Q : Set α) (hPQ : P ⊆ Q) : P ∩ Q = P   := by neural_grind
end split_active_042

/- benchmark 043: workbook/workbook_50000_59999/lean_workbook_plus_56588
   grind_collect_splits=4 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_043
example (x : ℝ)
  (h₀ : x ≠ 1) :
  ((x - 1) * (x + 1)) / ((x - 1) * (x^2 + x + 1)) + (Real.cos (x - 1)) / (3 * x^2) =
    (x + 1) / (x^2 + x + 1) + (Real.cos (x - 1)) / (3 * x^2)   := by neural_grind
end split_active_043

/- benchmark 044: workbook/workbook_80000_89999/lean_workbook_plus_82549
   grind_collect_splits=3 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_044
example (α β γ : ℝ) (h₁ : α * β + β * γ + γ * α = 0) (h₂ : α * β * γ = 1) : 1 / γ = 1 / -α + 1 / -β   := by neural_grind
end split_active_044

/- benchmark 045: workbook/workbook_00000_09999/lean_workbook_plus_2081
   grind_collect_splits=4 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_045
example (t : ℝ) : t * (t - 1) * (t + 2) * (19 * t - 30) = 0 ↔ t = 0 ∨ t = 1 ∨ t = -2 ∨ t = 30 / 19   := by neural_grind
end split_active_045

/- benchmark 046: workbook/workbook_50000_59999/lean_workbook_plus_54147
   grind_collect_splits=5 multi_candidate_steps=3 max_pool_size=3
-/
section split_active_046
example (M x: ℝ) (g : ℝ → ℝ) (h₁ : |g x - M| < |M| / 2) : |g x| > |M| / 2   := by neural_grind
end split_active_046

/- benchmark 047: workbook/workbook_30000_39999/lean_workbook_plus_32045
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_047
example (a b c : ℝ) (h₁ : a * (1/b) = 1) (h₂ : b * (1/c) = 1) : c * (1/a) = 1   := by neural_grind
end split_active_047

/- benchmark 048: workbook/workbook_80000_89999/lean_workbook_plus_81216
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_048
example (x : ℝ) (hx : x ≠ 1) : (x^2 - 2) / (x - 1)^3 = -1 / (x - 1)^3 + 2 / (x - 1)^2 + 1 / (x - 1)   := by neural_grind
end split_active_048

/- benchmark 049: workbook/workbook_40000_49999/lean_workbook_plus_40007
   grind_collect_splits=13 multi_candidate_steps=11 max_pool_size=5
-/
section split_active_049
example (x : ℝ) : abs x + x ^ 2 + abs (abs x - 1) + 6 * abs (x - 2) + abs (x ^ 2 - 1) + 3 * abs (2 * x + 1) ≥ 17   := by neural_grind
end split_active_049

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

/- benchmark 051: numina/Algebra/algebra_135946
   grind_collect_splits=8 multi_candidate_steps=2 max_pool_size=2
-/
section split_active_051
/- Find all real numbers $x, y, z$ satisfying:

$$
\left\{\begin{array}{l}
(x+1) y z=12 \\
(y+1) z x=4 \\
(z+1) x y=4
\end{array}\right.
$$ -/
example {x y z : ℝ} (h₀ : (x + 1) * y * z = 12) (h₁ : (y + 1) * z * x = 4)
    (h₂ : (z + 1) * x * y = 4) :
    (x = 2 ∧ y = -2 ∧ z = -2) ∨ (x = 1 / 3 ∧ y = 3 ∧ z = 3) := by neural_grind
end split_active_051

/- benchmark 052: numina/Inequalities/inequalities_205242
   grind_collect_splits=21 multi_candidate_steps=15 max_pool_size=6
-/
section split_active_052
/- Galochkin A.i.

Prove that if for numbers $a, b$ and $c$ the inequalities $|a-b| \geq|c|,|b-c| \geq|a|,|c-a| \geq|b|$ hold, then one of these numbers is equal to the sum of the other two. -/
example {a b c : ℝ} (h₀ : abs (a - b) ≥ abs c) (h₁ : abs (b - c) ≥ abs a)
    (h₂ : abs (c - a) ≥ abs b) :
    a = b + c ∨ b = a + c ∨ c = a + b := by neural_grind
end split_active_052

/- benchmark 053: numina/unknown/algebra_4744
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_053
/- Solve the equation: $\frac{1}{x^{2}+3x}+ \frac{1}{x^{2}+9x+18}+ \frac{1}{x^{2}+15x+54}= \frac{3}{2x+18}$, $x=$ ___          ___ . -/
example (x : ℝ) (hx : x^2 + 3 * x ≠ 0 ∧ x^2 + 9 * x + 18 ≠ 0 ∧ x^2 + 15 * x + 54 ≠ 0) :
    1 / (x^2 + 3 * x) + 1 / (x^2 + 9 * x + 18) + 1 / (x^2 + 15 * x + 54) = 3 / (2 * x + 18) ↔ x = 2 := by neural_grind
end split_active_053

/- benchmark 054: numina/Other/other_269148
   grind_collect_splits=12 multi_candidate_steps=11 max_pool_size=7
-/
section split_active_054
example :
   (|(1.01 : ℝ) - 1| < |(0.50 : ℝ) - 1| ∧
    |(1.01 : ℝ) - 1| < |(0.90 : ℝ) - 1| ∧
    |(1.01 : ℝ) - 1| < |(0.95 : ℝ) - 1| ∧
    |(1.01 : ℝ) - 1| < |(1.15 : ℝ) - 1|) := by neural_grind
end split_active_054

/- benchmark 055: numina/Inequalities/inequalities_223947
   grind_collect_splits=21 multi_candidate_steps=15 max_pool_size=6
-/
section split_active_055
/- 11. Prove: For any real numbers $x, y, z$, the following three inequalities cannot all hold simultaneously: $|x|<|y-z|$, $|y|<|z-x|$, $|z|<|x-y|$. -/
example (x y z : ℝ) :
    ¬(|x| < |y - z| ∧ |y| < |z - x| ∧ |z| < |x - y|) := by neural_grind
end split_active_055

/- benchmark 056: numina/Inequalities/inequalities_189838
   grind_collect_splits=21 multi_candidate_steps=15 max_pool_size=6
-/
section split_active_056
/- [ Absolute value ] [ Case analysis ]

Prove that the system of inequalities $|x|<|y-z|$, $|y|<|z-x|$, $|z|<|x-y|$ has no solutions.

# -/
example (x y z : ℝ) :
    (|x| < |y - z| ∧ |y| < |z - x| ∧ |z| < |x - y|) ↔ False := by neural_grind
end split_active_056

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

/- benchmark 058: numina/Number Theory/algebra_635522
   grind_collect_splits=3 multi_candidate_steps=3 max_pool_size=157
-/
section split_active_058
set_option maxHeartbeats 800000
example (n1 n2 n3 a1 a2 a3 a4 d1 d2 d3 d4 : ℕ) (h1 : 0 < a1) (h2 : a1 < a2) (h3 : a2 < a3) (h4 : a3 < a4) (h5 : a4 ≤ 9) (hn1 : n1 = 1000 * a1 + 100 * a2 + 10 * a3 + a4) (hn2 : n2 = 1000 * a4 + 100 * a3 + 10 * a2 + a1) (hn3 : n3 = 1000 * d1 + 100 * d2 + 10 * d3 + d4) (hd1 : 0 < d1 ∧ d1 < 10) (hd2 : 0 < d2 ∧ d2 < 10) (hd3 : 0 < d3 ∧ d3 < 10) (hd4 : 0 < d4 ∧ d4 < 10) (h : (d1, d2, d3, d4) ∈ ({(a1, a2, a3, a4), (a1, a2, a4, a3), (a1, a3, a2, a4), (a1, a4, a2, a3), (a1, a3, a4, a2), (a1, a4, a3, a2), (a2, a1, a3, a4), (a2, a1, a4, a3), (a3, a1, a2, a4), (a4, a1, a2, a3), (a3, a1, a4, a2), (a4, a1, a3, a2), (a3, a2, a1, a4), (a4, a2, a1, a3), (a2, a3, a1, a4), (a2, a4, a1, a3), (a4, a3, a1, a2), (a3, a4, a1, a2), (a4, a2, a3, a1), (a3, a2, a4, a1), (a4, a3, a2, a1), (a3, a4, a2, a1), (a2, a3, a4, a1), (a2, a4, a3, a1)} : Finset (ℕ × ℕ × ℕ × ℕ))) (hsum : n1 + n2 + n3 = 6798) : min (min n1 n2) n3 = 1234 := by neural_grind
end split_active_058

/- benchmark 059: numina/Algebra/algebra_97650
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_059
/- Real numbers $x$ and $y$ satisfy $x + y = 4$ and $x \cdot y = -2$. What is the value of 
\[x + \frac{x^3}{y^2} + \frac{y^3}{x^2} + y?\]
$\textbf{(A)}\ 360\qquad\textbf{(B)}\ 400\qquad\textbf{(C)}\ 420\qquad\textbf{(D)}\ 440\qquad\textbf{(E)}\ 480$ -/
example {x y : ℝ} (h₀ : x + y = 4) (h₁ : x * y = -2) :
    x + x^3 / y^2 + y^3 / x^2 + y = 440 := by neural_grind
end split_active_059

/- benchmark 060: numina/unknown/algebra_3430
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_060
/- Given that $x_{1}$ and $x_{2}$ are the two real roots of the quadratic equation $x^{2}-8x+k=0$, and $\dfrac{1}{x_{1}}+\dfrac{1}{x_{2}}=\dfrac{2}{3}$. Find the value of $k$. -/
example {x1 x2 k : ℝ} (hx1 : x1^2 - 8 * x1 + k = 0) (hx2 : x2^2 - 8 * x2 + k = 0)
    (hroots : x1 ≠ x2) (hsum : 1 / x1 + 1 / x2 = 2 / 3) : k = 12 := by neural_grind
end split_active_060

/- benchmark 061: numina/NaN/algebra_272103
   grind_collect_splits=3 multi_candidate_steps=2 max_pool_size=3
-/
section split_active_061
/- If $x$ and $y$ are positive real numbers with $\frac{1}{x+y}=\frac{1}{x}-\frac{1}{y}$, what is the value of $\left(\frac{x}{y}+\frac{y}{x}\right)^{2} ?$ -/
example (x y : ℝ) (hx : 0 < x) (hy : 0 < y) (h : 1 / (x + y) = 1 / x - 1 / y) :
    (x / y + y / x) ^ 2 = 5 := by neural_grind
end split_active_061

/- benchmark 062: numina/Algebra/algebra_242442
   grind_collect_splits=5 multi_candidate_steps=2 max_pool_size=2
-/
section split_active_062
/- Problem 5. Solve the system of equations

$$
\left\{\begin{array}{l}
x^{2}=(y-z)^{2}-3 \\
y^{2}=(z-x)^{2}-7 \\
z^{2}=(x-y)^{2}+21
\end{array}\right.
$$ -/
example {x y z : ℝ}
    (h1 : x^2 = (y - z)^2 - 3) (h2 : y^2 = (z - x)^2 - 7) (h3 : z^2 = (x - y)^2 + 21) :
    (x = -1 ∧ y = -3 ∧ z = -5) ∨ (x = 1 ∧ y = 3 ∧ z = 5) := by neural_grind
end split_active_062

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

/- benchmark 065: numina/Inequalities/inequalities_220639
   grind_collect_splits=12 multi_candidate_steps=7 max_pool_size=8
-/
section split_active_065
example (a b c : ℕ) (h₀ : a + b + c = 60) (h₁ : a ≤ b + c)
    (h₂ : b ≤ a + c) (h₃ : c ≤ a + b) (h₄ : |(a : ℤ) - b| ≥ 3) (h₅ : |(b : ℤ) - c| ≥ 3)
    (h₆ : |(c : ℤ) - a| ≥ 3) :
    min (min a b) c ∈ Finset.Icc 3 17 := by neural_grind
end split_active_065

/- benchmark 066: numina/Inequalities/inequalities_319875
   grind_collect_splits=15 multi_candidate_steps=7 max_pool_size=4
-/
section split_active_066
open Real Set
open scoped BigOperators

/- 4. The coordinates of point $M(x, y)$ satisfy $|x+y|<|x-y|$. Then the quadrant in which point $M$ is located is ( ).
(A) 1,3
(B) 2,4
(C) 1,2
(D) 3,4 -/
example (x y : ℝ) (h : abs (x + y) < abs (x - y)) :
    (x < 0 ∧ y > 0) ∨ (x > 0 ∧ y < 0) := by neural_grind
end split_active_066

/- benchmark 067: numina/Algebra/algebra_218509
   grind_collect_splits=2 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_067
/- 2. A person travels by boat along the river Drim from Struga to Globocica and back. The distance between Struga and Globocica is $18 \mathrm{~km}$, and he traveled in total 5 hours. What is the speed of the river Drim, if the person traveled $4 \mathrm{~km}$ downstream and $2 \mathrm{~km}$ upstream in the same time? -/
example (v : ℝ) (h : v > 0) (h1 : 18 / (v + w) + 18 / (v - w) = 5)
    (h2 : 4 / (v + w) = 2 / (v - w)) :
    w = 2.7 := by neural_grind
end split_active_067

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

/- benchmark 070: numina/Inequalities/inequalities_115987
   grind_collect_splits=45 multi_candidate_steps=27 max_pool_size=6
-/
section split_active_070
/- 9・173 Let $x, y, z$ be real numbers, prove:
$$
|x|+|y|+|z| \leqslant |x+y-z|+|x-y+z|+|-x+y+z| \text {. }
$$ -/
example (x y z : ℝ) :
    abs x + abs y + abs z ≤ abs (x + y - z) + abs (x - y + z) + abs (-x + y + z) := by neural_grind
end split_active_070

/- benchmark 071: numina/Combinatorics/combinatorics_239111
   grind_collect_splits=2 multi_candidate_steps=2 max_pool_size=4
-/
section split_active_071
open Finset
example (a : ℕ → ℕ → ℕ)
    (ha : ∀ i j, a i j = if i % 2 = j % 2 then 1 else 0) :
    ¬∃ i j, a i j = 1 ∧ a (i + 1) j = 1 ∧ a i (j + 1) = 1 ∧ a (i + 1) (j + 1) = 1 := by neural_grind
end split_active_071

/- benchmark 072: numina/unknown/algebra_8833
   grind_collect_splits=4 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_072
/- Solve the equation
$$\left(x^2 + 3x - 4\right)^3 + \left(2x^2 - 5x + 3\right)^3 = \left(3x^2 - 2x - 1\right)^3.$$ -/
example (x : ℝ) :
    (x ^ 2 + 3 * x - 4)^3 + (2 * x^2 - 5 * x + 3)^3 =
    (3 * x^2 - 2 * x - 1)^3 ↔
    x = -4 ∨ x = -1 / 3 ∨ x = 1 ∨ x = 3 / 2 := by neural_grind
end split_active_072

/- benchmark 073: numina/Algebra/algebra_325177
   grind_collect_splits=3 multi_candidate_steps=1 max_pool_size=2
-/
section split_active_073
/- Example 3 Solve the equation
$$
\frac{1}{6 x-5}-\frac{1}{5 x+4}=\frac{1}{5 x-4}-\frac{1}{4 x+5} .
$$ -/
example (x : ℝ) (hx : 6*x-5≠0 ∧ 5*x+4≠0 ∧ 5*x-4≠0 ∧ 4*x+5≠0) :
    1/(6*x-5) - 1/(5*x+4) = 1/(5*x-4) - 1/(4*x+5) ↔ x=9 ∨ x=0 ∨ x=1 := by neural_grind
end split_active_073

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
