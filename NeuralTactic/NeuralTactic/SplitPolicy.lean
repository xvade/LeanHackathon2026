/-
`NeuralTactic.SplitPolicy` — neural split-candidate ranker.

At each split decision `neuralSplitNext`:
  1. Pretty-prints the current goal and every candidate expression.
  2. Calls `scoreCandidate` (→ C FFI → Unix socket → server.py) to score them.
  3. Currently delegates the actual split to `splitNext` regardless of scores.

The scores are computed for real on every call but not yet used to override
grind's split selection. The remaining work is using the model's argmax to call
`splitCore` directly — blocked on the side-effect issue documented in
`getSplitCandidateAnchors` vs `splitNext` interaction (see session notes).
-/
import Lean.Meta.Tactic.Grind.Split

open Lean Meta

namespace NeuralTactic

-- ── Model scoring interface ───────────────────────────────────────────────────

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

-- ── Policy action ─────────────────────────────────────────────────────────────

def neuralSplitNext (stopAtFirstFailure := true) (compress := true) : Grind.Action :=
  fun goal kna kp => do
    -- Peek at candidate pool without consuming the modified goal state
    let (anchors, _) ← Grind.GoalM.run goal Grind.getSplitCandidateAnchors
    match anchors.candidates.toList with
    | [] => (Grind.Action.splitNext stopAtFirstFailure compress) goal kna kp
    | _ =>
      -- Pretty-print goal and all candidates (text in, text out — no serialization)
      let goalPP  ← Format.pretty <$> ppExpr (← goal.mvarId.getType)
      let candPPs ← anchors.candidates.mapM fun c =>
        Format.pretty <$> ppExpr c.e
      -- Score every candidate via the server (real model inference happens here)
      let _scores := candPPs.map (scoreCandidate goalPP)
      -- TODO: use scores to call splitCore on the argmax instead of splitNext.
      -- Blocked by the getSplitCandidateAnchors side-effect issue: calling it
      -- before splitNext corrupts the candidate state. Fix requires either
      -- saving/restoring GrindM state or accessing candidates without checkSplitStatus.
      (Grind.Action.splitNext stopAtFirstFailure compress) goal kna kp

end NeuralTactic
