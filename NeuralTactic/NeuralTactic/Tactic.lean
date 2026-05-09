/-
`NeuralTactic.Tactic` — the `neural_grind` tactic.

Assembles a custom grind action loop that substitutes `neuralSplitNext` for `splitNext`,
then exposes it as the `neural_grind` tactic.

The action loop mirrors `Lean.Meta.Grind.Action.mkFinish` line-for-line, with one change:
  `solvers <|> instantiate <|> splitNext    <|> mbtc`  →
  `solvers <|> instantiate <|> neuralSplitNext <|> mbtc`

All components (`Solvers.mkAction`, `instantiate`, `mbtc`, `checkTactic`, `intros`,
`assertAll`) are part of grind's public API — no private copies needed.
-/
import Lean.Elab.Tactic.Basic
import Lean.Meta.Tactic.Grind.Main
import Lean.Meta.Tactic.Grind.Finish
import Lean.Meta.Tactic.Grind.EMatchAction
import Lean.Meta.Tactic.Grind.Intro
import NeuralTactic.SplitPolicy

open Lean Meta Elab Tactic

namespace NeuralTactic

/--
Custom grind action loop with `neuralSplitNext` swapped in for `splitNext`.
Mirrors `Lean.Meta.Grind.Action.mkFinish`.
-/
def mkNeuralFinish (maxIterations : Nat := Grind.Action.maxIterationsDefault) : IO Grind.Action := do
  let solvers ← Grind.Solvers.mkAction
  let step : Grind.Action :=
    solvers <|> Grind.Action.instantiate <|> neuralSplitNext <|> Grind.Action.mbtc
  return Grind.Action.checkTactic (warnOnly := true) >>
         Grind.Action.intros 0 >>
         Grind.Action.assertAll >>
         step.loop maxIterations

/-- Run the neural-split grind loop on a single goal mvar. -/
private def neuralMain (mvarId : MVarId) (params : Grind.Params) : MetaM Grind.Result :=
  Grind.GrindM.runAtGoal mvarId params fun goal => do
    let finish ← mkNeuralFinish
    let failure? ← match (← finish.run goal) with
      | .closed _ => pure none
      | .stuck (g :: _) => pure (some g)
      | .stuck [] => pure none
    Grind.mkResult params failure?

syntax (name := neuralGrind) "neural_grind" : tactic

/--
`neural_grind` runs grind with a learned split-candidate ranker instead of the default
heuristic. Currently uses a simple scoring function; swap `scoreCandidate` in
`SplitPolicy.lean` for a neural model call to enable the full ML pipeline.
-/
@[tactic neuralGrind]
def evalNeuralGrind : Tactic := fun _ => do
  let mvarId ← getMainGoal
  let config : Grind.Config := {}
  let params ← Grind.mkDefaultParams config
  Grind.withProtectedMCtx config mvarId fun mvarId' => do
    let result ← neuralMain mvarId' params
    if result.hasFailed then
      throwError "`neural_grind` failed\n{← result.toMessageData}"
    replaceMainGoal []

end NeuralTactic
