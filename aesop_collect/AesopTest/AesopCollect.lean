/-
Copyright (c) 2026. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: OpenAI
-/

import Aesop

set_option aesop.check.all true
set_option aesop.smallErrorMessages true

-- Plain `aesop` should not emit collection output.

example (p q : Prop) (hp : p) : p ∨ q := by
  aesop (config := { enableSimp := false })

/--
info: aesop_collect: []
-/
-- #guard_msgs in
example (p q : Prop) (hp : p) (hq : q) : p ∧ q := by
  aesop_collect

/--
info: aesop_collect: [
  (goal :=
    p q : Prop
    hp : p
    ⊢ p ∨ q,
    allowedUnsafeRules := [unsafe|tactic|global|Aesop.BuiltinRules.applyHyps, unsafe|constructors|global|Or],
    chosen := unsafe|constructors|global|Or)
]
-/
-- #guard_msgs in
example (p q : Prop) (hp : p) : p ∨ q := by
  aesop_collect (config := { enableSimp := false })

/--
info: aesop_collect: [
  (goal :=
    p q r : Prop
    hp : p
    ⊢ (p ∨ q) ∨ r,
    allowedUnsafeRules := [unsafe|tactic|global|Aesop.BuiltinRules.applyHyps, unsafe|constructors|global|Or],
    chosen := unsafe|constructors|global|Or),
  (goal :=
    case h
    p q r : Prop
    hp : p
    ⊢ p ∨ q,
    allowedUnsafeRules := [unsafe|tactic|global|Aesop.BuiltinRules.applyHyps, unsafe|constructors|global|Or],
    chosen := unsafe|constructors|global|Or)
]
-/
-- #guard_msgs in
example (p q r : Prop) (hp : p) : (p ∨ q) ∨ r := by
  aesop_collect (config := { enableSimp := false })
