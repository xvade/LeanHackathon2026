/-
  aesop_with_overrides tactic: wraps standard aesop but overrides the success
  probabilities of named unsafe rules before running the search.

  Override source: a JSON file whose path is given by the environment variable
  AESOP_OVERRIDES_JSON.  If the variable is unset the tactic behaves identically
  to aesop.

  JSON schema (values are floats in [0, 1]):
    { "Nat.succ_pos": 0.9, "List.append_nil": 0.05 }
  Keys are fully-qualified declaration names; values are the new success
  probabilities.  Only unsafe rules are affected (safe and norm rules have
  integer penalties, not probabilities).
-/

import Aesop
import Lean.Data.Json

namespace AesopWithOverrides

open Lean Lean.Meta Lean.Elab Lean.Elab.Tactic

-- ---------------------------------------------------------------------------
-- Name utilities
-- ---------------------------------------------------------------------------

/-- Convert a dotted string like "Nat.succ_pos" to the Lean Name `Nat.succ_pos`. -/
private def stringToName (s : String) : Name :=
  s.splitOn "." |>.foldl (fun n part => Name.mkStr n part) Name.anonymous

-- ---------------------------------------------------------------------------
-- JSON override loading
-- ---------------------------------------------------------------------------

/--
  Load probability overrides from the file named by `AESOP_OVERRIDES_JSON`.
  Returns an empty map when the variable is unset.
  The second return value is a display-ready list of `(ruleName, rawFloat)` pairs.
-/
private def loadOverrides :
    IO (Std.HashMap Name Aesop.Percent × Array (String × Float)) := do
  let some path ← IO.getEnv "AESOP_OVERRIDES_JSON" | return ({}, #[])
  let contents ← IO.FS.readFile path
  let json     ← IO.ofExcept (Json.parse contents)
  let fields   ← IO.ofExcept (json.getObj?)
  let mut map  : Std.HashMap Name Aesop.Percent := {}
  let mut disp : Array (String × Float) := #[]
  for (k, v) in fields.toArray do
    let n ← IO.ofExcept (v.getNum?)
    let f := n.toFloat
    match Aesop.Percent.ofFloat f with
    | some p =>
      map  := map.insert (stringToName k) p
      disp := disp.push (k, f)
    | none =>
      throw (IO.Error.userError
        s!"aesop_with_overrides: probability {f} for '{k}' must be in [0, 1]")
  return (map, disp)

-- ---------------------------------------------------------------------------
-- Rule-set patching
-- ---------------------------------------------------------------------------

/--
  Rebuild an `Index UnsafeRuleInfo`, replacing the `successProbability` of any
  rule whose declaration name appears in `overrides`.
  Returns the patched index and the names of rules that were actually matched.
-/
private def patchUnsafeIndex (overrides : Std.HashMap Name Aesop.Percent)
    (idx : Aesop.Index Aesop.UnsafeRuleInfo)
    : Aesop.Index Aesop.UnsafeRuleInfo × Array Name :=
  idx.fold (init := (∅, #[])) fun (acc, hit) rule =>
    match overrides[rule.name.name]? with
    | some prob =>
      let rule' := { rule with extra := { successProbability := prob } }
      (acc.add rule' rule'.indexingMode, hit.push rule.name.name)
    | none =>
      (acc.add rule rule.indexingMode, hit)

/--
  Apply `overrides` to every unsafe rule in `rs`.  Safe and norm rules are left
  unchanged (they use integer penalties, not success probabilities).
  Returns the patched rule set and the names of rules that were actually matched.
-/
def applyOverrides (overrides : Std.HashMap Name Aesop.Percent)
    (rs : Aesop.LocalRuleSet) : Aesop.LocalRuleSet × Array Name :=
  if overrides.isEmpty then (rs, #[])
  else
    -- LocalRuleSet.onBase threads an extra return value α out of the closure,
    -- which lets us return both the patched rule set and the hit list.
    rs.onBase fun base =>
      let (patchedIdx, hit) := patchUnsafeIndex overrides base.unsafeRules
      ({ base with unsafeRules := patchedIdx }, hit)

-- ---------------------------------------------------------------------------
-- Tactic syntax
-- ---------------------------------------------------------------------------

/-
  We reuse `Aesop.tactic_clause` (declared by the upstream aesop package) so
  the new tactic accepts exactly the same clauses as `aesop`.
-/
/--
`aesop_with_overrides` behaves like `aesop` but reads success-probability
overrides from a JSON file before running the search.

Set `AESOP_OVERRIDES_JSON=/path/to/overrides.json` in the environment.
The file must be a JSON object mapping fully-qualified declaration names to
floats in [0, 1]:
```json
{ "Nat.succ_pos": 0.9, "List.append_nil": 0.05 }
```
Only *unsafe* rules are affected (safe/norm rules have integer penalties).
When the environment variable is unset the tactic is identical to `aesop`.

Accepts the same clauses as `aesop`: `(add ...)`, `(erase ...)`,
`(rule_sets := [...])`, `(config := ...)`, `(simp_config := ...)`.
-/
syntax (name := aesopWithOverridesTactic)
    "aesop_with_overrides" (ppSpace colGt Aesop.tactic_clause)* : tactic

@[inherit_doc aesopWithOverridesTactic]
syntax (name := aesopWithOverridesTactic?)
    "aesop_with_overrides?" (ppSpace colGt Aesop.tactic_clause)* : tactic

-- ---------------------------------------------------------------------------
-- Elaborators
-- ---------------------------------------------------------------------------

private def runWithOverrides (clauses : Array (TSyntax `Aesop.tactic_clause))
    (traceScript : Bool) : TacticM Unit := do
  let goal ← getMainGoal
  goal.withContext do
    let aesopStx ←
      if traceScript then `(tactic| aesop? $clauses*)
      else `(tactic| aesop $clauses*)
    let config  ← Aesop.Frontend.TacticConfig.parse aesopStx goal
    let ruleSet ← config.getRuleSet goal
    let (overrides, disp) ← loadOverrides
    let (ruleSet', hit) := applyOverrides overrides ruleSet
    -- Emit an Information diagnostic listing requested vs matched overrides.
    if !overrides.isEmpty then
      let requested := disp.foldl (init := "")
        fun s (name, prob) => s ++ s!"\n  {name} → {prob}"
      let matched :=
        if hit.isEmpty then "\n  (none — check that rule names are fully qualified)"
        else hit.foldl (init := "") fun s n => s ++ s!"\n  {n}"
      logInfo s!"aesop_with_overrides overrides loaded:{requested}\nmatched unsafe rules:{matched}"
    let (goals, stats) ←
      Aesop.search goal (ruleSet? := some ruleSet')
        config.options config.simpConfig config.simpConfigSyntax?
    stats.trace .stats
    replaceMainGoal goals.toList

@[tactic aesopWithOverridesTactic]
def evalAesopWithOverrides : Tactic := fun stx =>
  match stx with
  | `(tactic| aesop_with_overrides $clauses:Aesop.tactic_clause*) =>
    runWithOverrides clauses (traceScript := false)
  | _ => throwUnsupportedSyntax

@[tactic aesopWithOverridesTactic?]
def evalAesopWithOverrides? : Tactic := fun stx =>
  match stx with
  | `(tactic| aesop_with_overrides? $clauses:Aesop.tactic_clause*) =>
    runWithOverrides clauses (traceScript := true)
  | _ => throwUnsupportedSyntax

end AesopWithOverrides
