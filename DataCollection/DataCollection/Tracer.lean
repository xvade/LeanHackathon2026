/-
`DataCollection.Tracer` — grind trace and candidate-pool collection.

Provides two tactics:

  `grind_trace`   — records goal, events (including splits), and solved flag.

  `grind_collect` — at each split decision, captures the full candidate pool
                    (human-readable pp for every candidate) and which candidate
                    grind actually chose. This is the ranking model's training signal.

Output schema for `grind_collect` (one JSON line per theorem):
  {
    "theoremName": "...",
    "goalPP":      "...",
    "solved":      true/false,
    "splitDecisions": [
      { "pool": [{"pp": "..."}, ...], "chosenIdx": N },
      ...
    ]
  }
-/
import Lean
import Lean.Elab.Tactic.Grind
import Lean.Meta.Tactic.Grind.Split
import Lean.Meta.Tactic.Grind.Main
import Lean.Meta.Tactic.Grind.Finish
import Lean.Meta.Tactic.Grind.EMatchAction
import Lean.Meta.Tactic.Grind.Intro

open Lean Meta Elab Tactic Grind

namespace DataCollection

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
  pp : String  -- human-readable expression; fed directly to the ranking model
  deriving ToJson

structure SplitDecision where
  pool      : Array CandidateInfo
  chosenIdx : Nat  -- index of the candidate grind's heuristic selected
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
def collectingAction
    (decisions : IO.Ref (Array SplitDecision))
    (compress := true) : Action :=
  fun goal kna kp => do
    let (anchors, goal) ← GoalM.run goal getSplitCandidateAnchors
    if anchors.candidates.isEmpty then
      kna goal
    else
      -- Build the pool: just pretty-printed expressions, no serialization
      let (pool, _) ← GoalM.run goal do
        anchors.candidates.mapM fun c => do
          return { pp := Format.pretty (← ppExpr c.e) : CandidateInfo }
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
      let chosenIdx := match chosenPP? with
        | none    => 0  -- fallback: trace not captured (shouldn't happen)
        | some pp => (pool.toList.findIdx? fun c => c.pp == pp).getD 0
      decisions.modify fun ds => ds.push { pool, chosenIdx }
      return result

/-- Assemble a finish action that collects split decisions. -/
def mkCollectFinish
    (decisions : IO.Ref (Array SplitDecision))
    (maxIter   : Nat := Action.maxIterationsDefault) : IO Action := do
  let solvers ← Solvers.mkAction
  let step : Action :=
    solvers <|> Action.instantiate <|> collectingAction decisions <|> Action.mbtc
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
  let solved ← try
    Grind.withProtectedMCtx config mvarId fun mvarId' => do
      let result ← Grind.GrindM.runAtGoal mvarId' params fun goal => do
        let finish ← mkCollectFinish decisions
        match (← finish.run goal) with
        | .closed _ => pure true
        | .stuck _  => pure false
      replaceMainGoal []
      return result
  catch _ => pure false
  let splitDecisions ← decisions.get
  IO.println (toJson (CollectSample.mk thmName goalPP solved splitDecisions)).compress

end DataCollection
