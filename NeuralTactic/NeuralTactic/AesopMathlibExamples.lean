import Aesop
import Mathlib.Algebra.Group.Nat.Even
import Mathlib.Data.List.Basic
import Mathlib.Data.Set.Basic
import Mathlib.Order.Basic

/-!
# Aesop with mathlib: tracing rule selection and ordering

Open this file in the Lean editor and inspect the InfoView output for each
example.

Useful trace options:

* `trace.aesop`: step-by-step search.
* `trace.aesop.debug`: prints `rule selection` blocks. These are the rules
  returned by the index for the current goal, after sorting.
* `trace.aesop.ruleSet`: prints the whole rule set before search, including
  indexing buckets and priorities.
* `trace.aesop.tree`: prints the final search tree.
* `trace.aesop.proof`: prints the generated proof term.

Ordering to look for:

* Norm and safe rules are sorted by integer penalty, then rule name.
* Unsafe rules are sorted by descending success probability, then rule name.

Several examples use `(rule_sets := [-default])` to keep mathlib's large default
Aesop rule set out of the trace. The builtin rule set is still active, and the
mathlib lemmas named in each `(add ...)` clause are added locally.
-/

namespace AesopMathlibExamples

/-!
## Normalisation can solve set membership goals

The debug trace shows normalisation selecting the builtin `intros` rule and
then closing the goal with Aesop's norm simp step. The simp theorem used here
comes from mathlib's set membership API.
-/

set_option trace.aesop true in
set_option trace.aesop.debug true in
example {α : Type} {s t : Set α} {x : α} (h : x ∈ s ∩ t) : x ∈ t ∩ s := by
  aesop

/-!
## A local mathlib lemma as an unsafe rule

`Even.add` is a mathlib theorem. The `trace.aesop.debug` output for the unsafe
phase contains a block like:

```
selected rules:
  unsafe|apply|global|Even.add
  unsafe|tactic|global|Aesop.BuiltinRules.applyHyps
```

The first rule creates the two subgoals `Even m` and `Even n`, which are then
closed by normalisation/simp from the hypotheses.
-/
-- set_option trace.aesop.script true in
-- set_option trace.aesop true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {m n : Nat} (hm : Even m) (hn : Even n) : Even (m + n) := by
  aesop (rule_sets := [-default])
    (add unsafe 90% apply Even.add)

/-!
## Unsafe rule ordering by success probability

This one is meant to be read with both traces open:

* `trace.aesop.ruleSet` shows the locally added probabilities:
  `le_trans` at `80%` and `le_of_eq` at `20%`.
* `trace.aesop.debug` shows the applicable unsafe rules for the goal after
  indexing and sorting. The builtin `applyHyps` rule has probability `75%`, so
  the unsafe order is:

```
le_trans        -- 80%
applyHyps       -- 75%
le_of_eq        -- 20%
```
-/

set_option trace.aesop.script true in
set_option trace.aesop.ruleSet true in
set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {a b c : Nat} (hab : a <= b) (hbc : b <= c) : a <= c := by
  aesop (rule_sets := [-default])
    (add unsafe 80% apply le_trans, unsafe 20% apply le_of_eq)

/-!
## Safe rule indexing and ordering

Here `List.mem_append_left` is added as a safe rule with penalty `0`.

In the `trace.aesop.ruleSet` output, look under:

```
Safe rules
  Indexed by target
```

You should see:

```
[0/safe] safe|apply|global|List.mem_append_left
```

In the `trace.aesop.debug` `Safe rules` phase, the selected rules are the
currently applicable safe rules sorted by penalty. The builtin assumption rule
has penalty `-50`, so it is tried before this local list rule when it matches.

Simp is disabled for this example so that normalisation does not close the goal
before the safe-rule phase.
-/

set_option trace.aesop true in
set_option trace.aesop.ruleSet true in
set_option trace.aesop.debug true in
example {α : Type} {xs ys : List α} {x : α} (hx : x ∈ xs) :
    x ∈ xs ++ ys := by
  aesop (rule_sets := [-default])
    (config := { enableSimp := false })
    (add safe 0 apply List.mem_append_left)

/-!
## Generated proof term

`trace.aesop.proof` prints the final proof term after proof reconstruction.
This is useful when you want to replace a search-heavy `aesop` call with a more
explicit proof.
-/

set_option trace.aesop.proof true in
example {m n : Nat} (hm : Even m) (hn : Even n) : Even (m + n) := by
  aesop (rule_sets := [-default])
    (add unsafe 90% apply Even.add)


open Lean Meta

meta def brancher : Aesop.TacGen := fun goal => do
  goal.withContext do
    let target ← instantiateMVars (← goal.getType)
    if target.isAppOf ``Or then
      return #[("left", 0.80), ("right", 0.40)]
    else if target.isAppOf ``And then
      return #[("constructor", 0.90)]
    else
      return #[("assumption", 0.70), ("rfl", 0.20)]


set_option trace.aesop true in
set_option trace.aesop.ruleSet true in
set_option trace.aesop.debug true in
example {P Q : Prop} (hP : P) : P ∨ Q := by
  aesop (rule_sets := [-default])
    (config := { enableSimp := false })
    (add unsafe 60% tactic brancher)


set_option trace.aesop.debug true in
set_option trace.aesop.tree true in
example {P Q R : Prop} (hP : P) (hQ : Q) (hR : R) : ((P → Q) ∧ R) ∨ (¬P ∧ ¬R) := by
  aesop
    (rule_sets := [-default])
    (config := { enableSimp := false })

end AesopMathlibExamples
