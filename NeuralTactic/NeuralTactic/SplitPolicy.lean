import Lean.Meta.Tactic.Grind.Split

open Lean Meta

namespace NeuralTactic

/--
Score a (goal, candidate) pair by calling the inference server.

The server (scripts/server.py) must be running:
  python3 scripts/server.py &

Implemented in native/score_client.c via a Unix socket to /tmp/neural_grind.sock.
Falls back to a length heuristic if the server is not reachable, so proofs still
work even without the server (just with a weaker policy).
-/
@[extern "lean_neural_score"]
opaque scoreCandidate (goalPP : @& String) (candPP : @& String) : Float


def neuralSplitNext (stopAtFirstFailure := true) (compress := true) : Grind.Action :=
  fun goal kna kp => do
    -- Get candidate pool, capturing the updated goal state
    let (anchors, goal') ← Grind.GoalM.run goal Grind.getSplitCandidateAnchors
    if anchors.candidates.isEmpty then
      kna goal'
    else
      -- Pretty-print goal and all candidates (text in, text out — no serialization)
      let goalPP  ← Format.pretty <$> ppExpr (← goal'.mvarId.getType)
      let candPPs ← anchors.candidates.mapM fun c =>
        Format.pretty <$> ppExpr c.e
      -- Score every candidate via the inference backend
      let scores := candPPs.map (scoreCandidate goalPP)
      -- Select the highest-scoring candidate (argmax), using Option to avoid Inhabited requirement
      let best := (anchors.candidates.zip scores).foldl (fun acc (cand, score) =>
        match acc with
        | none => some (cand, score)
        | some (_, bestScore) => if score > bestScore then some (cand, score) else acc
      ) (none : Option (Grind.SplitCandidateWithAnchor × Float))
      let some (bestCand, _) := best | kna goal'
      -- Compute intro generation and perform the split on the chosen candidate
      let gen := goal'.getGeneration bestCand.e
      let genNew := if bestCand.numCases > 1 || bestCand.isRec then gen + 1 else gen
      let x : Grind.Action :=
        Grind.Action.splitCore bestCand.c bestCand.numCases bestCand.isRec stopAtFirstFailure compress >>
        Grind.Action.intros genNew >>
        Grind.Action.assertAll
      x goal' kna kp

end NeuralTactic
