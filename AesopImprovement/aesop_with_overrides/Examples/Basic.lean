/-
  Examples/Basic.lean — basic coexistence and clause-forwarding examples.

  Run without overrides:
    lake build Examples.Basic

  Run with overrides (re-elaborates if source is unchanged? no — touch the file
  or clear the cache first):
    AESOP_OVERRIDES_JSON=examples/overrides_basic.json lake build Examples.Basic
-/

import Mathlib
import AesopWithOverrides

-- ---------------------------------------------------------------------------
-- 1. Both tactics work in the same file
-- ---------------------------------------------------------------------------

example : True := by aesop

set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example : True := by aesop_with_overrides

-- ---------------------------------------------------------------------------
-- 2. aesop_with_overrides accepts the same clauses as aesop
-- ---------------------------------------------------------------------------

-- (add ...) clause
example : True ∧ True := by
  aesop_with_overrides (add safe apply And.intro)

-- (erase ...) clause
example : True := by
  aesop_with_overrides (erase Aesop.BuiltinRules.assumption)

-- (config := ...) clause
example : True := by
  aesop_with_overrides (config := { maxRuleApplications := 200 })

-- ---------------------------------------------------------------------------
-- 3. aesop_with_overrides? prints a Try this suggestion, just like aesop?
-- ---------------------------------------------------------------------------

-- Produces: Try this: aesop (or similar)
example : True := by aesop_with_overrides?

-- ---------------------------------------------------------------------------
-- 4. Proofs that require Mathlib lemmas tagged @[aesop]
-- ---------------------------------------------------------------------------

set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example (n : ℕ) : 0 ≤ n := by aesop_with_overrides

set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example (p q r: Prop) (hp : p) (hq : q) : p ∧ (q ∨ r) := by aesop_with_overrides (config := { enableSimp := false })
