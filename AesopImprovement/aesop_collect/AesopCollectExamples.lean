import Aesop

/-!
Small examples for the instrumented `aesop_collect` tactic.

When `aesop_collect` closes a goal, it logs the unsafe-rule choices on the
successful branch. Each entry has this shape:

```
(goal := <goal state>,
  allowedUnsafeRules := [<unsafe rules still available at this choice point>],
  chosen := <unsafe rule selected on the successful branch>)
```
-/

example (p q : Prop) (hp : p) : p ∨ q := by
  aesop_collect (config := { enableSimp := false })

example (p q r : Prop) (hp : p) : (p ∨ q) ∨ r := by
  aesop_collect (config := { enableSimp := false })
