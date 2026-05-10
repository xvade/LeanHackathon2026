import Aesop

/-!
# Aesop global goal queue examples

Aesop has two different queues that are easy to conflate:

* The per-goal unsafe-rule queue decides which unsafe rule to try next on one
  selected goal.
* The global active-goal queue decides which active goal in the whole search
  tree gets expanded next.

This file demonstrates the second queue.

The examples use a small `TacGen` so the produced branch probabilities are
predictable. They also disable the default and builtin rule sets, apart from
Aesop's always inserted preprocess rule, so the trace mostly shows the behavior
we care about.
-/

open Lean Meta

namespace AesopGoalQueueExamples

private def binaryArgs? (declName : Name) (e : Expr) : Option (Expr × Expr) :=
  if e.isAppOf declName then
    let args := e.getAppArgs
    if h : args.size = 2 then
      some (args[0], args[1])
    else
      none
  else
    none

private def hasLocalHypDefEq (type : Expr) : MetaM Bool := do
  let lctx <- getLCtx
  for localDecl in lctx do
    unless localDecl.isImplementationDetail do
      let localType <- instantiateMVars localDecl.type
      if <- withNewMCtxDepth <| isDefEq localType type then
        return true
  return false

/--
Heuristic evidence that a goal is locally easy. Atomic propositions are easy
when there is a matching local hypothesis. A conjunction is easy when both
parts have matching local hypotheses.
-/
private def hasLocalEvidence (type : Expr) : MetaM Bool := do
  if let some (left, right) := binaryArgs? ``And type then
    return (← hasLocalHypDefEq left) && (← hasLocalHypDefEq right)
  else
    hasLocalHypDefEq type

/--
The generated tactic order is intentionally sometimes worse than the generated
probability order. This lets the traces show the global queue selecting the
higher-priority goal, not merely the first tactic returned by the generator.
-/
def queueDemoTacGen : Aesop.TacGen := fun goal => do
  goal.withContext do
    let target <- instantiateMVars (← goal.getType)
    if let some (leftTarget, rightTarget) := binaryArgs? ``Or target then
      let leftEasy <- hasLocalEvidence leftTarget
      let rightEasy <- hasLocalEvidence rightTarget
      match leftEasy, rightEasy with
      | true, false => return #[("right", 0.30), ("left", 0.95)]
      | false, true => return #[("left", 0.30), ("right", 0.95)]
      | true, true =>
        if (binaryArgs? ``And leftTarget).isSome then
          return #[("right", 0.45), ("left", 0.90)]
        else
          return #[("right", 0.85), ("left", 0.90)]
      | false, false => return #[("right", 0.45), ("left", 0.50)]
    else if (binaryArgs? ``And target).isSome then
      return #[("constructor", 0.90)]
    else if <- hasLocalHypDefEq target then
      return #[("assumption", 0.95), ("rfl", 0.15)]
    else
      return #[("rfl", 0.70), ("assumption", 0.15)]

/-!
## Demo 1: best-first expands the higher-probability child

The generator returns `right` first at 30%, then `left` at 95%. Both generated
tactics succeed on the root goal, so both child goals are inserted into the
global active-goal queue:

```
Q : 30%
P : 95%
```

With the default best-first strategy, Aesop expands the `P` goal first even
though it was generated second.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {P Q : Prop} (hP : P) : P \/ Q := by
  aesop (rule_sets := [-default, -builtin])
    (config := { strategy := .bestFirst, enableSimp := false })
    (add unsafe 60% tactic queueDemoTacGen)

/-!
## Demo 2: breadth-first ignores those probabilities

This is the same proof shape as Demo 1, but the strategy is breadth-first.
The low-probability `right` branch was generated first, so breadth-first
explores it before the high-probability `left` branch.

The proof still succeeds after the `right` branch fails, because the `left`
branch remains active in the global queue.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {P Q : Prop} (hP : P) : P \/ Q := by
  aesop (rule_sets := [-default, -builtin])
    (config := { strategy := .breadthFirst, enableSimp := false })
    (add unsafe 60% tactic queueDemoTacGen)

/-!
## Demo 3: a tactic that produces multiple subgoals

For `P /\ Q`, the generated tactic is `constructor` at 90%. This is one rule
application that creates two child goals. Both child goals inherit the same
priority from that rule application:

```
P : 90%
Q : 90%
```

This illustrates an important limitation: Aesop's built-in queue score is
attached to a rule application, not individually to each subgoal produced by a
multi-subgoal tactic.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {P Q : Prop} (hP : P) (hQ : Q) : P /\ Q := by
  aesop (rule_sets := [-default, -builtin])
    (config := { strategy := .bestFirst, enableSimp := false })
    (add unsafe 60% tactic queueDemoTacGen)

/-!
## Demo 4: multi-subgoal branch competing with another branch

The root goal is `(P /\ Q) \/ R`.

The generator returns:

```
right : 45%   -- child goal R
left  : 90%   -- child goal P /\ Q
```

Best-first expands the `P /\ Q` child before the `R` child. Then `constructor`
on `P /\ Q` creates two subgoals, each with priority roughly `90% * 90%`.
Those subgoals still outrank the waiting `R` branch at 45%, so the global queue
continues down the left branch.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {P Q R : Prop} (hP : P) (hQ : Q) (hR : R) : (P /\ Q) \/ R := by
  aesop (rule_sets := [-default, -builtin])
    (config := { strategy := .bestFirst, enableSimp := false })
    (add unsafe 60% tactic queueDemoTacGen)

end AesopGoalQueueExamples
