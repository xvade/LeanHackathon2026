import Lean.Meta.Tactic.Grind.Split

open Lean Meta

namespace NeuralTactic

/-- Log a neural split decision to stdout for debugging. -/
def logSplitDecision (goalPP : String) (candPPs : Array String) (scores : Array Float) (chosenIdx : Nat) : IO Unit :=
  IO.println s!"[neural_grind] goal={goalPP} chosen={chosenIdx}/{candPPs.size} score={scores.getD chosenIdx 0.0}"

end NeuralTactic
