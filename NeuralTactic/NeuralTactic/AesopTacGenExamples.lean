import Aesop

/-!
# Aesop tactic-generator examples

This file demonstrates Aesop's existing `TacGen` hook:

```
Aesop.TacGen := MVarId -> MetaM (Array (Prod String Float))
```

A generator receives the current goal and returns tactic strings with
probabilities. Aesop parses and runs each tactic. Each successful generated
tactic becomes a separate rule application, and its probability is multiplied
into the child goal priority.

The examples below intentionally use only one local unsafe rule and disable the
default/builtin rule sets. Apart from Aesop's always inserted preprocess rule,
that makes the trace output show the generated branches instead of Aesop's
normal library of rules.

Useful trace options in this file:

* `trace.aesop.debug`: shows that the selected unsafe rule is the generator.
* `trace.aesop`: shows the generated successful branch applications and their
  probabilities.
* `trace.aesop.tree`: shows the final search tree, including branch ordering.
* `trace.aesop.proof`: shows the reconstructed proof term.
-/

open Lean Meta

namespace AesopTacGenExamples

/--
Return true if the local context contains a non-implementation-detail
hypothesis whose type is definitionally equal to `type`.
-/
private def hasLocalHypDefEq (type : Expr) : MetaM Bool := do
  let lctx <- getLCtx
  for localDecl in lctx do
    unless localDecl.isImplementationDetail do
      let localType <- instantiateMVars localDecl.type
      if <- withNewMCtxDepth <| isDefEq localType type then
        return true
  return false

/--
This generator is deliberately small, but it is enough to demonstrate the hook.

For an `Or` goal, it looks at the current local context. If the left side has a
matching hypothesis, it gives `left` the high score. If the right side has a
matching hypothesis, it gives `right` the high score. For an `And` goal, it
tries `constructor`. For leaf goals, it falls back to `assumption` and `rfl`.
-/
def goalAwareTacGen : Aesop.TacGen := fun goal => do
  goal.withContext do
    let goalType <- goal.getType
    let target <- instantiateMVars goalType
    if target.isAppOf ``Or then
      let args := target.getAppArgs
      if h : args.size = 2 then
        let leftTarget := args[0]
        let rightTarget := args[1]
        let leftHasHyp <- hasLocalHypDefEq leftTarget
        let rightHasHyp <- hasLocalHypDefEq rightTarget
        match leftHasHyp, rightHasHyp with
        -- Put the weaker branch first to demonstrate that Aesop's queue is
        -- using probabilities, not just the generator's array order.
        | true, false => return #[("right", 0.35), ("left", 0.95)]
        | false, true => return #[("left", 0.35), ("right", 0.95)]
        | true, true => return #[("left", 0.90), ("right", 0.85)]
        | false, false => return #[("left", 0.55), ("right", 0.50)]
      else
        return #[("left", 0.50), ("right", 0.50)]
    else if target.isAppOf ``And then
      return #[("constructor", 0.90)]
    else if <- hasLocalHypDefEq target then
      return #[("assumption", 0.95), ("rfl", 0.20)]
    else
      return #[("rfl", 0.70), ("assumption", 0.20)]

/-!
## Demo 1: left branch first

The target is `P \/ Q`, and the context contains `hP : P`.

In the trace, look for generated branch applications with probabilities around:

```
left   95%
right  35%
```

The generator deliberately returns `right` before `left` in this case. Aesop
still expands the `left` child first because that generated tactic has the
higher probability for this goal state.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {P Q : Prop} (hP : P) : P \/ Q := by
  aesop (rule_sets := [-default, -builtin])
    (config := { enableSimp := false })
    (add unsafe 60% tactic goalAwareTacGen)

/-!
## Demo 2: right branch first

This has the same target shape as Demo 1, but the available hypothesis is
`hQ : Q`. The generator sees that the right side is immediately plausible and
assigns `right` a higher probability than `left`, even though `left` is returned
first by the generator.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {P Q : Prop} (hQ : Q) : P \/ Q := by
  aesop (rule_sets := [-default, -builtin])
    (config := { enableSimp := false })
    (add unsafe 60% tactic goalAwareTacGen)

/-!
## Demo 3: conjunction creates ordered subgoals

For an `And` goal, the generator proposes `constructor` at 90%. That produces
two children. Each child is then solved by a later generator call using the
`assumption` fallback at 95%.

The resulting child priorities are products of the probabilities along the
path, so the assumption leaves show roughly `90% * 95%`.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {P Q : Prop} (hP : P) (hQ : Q) : P /\ Q := by
  aesop (rule_sets := [-default, -builtin])
    (config := { enableSimp := false })
    (add unsafe 60% tactic goalAwareTacGen)

/-!
## Demo 4: fallback tactic ordering

There is no hypothesis of type `n = n`, so the generator puts `rfl` before
`assumption`. Only successful generated tactics become rule applications, so
the trace should show the `rfl` application for this leaf goal.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example (n : Nat) : n = n := by
  aesop (rule_sets := [-default, -builtin])
    (config := { enableSimp := false })
    (add unsafe 60% tactic goalAwareTacGen)

/-!
## Demo 5: proof reconstruction

`trace.aesop.proof` prints the proof term/script that Aesop reconstructs from
the successful generated tactic applications.
-/

set_option trace.aesop.proof true in
example {P Q : Prop} (hQ : Q) : P \/ Q := by
  aesop (rule_sets := [-default, -builtin])
    (config := { enableSimp := false })
    (add unsafe 60% tactic goalAwareTacGen)

end AesopTacGenExamples
