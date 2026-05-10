import Lean
import Lean.Elab.Tactic.Grind
import Lean.Meta.Tactic.Grind.Split
import Lean.Meta.Tactic.Grind.Main
import Lean.Meta.Tactic.Grind.Finish
import Lean.Meta.Tactic.Grind.EMatchAction
import Lean.Meta.Tactic.Grind.Intro

open Lean Meta Elab Tactic Grind

namespace GrindExtraction

-- ── Shared trace infrastructure ───────────────────────────────────────────────

private def TRACE_CLASSES : List Name :=
  [`grind.eqc, `grind.split, `grind.ematch.instance.assignment, `grind.assert]

structure TraceEvent where
  cls : String
  msg : String
  deriving ToJson

private def splitTraceElem (elem : TraceElem) : Option (Name × MessageData) :=
  match elem.msg with
  | .trace data inner _ => some (data.cls, inner)
  | _                   => none

def withGrindTraces (action : TacticM α) : TacticM (α × Array TraceEvent) := do
  withOptions (fun opts =>
    TRACE_CLASSES.foldl (fun o cls => o.setBool (`trace ++ cls) true) opts
  ) do
    let snapBefore := (← getTraceState).traces.size
    let result ← action
    let allTraces := (← getTraceState).traces
    let newElems  := allTraces.toArray.extract snapBefore allTraces.size
    let events ← newElems.filterMapM fun elem => do
      match splitTraceElem elem with
      | none => return none
      | some (cls, inner) =>
        if !TRACE_CLASSES.contains cls then return none
        let fmt ← inner.format
        return some { cls := cls.toString, msg := Format.pretty fmt : TraceEvent }
    return (result, events)

-- ── grind_trace ───────────────────────────────────────────────────────────────

structure GrindTraceSample where
  theoremName : String
  goalPP      : String
  solved      : Bool
  events      : Array TraceEvent
  deriving ToJson

syntax (name := grindTrace) "grind_trace" : tactic

@[tactic grindTrace]
def evalGrindTrace : Tactic := fun _ => do
  let mvarId   ← getMainGoal
  let goalType ← mvarId.getType
  let goalPP   := Format.pretty (← ppExpr goalType)
  let thmName  := (← getEnv).mainModule.toString
  let (solved, events) ← withGrindTraces do
    try
      evalTactic (← `(tactic| grind))
      pure (← getUnsolvedGoals).isEmpty
    catch _ => pure false
  IO.println (toJson (GrindTraceSample.mk thmName goalPP solved events)).compress

-- ── grind_collect (full candidate pool with grind's actual choice) ────────────

structure CandidateInfo where
  anchor     : UInt64
  exprText   : String
  numCases   : Nat
  isRec      : Bool
  source     : String  -- "input" | "ematch" | "inj" | "ext" | "mbtc" | "beta" | "forallProp" | "existsProp" | "guard"
  generation : Nat     -- grind's internal generation counter; lower = older candidate
  tryPostpone : Bool
  variant    : String  -- "default" | "imp" | "arg"
  deriving ToJson

structure GoalFeatures where
  splitDepth : Nat
  assertedCount : Nat
  ematchRounds : Nat
  splitTraceLen : Nat
  numCandidates : Nat
  deriving ToJson

structure SplitDecision where
  step         : Nat
  goalFeatures : GoalFeatures
  statePP      : Array String   -- tactic proof state: local hyps + goal at this split
  grindState   : Array String   -- grind.assert + grind.eqc events accumulated so far
  pool         : Array CandidateInfo
  chosenAnchor : UInt64
  deriving ToJson

structure CollectSample where
  theoremName    : String
  goalPP         : String
  solved         : Bool
  splitDecisions : Array SplitDecision
  deriving ToJson

/--
Strip ", generation: N" from a grind.split trace message to get the candidate PP.
Example: "if a = true then b else false, generation: 0" → "if a = true then b else false"
-/
private def stripGeneration (msg : String) : String :=
  (msg.splitOn ", generation:").head!

/--
Custom split action for data collection.

At each split decision:
1. Captures the full candidate pool (PP of each expression).
2. Calls splitNext (grind's heuristic makes the actual decision).
3. Observes the grind.split trace to find which candidate was chosen.
4. Logs {pool, chosenIdx} — the ranking model's training signal.
-/
private def GRIND_STATE_CLASSES : List Name :=
  [`grind.assert, `grind.eqc, `grind.ematch.instance.assignment]

private def variantStr (si : SplitInfo) : String :=
  match si with
  | .default _ _ => "default"
  | .imp _ _ _   => "imp"
  | .arg _ _ _ _ _ => "arg"

private def sourceTagStr (si : SplitInfo) : String :=
  match si.source with
  | .ematch _     => "ematch"
  | .ext _        => "ext"
  | .mbtc _ _ _   => "mbtc"
  | .beta _       => "beta"
  | .forallProp _ => "forallProp"
  | .existsProp _ => "existsProp"
  | .input        => "input"
  | .inj _        => "inj"
  | .guard _      => "guard"

def collectingAction
    (decisions      : IO.Ref (Array SplitDecision))
    (proofSnapStart : Nat)    -- trace index at proof start (to accumulate from)
    (compress := true) : Action :=
  fun goal kna kp => do
    let (anchors, goal) ← GoalM.run goal getSplitCandidateAnchors
    if anchors.candidates.isEmpty then
      kna goal
    else
      -- Build the pool: anchor, exprText, numCases, isRec, source, generation
      let (pool, _) ← GoalM.run goal do
        anchors.candidates.mapM fun c => do
          let pp  := Format.pretty (← ppExpr c.e)
          let gen := goal.getGeneration c.e  -- pure: lower = older candidate
          let status ← checkSplitStatus c.c
          let tryPostpone := match status with
            | .ready _ _ tp => tp
            | _ => false
          return { anchor     := c.anchor
                   exprText   := pp
                   numCases   := c.numCases
                   isRec      := c.isRec
                   source     := sourceTagStr c.c
                   generation := gen
                   tryPostpone := tryPostpone
                   variant    := variantStr c.c : CandidateInfo }
      let numCandidates := anchors.candidates.size
      -- goal features
      let splitDepth := goal.split.num
      let assertedCount := goal.facts.size
      let ematchRounds := goal.ematch.num
      let splitTraceLen := goal.split.trace.length
      let goalFeatures := GoalFeatures.mk splitDepth assertedCount ematchRounds splitTraceLen numCandidates
      -- Tactic proof state: local hypotheses + goal (what you see in the infoview)
      let decl ← goal.mvarId.getDecl
      let hyps ← decl.lctx.foldlM (init := #[]) fun acc d => do
        if d.isImplementationDetail then return acc
        let typePP := Format.pretty (← ppExpr d.type)
        return acc.push s!"{d.userName} : {typePP}"
      let goalTypePP := Format.pretty (← ppExpr (← goal.mvarId.getType))
      let statePP := hyps.push s!"⊢ {goalTypePP}"
      -- Grind internal state: all grind.assert and grind.eqc events accumulated since proof start
      let allTracesSoFar := (← getTraceState).traces
      let grindState ← (allTracesSoFar.toArray.extract proofSnapStart allTracesSoFar.size).foldlM
        (init := #[]) fun acc elem => do
          match elem.msg with
          | .trace data inner _ =>
            if GRIND_STATE_CLASSES.contains data.cls then do
              let fmt ← inner.format
              return acc.push (Format.pretty fmt)
            else return acc
          | _ => return acc
      -- Enable grind.split trace to observe grind's actual choice
      let snapBefore := (← getTraceState).traces.size
      let result ← (Action.splitNext (stopAtFirstFailure := true) compress) goal kna kp
      -- Find the first grind.split event after the snap (= the split just made)
      let allTraces := (← getTraceState).traces
      let newElems  := allTraces.toArray.extract snapBefore allTraces.size
      let chosenPP? ← newElems.foldlM (fun acc elem =>
        match acc with
        | some _ => return acc  -- already found one
        | none   =>
          match elem.msg with
          | .trace data inner _ =>
            if data.cls == `grind.split then do
              let fmt ← inner.format
              return some (stripGeneration (Format.pretty fmt))
            else return none
          | _ => return none
      ) (none : Option String)
      -- Resolve chosenAnchor by matching chosen pretty-print to pool entries and using anchors array
      let chosenAnchor := match chosenPP? with
        | none => match anchors.candidates.toList with
          | [] => 0
          | a :: _ => SplitCandidateWithAnchor.anchor a
        | some pp =>
          let pairs := List.zip (anchors.candidates.toList) (pool.toList)
          match List.find? (fun p => CandidateInfo.exprText (Prod.snd p) == pp) pairs with
          | some p => SplitCandidateWithAnchor.anchor (Prod.fst p)
          | none => match anchors.candidates.toList with
            | [] => 0
            | a :: _ => SplitCandidateWithAnchor.anchor a
      let cur ← decisions.get
      let stepIdx := cur.size
      decisions.modify fun ds => ds.push { step := stepIdx, goalFeatures, statePP, grindState, pool, chosenAnchor }
      return result

/-- Assemble a finish action that collects split decisions. -/
def mkCollectFinish
    (decisions      : IO.Ref (Array SplitDecision))
    (proofSnapStart : Nat)
    (maxIter        : Nat := Action.maxIterationsDefault) : IO Action := do
  let solvers ← Solvers.mkAction
  let step : Action :=
    solvers <|> Action.instantiate <|> collectingAction decisions proofSnapStart <|> Action.mbtc
  return Action.checkTactic (warnOnly := true) >>
         Action.intros 0 >>
         Action.assertAll >>
         step.loop maxIter

syntax (name := grindCollect) "grind_collect" : tactic

@[tactic grindCollect]
def evalGrindCollect : Tactic := fun _ => do
  let mvarId   ← getMainGoal
  let goalType ← mvarId.getType
  let goalPP   := Format.pretty (← ppExpr goalType)
  let thmName  := (← getEnv).mainModule.toString
  let config   : Grind.Config := {}
  let params   ← Grind.mkDefaultParams config
  let decisions ← IO.mkRef #[]
  -- Enable grind state trace classes and snapshot before grind starts
  let proofSnapStart := (← getTraceState).traces.size
  let solved ← try
    withOptions (fun opts =>
      GRIND_STATE_CLASSES.foldl (fun o cls => o.setBool (`trace ++ cls) true) opts
    ) do
    Grind.withProtectedMCtx config mvarId fun mvarId' => do
      let result ← Grind.GrindM.runAtGoal mvarId' params fun goal => do
        let finish ← mkCollectFinish decisions proofSnapStart
        match (← finish.run goal) with
        | .closed _ => pure true
        | .stuck _  => pure false
      replaceMainGoal []
      return result
  catch _ => pure false
  let splitDecisions ← decisions.get
  IO.println (toJson (CollectSample.mk thmName goalPP solved splitDecisions)).compress

end GrindExtraction
