import Lean

/-!
Small examples for `grind =>`, Lean's interactive `grind` mode.

Open this file in the Lean editor. The trailing `|` on a step asks the
InfoView to show the grind state before and after that step. Use `finish?`
instead of `finish` when you want Lean to suggest a more explicit script.
-/

namespace GrindInteractiveExamples

/-! ## Manual theorem instantiation -/

def inc (n : Nat) : Nat := n + 1
def dec (n : Nat) : Nat := n - 1

theorem dec_inc (n : Nat) : dec (inc n) = n := by
  simp [dec, inc]

example {a b : Nat} (h : inc b = a) : dec a = b := by
  grind =>
    -- `= dec_inc` uses the left-hand side of the equality as the pattern.
    use [= dec_inc]

/-! ## One explicit E-matching round, then default search -/

opaque Related : Int → Int → Prop

@[grind →]
axiom Related.trans {x y z : Int} : Related x y → Related y z → Related x z

example {a b c d : Int}
    (hab : Related a b) (hbc : Related b c) (hcd : Related c d) : Related a d := by
  grind =>
    instantiate only [Related.trans] |
    finish

/-! ## Calling a specific grind subsolver -/

example {x y : Int} (h : 2 * x + 3 * y = 0) (hx : 1 ≤ x) : y < 1 := by
  grind =>
    lia

/-! ## Interactive case splitting -/

example (b : Bool) : (if b then (1 : Nat) else 2) ≠ (if b then 2 else 1) := by
  grind =>
    -- The anchor was produced by temporarily writing `cases?` here and
    -- accepting the suggested `cases #...` code action.
    cases #c8a3
    all_goals finish

end GrindInteractiveExamples
