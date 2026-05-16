/-
  aesop_audit — dump every @[aesop]-tagged declaration from Mathlib to JSONL.

  Usage (from this directory):
      lake build && .lake/build/bin/aesop_audit [output.jsonl]

  The output path defaults to `aesop_mathlib_rules.jsonl` in the CWD.

  Each JSONL record has:
    name               : fully-qualified declaration name (String)
    phase              : "norm" | "safe" | "unsafe"
    builder            : "apply" | "cases" | "constructors" | "destruct" |
                         "forward" | "simp" | "tactic" | "unfold"
    scope              : "global" | "local"
    penalty            : Int    (norm / safe rules only)
    safety             : String (safe rules only: "safe" | "almostSafe")
    successProbability : Float  (unsafe rules only, in [0, 1])
    ruleSets           : [String]  (all rule sets this rule appears in)
    kind               : "theorem" | "def" | "axiom" | "inductive" | …
    statement          : pretty-printed type, or "" if unavailable

  Implementation notes
  ────────────────────
  • getDeclaredRuleSets is IO (reads an IO.Ref populated by module initializers
    that run when withImportModules loads Mathlib).
  • ext.getState env is pure (extension state is baked into the .olean).
  • Index.fold is pure but visits rules indexed by both target and hypothesis
    trees twice; we deduplicate per-index with a PHashSet.
  • ppExpr is MetaM; we run it through IO.mkRef + StateRefT' and fall back to
    "" on any failure.
-/

-- Import Mathlib at compile time so that this binary's extension-registration
-- order matches Mathlib's compiled oleans exactly.  Without this, any module
-- imported here but NOT in Mathlib's dep chain before Aesop would shift every
-- Aesop extension's index, causing ext.getState(env) to return empty.
import Mathlib
import Aesop

open Lean Meta Aesop Aesop.Frontend

-- ============================================================
-- String conversions
-- ============================================================

private def phaseStr : PhaseName → String
  | .norm   => "norm"
  | .safe   => "safe"
  | .unsafe => "unsafe"

private def builderStr : BuilderName → String
  | .apply        => "apply"
  | .cases        => "cases"
  | .constructors => "constructors"
  | .destruct     => "destruct"
  | .forward      => "forward"
  | .simp         => "simp"
  | .tactic       => "tactic"
  | .unfold       => "unfold"

private def scopeStr : ScopeName → String
  | .global => "global"
  | .local  => "local"

private def safetyStr : Safety → String
  | .safe       => "safe"
  | .almostSafe => "almostSafe"

private def kindOf : ConstantInfo → String
  | .thmInfo _    => "theorem"
  | .defnInfo _   => "def"
  | .axiomInfo _  => "axiom"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _   => "quotient"
  | .inductInfo _ => "inductive"
  | .ctorInfo _   => "constructor"
  | .recInfo _    => "recursor"

-- ============================================================
-- Run MetaM from IO
-- ============================================================

-- CoreM = ReaderT Core.Context (StateT Core.State (EIO Exception))
-- act.run ctx       : Core.State → EIO Exception (α × Core.State)
-- act.run ctx state : EIO Exception (α × Core.State)
-- EIO.toIO converts that to IO (α × Core.State).

private def runCoreM {α} (env : Environment) (act : CoreM α) : IO α := do
  let ctx : Core.Context := {
    fileName := "<aesop_audit>"
    fileMap  := FileMap.ofString ""
  }
  let initState : Core.State := { env }
  let (a, _) ← EIO.toIO (fun _ => IO.Error.userError "CoreM error")
    (act.run ctx initState)
  return a

-- MetaM.run' converts MetaM α → CoreM α (handles the inner StateRefT' itself).
private def runMetaM {α} (env : Environment) (act : MetaM α) : IO α :=
  runCoreM env (MetaM.run' act)

-- Pretty-print a declaration type; returns "" on any failure.
private def ppDeclType (env : Environment) (name : Name) : IO String :=
  match env.find? name with
  | none    => return ""
  | some ci =>
    try
      let fmt ← runMetaM env (ppExpr ci.type)
      return fmt.pretty
    catch _ => return ""

-- ============================================================
-- Rule accumulator
-- (Avoid naming it `Acc` – `open Meta` brings Lean.Meta.Acc into scope.)
-- ============================================================

-- Maps each unique RuleName → (base JSON field list, rule-set names)
private abbrev RuleMap := Std.HashMap RuleName (Array (String × Json) × Array String)

private def rmUpsert (m : RuleMap) (rn : RuleName)
    (fields : Array (String × Json)) (rsName : String) : RuleMap :=
  match m[rn]? with
  | some (fs, rss) => m.insert rn (fs, rss.push rsName)
  | none           => m.insert rn (fields, #[rsName])

private def rnBaseFields (rn : RuleName) : Array (String × Json) :=
  #[("name",    .str rn.name.toString),
    ("phase",   .str (phaseStr rn.phase)),
    ("builder", .str (builderStr rn.builder)),
    ("scope",   .str (scopeStr rn.scope))]

-- Fold a single rule index (norm / safe / unsafe), deduplicating by RuleName.
-- Index.fold iterates byHyp, byTarget, and unindexed — a rule indexed under
-- both byHyp and byTarget appears twice.  The PHashSet `seen` prevents that.
-- No typeclass constraints on α needed here: Rule α always has BEq/Hashable.
private def collectIdx
    (m : RuleMap) (erased : PHashSet RuleName) (rsName : String)
    (idx : Index α) (extra : Rule α → Array (String × Json)) : RuleMap :=
  (idx.fold
    (init := (m, ({} : PHashSet RuleName)))
    fun (m, seen) rule =>
      if seen.contains rule.name || erased.contains rule.name then (m, seen)
      else
        let fields := rnBaseFields rule.name ++ extra rule
        (rmUpsert m rule.name fields rsName, seen.insert rule.name)
  ).1

private def collectBase (m : RuleMap) (rsName : String) (base : BaseRuleSet) : RuleMap :=
  -- Normalisation rules
  let m := collectIdx m base.erased rsName base.normRules fun r =>
    #[("penalty", toJson r.extra.penalty)]
  -- Safe rules
  let m := collectIdx m base.erased rsName base.safeRules fun r =>
    #[("penalty", toJson r.extra.penalty),
      ("safety",  .str (safetyStr r.extra.safety))]
  -- Unsafe rules
  let m := collectIdx m base.erased rsName base.unsafeRules fun r =>
    #[("successProbability", toJson r.extra.successProbability.toFloat)]
  -- Unfold rules — stored in a separate PHashMap, not an Index
  base.unfoldRules.toArray.foldl (init := m) fun m (declName, _unfoldThm?) =>
    let rn : RuleName :=
      { name := declName, builder := .unfold, phase := .norm, scope := .global }
    if base.erased.contains rn then m
    else
      rmUpsert m rn
        (rnBaseFields rn |>.push ("penalty", toJson (0 : Int)))
        rsName

-- ============================================================
-- Top-level gather (IO throughout)
-- ============================================================

-- CoreM action: enumerate all rules via ext.getState (← getEnv).
private def collectAllRules : CoreM (Array (RuleName × Array (String × Json) × Array String)) := do
  let env ← getEnv
  let ruleSets ← getDeclaredRuleSets
  let mut ruleMap : RuleMap := {}
  for (rsName, (ext, _, _)) in ruleSets.toList do
    ruleMap := collectBase ruleMap rsName.toString (ext.getState env)
  return ruleMap.toList.toArray.map fun (rn, (fs, rss)) => (rn, fs, rss)

def gatherAesopRules (env : Environment) : IO (Array Json) := do
  let entries ← runCoreM env collectAllRules
  let mut records : Array Json := #[]
  for (rn, fields, rss) in entries do
    let stmtStr ← ppDeclType env rn.name
    let kindStr  := match env.find? rn.name with
                    | none    => "unknown"
                    | some ci => kindOf ci
    let record := Json.mkObj
      (fields ++ #[("ruleSets",  toJson rss),
                   ("statement", .str stmtStr),
                   ("kind",      .str kindStr)]).toList
    records := records.push record
  return records

-- ============================================================
-- Entry point
-- ============================================================

unsafe def main (args : List String) : IO Unit := do
  let outPath := args.getD 0 "aesop_mathlib_rules.jsonl"
  -- Set up the Lean library search path.
  -- `initSearchPath` adds only the core Lean stdlib (sysroot/lib/lean).
  -- `lake exe aesop_audit` also sets LEAN_PATH to include all Lake package
  -- olean dirs; we append those so that `withImportModules #[Mathlib]` works.
  Lean.initSearchPath (← Lean.findSysroot)
  if let some lp ← IO.getEnv "LEAN_PATH" then
    let extra : Lean.SearchPath :=
      lp.splitOn ":" |>.filter (· != "") |>.map System.FilePath.mk
    Lean.searchPathRef.modify (· ++ extra)
  IO.println "Importing Mathlib (uses cached .olean files; first run may take ~30 s)..."
  let records ← Lean.withImportModules
    #[{ module := `Mathlib }]
    (opts := {})
    (trustLevel := 0)
    (act := gatherAesopRules)
  IO.println s!"Writing {records.size} records to {outPath} ..."
  let h ← IO.FS.Handle.mk outPath .write
  for r in records do
    h.putStrLn r.compress
  IO.println "Done."
