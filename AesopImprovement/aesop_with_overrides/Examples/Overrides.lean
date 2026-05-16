/-
  Examples/Overrides.lean — demonstrates probability override behaviour.

  WHAT CAN BE OVERRIDDEN
  ──────────────────────
  Any rule registered as *unsafe* (i.e. tagged with a % probability in
  @[aesop]) can have its success probability replaced.  Match by the
  fully-qualified Lean declaration name.

  Examples of overridable rules (all unsafe):
    • "Aesop.BuiltinRules.applyHyps"   default 75%   (builtin)
    • "Aesop.BuiltinRules.ext"         default 80%   (builtin)
    • Any Mathlib lemma tagged, e.g.:
        @[aesop unsafe 90% apply]
        theorem IsSquare.sq ...

  WHAT CANNOT BE OVERRIDDEN (current implementation)
  ───────────────────────────────────────────────────
  Safe and norm rules use integer *penalties*, not probabilities.  Our patch
  only touches `BaseRuleSet.unsafeRules`; the following builtins are unaffected:
    • Aesop.BuiltinRules.assumption   (safe  -50)
    • Aesop.BuiltinRules.rfl          (safe    0)
    • Aesop.BuiltinRules.split        (safe  100/1000)
    • Aesop.BuiltinRules.intros       (norm -100)
    • Aesop.BuiltinRules.subst        (norm  -50)
    • Aesop.BuiltinRules.destructProducts (norm 0)

  JSON FORMAT
  ───────────
  { "DeclarationName": <float in [0,1]>, ... }

  The key is the bare Lean name (dots as namespace separators).
  The value replaces the rule's successProbability field before search.

  HOW TO USE
  ──────────
  Set AESOP_OVERRIDES_JSON to the path of your JSON file, then build.
  The file is read at elaboration time (= when the .olean is compiled).

    AESOP_OVERRIDES_JSON=/path/to/overrides.json lake build MyTarget

  After changing the JSON without touching the .lean source, clear the olean:
    lake build --force MyTarget        (or delete the relevant .olean)
-/

import Mathlib
import AesopWithOverrides

-- ---------------------------------------------------------------------------
-- Demonstration: deprioritise applyHyps
--
-- Without overrides: applyHyps runs at 75%.
-- With overrides.json = { "Aesop.BuiltinRules.applyHyps": 0.01 }
--   the rule is still tried (aesop is complete) but ranked last among
--   unsafe rules, so other rules are explored first.
--
-- Both proofs below succeed regardless of the override value; the override
-- changes the *order* in which rules are tried, not whether they are tried.
-- ---------------------------------------------------------------------------

example (h : True) : True := by aesop_with_overrides

example (h₁ : True) (h₂ : False) : False := by aesop_with_overrides

-- ---------------------------------------------------------------------------
-- Demonstration: rules that appear in the JSON but are not in the rule set
-- are silently ignored (no error).
-- ---------------------------------------------------------------------------

-- If overrides.json contains "Nat.nonexistent_lemma": 0.5, nothing breaks.
example : 1 + 1 = 2 := by aesop_with_overrides

-- ---------------------------------------------------------------------------
-- Demonstration: overriding a Mathlib unsafe rule
--
-- IsSquare.sq is tagged @[aesop unsafe 90% apply] in Mathlib.
-- Set "IsSquare.sq": 0.01 in the JSON to deprioritise it.
-- The proof still works because aesop exhausts all rules eventually.
-- ---------------------------------------------------------------------------

example (x : ℤ) : IsSquare (x ^ 2) := by aesop_with_overrides
