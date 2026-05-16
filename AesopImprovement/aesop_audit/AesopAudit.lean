/-
  AesopAudit.lean — dump every @[aesop]-tagged declaration to JSONL
                    by running at *elaboration time* (during `lake build`).

  Usage:
      lake build AesopAudit

  This produces `aesop_mathlib_rules.jsonl` in the directory where
  `lake build` is invoked (normally the project root).

  Why not a lean_exe with withImportModules?
  ─────────────────────────────────────────
  `withImportModules` creates a fresh Environment from oleans, but Lean 4's
  PersistentEnvExtension states are indexed by a per-process counter that
  increments as extensions are registered.  If the binary was compiled with
  a different import sequence than Mathlib's olean, every index is off by a
  constant and ext.getState(env) silently returns the initial empty state.

  Running inside `elab` sidesteps this entirely: the elaboration process
  imports everything in the correct order, the extension registry matches
  the compiled oleans, and getDeclaredGlobalRuleSets works as expected.
-/

import Mathlib
import Aesop

open Lean Meta Aesop Aesop.Frontend Lean.Elab Lean.Elab.Command

-- ============================================================
-- String helpers (duplicated here so this file is self-contained)
-- ============================================================

private def phaseStr' : PhaseName → String
  | .norm   => "norm"
  | .safe   => "safe"
  | .unsafe => "unsafe"

private def builderStr' : BuilderName → String
  | .apply        => "apply"
  | .cases        => "cases"
  | .constructors => "constructors"
  | .destruct     => "destruct"
  | .forward      => "forward"
  | .simp         => "simp"
  | .tactic       => "tactic"
  | .unfold       => "unfold"

private def scopeStr' : ScopeName → String
  | .global => "global"
  | .local  => "local"

private def safetyStr' : Safety → String
  | .safe       => "safe"
  | .almostSafe => "almostSafe"

private def kindOf' : ConstantInfo → String
  | .thmInfo _    => "theorem"
  | .defnInfo _   => "def"
  | .axiomInfo _  => "axiom"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _   => "quotient"
  | .inductInfo _ => "inductive"
  | .ctorInfo _   => "constructor"
  | .recInfo _    => "recursor"

-- ============================================================
-- Rule accumulator
-- ============================================================

private abbrev RuleMap' := Std.HashMap RuleName (Array (String × Json) × Array String)

private def upsert' (m : RuleMap') (rn : RuleName)
    (fields : Array (String × Json)) (rsName : String) : RuleMap' :=
  match m[rn]? with
  | some (fs, rss) => m.insert rn (fs, rss.push rsName)
  | none           => m.insert rn (fields, #[rsName])

private def rnBase' (rn : RuleName) : Array (String × Json) :=
  #[("name",    .str rn.name.toString),
    ("phase",   .str (phaseStr' rn.phase)),
    ("builder", .str (builderStr' rn.builder)),
    ("scope",   .str (scopeStr' rn.scope))]

private def collectIdx'
    (m : RuleMap') (erased : PHashSet RuleName) (rsName : String)
    (idx : Index α) (extra : Rule α → Array (String × Json)) : RuleMap' :=
  (idx.fold
    (init := (m, ({} : PHashSet RuleName)))
    fun (m, seen) rule =>
      if seen.contains rule.name || erased.contains rule.name then (m, seen)
      else
        let fields := rnBase' rule.name ++ extra rule
        (upsert' m rule.name fields rsName, seen.insert rule.name)
  ).1

private def collectBase' (m : RuleMap') (rsName : String) (base : BaseRuleSet) : RuleMap' :=
  let m := collectIdx' m base.erased rsName base.normRules fun r =>
    #[("penalty", toJson r.extra.penalty)]
  let m := collectIdx' m base.erased rsName base.safeRules fun r =>
    #[("penalty", toJson r.extra.penalty),
      ("safety",  .str (safetyStr' r.extra.safety))]
  let m := collectIdx' m base.erased rsName base.unsafeRules fun r =>
    #[("successProbability", toJson r.extra.successProbability.toFloat)]
  base.unfoldRules.toArray.foldl (init := m) fun m (declName, _) =>
    let rn : RuleName :=
      { name := declName, builder := .unfold, phase := .norm, scope := .global }
    if base.erased.contains rn then m
    else upsert' m rn (rnBase' rn |>.push ("penalty", toJson (0 : Int))) rsName

-- ============================================================
-- Elaboration-time command
-- ============================================================

/-- Collect all @[aesop] rules and write them to `outPath` as JSONL.
    Runs during `lake build`, so the environment is fully set up. -/
elab "#write_aesop_rules" outPath:str : command => do
  let env ← getEnv
  -- getDeclaredGlobalRuleSets is CoreM; lift it into CommandElabM explicitly.
  -- The extension IDs in declaredRuleSetsRef and the env were set by the
  -- same Lean process, so ext.getState(env) returns populated rule sets.
  let allRuleSets ← (getDeclaredGlobalRuleSets : CommandElabM _)
  let mut ruleMap : RuleMap' := {}
  for (rsName, rs, _, _) in allRuleSets do
    ruleMap := collectBase' ruleMap rsName.toString rs.toBaseRuleSet
  -- Build JSONL records with pretty-printed types.
  let mut lines : Array String := #[]
  for (rn, (fields, rss)) in ruleMap.toList do
    -- ppExpr is MetaM; runTermElabM goes from CommandElabM into TermElabM.
    let stmtStr ← runTermElabM (elabFn := fun _ => do
      match env.find? rn.name with
      | none    => return ""
      | some ci =>
        try pure (← ppExpr ci.type).pretty
        catch _ => return "")
    let kindStr := match env.find? rn.name with
                   | none    => "unknown"
                   | some ci => kindOf' ci
    let record := Json.mkObj
      (fields ++ #[("ruleSets",  toJson rss),
                   ("statement", .str stmtStr),
                   ("kind",      .str kindStr)]).toList
    lines := lines.push record.compress
  let path := outPath.getString
  let content := lines.toList.intersperse "\n" |>.foldl (· ++ ·) ""
  IO.FS.writeFile path content
  IO.println s!"[aesop_audit] wrote {lines.size} records to {path}"

-- ============================================================
-- Run it
-- ============================================================

#write_aesop_rules "aesop_mathlib_rules.jsonl"
