/-
`NeuralTactic.SplitPolicy` — neural split-candidate ranker.

At each split decision `neuralSplitNext`:
  1. Gets the candidate pool via `getSplitCandidateAnchors` (keeping the modified goal state).
  2. Sends goalFeatures + candidates to a persistent model subprocess.
  3. Uses the model's chosen anchor to call `splitCore` directly.
  4. Falls back to grind's native split selection if the model is unavailable
     or below the configured margin threshold.

Environment variables:
  GRIND_MODEL — path to the PyTorch checkpoint (.pt)
  GRIND_SERVE — path to the Python server or native inference executable
  GRIND_SERVE_NATIVE — set to 1 when GRIND_SERVE is a native executable
  GRIND_NO_MODEL — set to 1 to skip model inference and use only the fallback
  GRIND_MARGIN_MILLI — require model top-1/top-2 logit margin in milli-logits
  GRIND_INCLUDE_EXPR_TEXT — set to 1 to send pretty-printed candidate terms
  GRIND_DECISION_LOG — optional JSONL path for split-policy decision diagnostics
-/
import Lean.Elab.Tactic.Basic
import Lean.Meta.Tactic.Grind.Main
import Lean.Meta.Tactic.Grind.Finish
import Lean.Meta.Tactic.Grind.EMatchAction
import Lean.Meta.Tactic.Grind.Intro

open Lean Meta Elab Tactic Grind

namespace NeuralTactic

-- ---------------------------------------------------------------------------
-- JSON helpers
-- ---------------------------------------------------------------------------

private def jsonStr (s : String) : String :=
  "\"" ++ (s.replace "\\" "\\\\" |>.replace "\"" "\\\"" |>.replace "\n" "\\n") ++ "\""

private def variantStr (si : SplitInfo) : String :=
  match si with
  | .default _ _ => "default"
  | .imp _ _ _   => "imp"
  | .arg _ _ _ _ _ => "arg"

private def sourceTagStr (si : SplitInfo) : String :=
  match si.source with
  | .ematch _     => "ematch"  | .ext _        => "ext"
  | .mbtc _ _ _   => "mbtc"    | .beta _       => "beta"
  | .forallProp _ => "forallProp" | .existsProp _ => "existsProp"
  | .input        => "input"   | .inj _        => "inj"
  | .guard _      => "guard"

private def envFlag (name : String) : IO Bool := do
  match ← IO.getEnv name with
  | none => return false
  | some v =>
    return !(v == "" || v == "0" || v == "false" || v == "False" || v == "FALSE")

private def modelDisabled : IO Bool := do
  if ← envFlag "GRIND_NO_MODEL" then
    return true
  else
    envFlag "NEURAL_GRIND_NO_MODEL"

private def includeExprText : IO Bool :=
  envFlag "GRIND_INCLUDE_EXPR_TEXT"

private def marginThresholdMilli : IO Nat := do
  match ← IO.getEnv "GRIND_MARGIN_MILLI" with
  | some s =>
    match s.trimAscii.toString.toNat? with
    | some n => return n
    | none   => return 0
  | none => return 0

-- ---------------------------------------------------------------------------
-- Persistent model server subprocess
-- ---------------------------------------------------------------------------

private structure ModelServer where
  stdinH  : IO.FS.Handle
  stdoutH : IO.FS.Handle

private structure ModelChoice where
  anchor : UInt64
  marginMilli : Option Nat

private initialize neuralServerRef  : IO.Ref (Option ModelServer) ← IO.mkRef none
private initialize neuralServerPath : IO.Ref String               ← IO.mkRef ""

private def getOrStartServer : IO (Option ModelServer) := do
  if ← modelDisabled then
    return none
  let some modelPath ← IO.getEnv "GRIND_MODEL" | return none
  let some servePath ← IO.getEnv "GRIND_SERVE" | return none
  let pythonBin ← do
    match ← IO.getEnv "GRIND_PYTHON" with
    | some p => pure p
    | none   => pure "python3"
  let nativeServe ← envFlag "GRIND_SERVE_NATIVE"
  let currPath ← neuralServerPath.get
  if currPath == modelPath then
    if let some h := ← neuralServerRef.get then return some h
  try
    let cmd := if nativeServe then servePath else pythonBin
    let args := if nativeServe then #[ "--model", modelPath ] else #[servePath, "--model", modelPath]
    let child ← IO.Process.spawn {
      cmd    := cmd,
      args   := args,
      stdin  := .piped,
      stdout := .piped,
      stderr := .inherit,
    }
    let srv : ModelServer := { stdinH := child.stdin, stdoutH := child.stdout }
    neuralServerRef.set (some srv)
    neuralServerPath.set modelPath
    return some srv
  catch _ => return none

private def parseServerChoice (line : String) : ModelChoice :=
  let fields := (line.trimAscii.toString.splitOn " ").filter (fun f => f != "")
  match fields with
  | anchorStr :: rest =>
    let anchor := anchorStr.toNat?.map UInt64.ofNat |>.getD 0
    let marginMilli :=
      match rest with
      | marginStr :: _ => marginStr.toNat?
      | [] => none
    { anchor := anchor, marginMilli := marginMilli }
  | [] => { anchor := 0, marginMilli := none }

private def queryServer (gfJson candsJson : String) : IO ModelChoice := do
  let some srv ← getOrStartServer | return { anchor := 0, marginMilli := none }
  try
    let query := "{\"goalFeatures\":" ++ gfJson ++ ",\"candidates\":" ++ candsJson ++ ",\"statePP\":[],\"grindState\":[]}\n"
    srv.stdinH.putStr query
    srv.stdinH.flush
    let line ← srv.stdoutH.getLine
    return parseServerChoice line
  catch _ =>
    neuralServerRef.set none
    return { anchor := 0, marginMilli := none }

private def modelChoiceAllowed (choice : ModelChoice) (threshold : Nat) : Bool :=
  choice.anchor != 0 &&
    if threshold == 0 then
      true
    else
      match choice.marginMilli with
      | some margin => margin >= threshold
      | none => false

private def decisionLogLine
    (action : String)
    (reason : String)
    (numCandidates : Nat)
    (threshold : Nat)
    (choice : ModelChoice) : String :=
  "{\"action\":" ++ jsonStr action ++
    ",\"reason\":" ++ jsonStr reason ++
    ",\"numCandidates\":" ++ toString numCandidates ++
    ",\"thresholdMilli\":" ++ toString threshold ++
    ",\"anchor\":" ++ toString choice.anchor ++
    ",\"marginMilli\":" ++
      (match choice.marginMilli with
       | some m => toString m
       | none => "null") ++
    "}"

private def appendDecisionLog
    (action : String)
    (reason : String)
    (numCandidates : Nat)
    (threshold : Nat)
    (choice : ModelChoice) : IO Unit := do
  let some path ← IO.getEnv "GRIND_DECISION_LOG" | return
  if path.trimAscii.toString == "" then
    return
  try
    IO.FS.withFile path .append fun h => do
      h.putStrLn (decisionLogLine action reason numCandidates threshold choice)
  catch _ =>
    return

-- ---------------------------------------------------------------------------
-- neuralSplitNext
-- ---------------------------------------------------------------------------

def neuralSplitNext (stopAtFirstFailure := true) (compress := true) : Action :=
  fun goal kna kp => do
    if ← modelDisabled then
      appendDecisionLog "fallback" "model_disabled" 0 0 { anchor := 0, marginMilli := none }
      (Action.splitNext stopAtFirstFailure compress) goal kna kp
    else
      let (anchors, goal') ← GoalM.run goal getSplitCandidateAnchors
      if anchors.candidates.isEmpty then
        appendDecisionLog "fallback" "no_candidates" 0 0 { anchor := 0, marginMilli := none }
        kna goal'
      else
        -- goalFeatures JSON (one line, avoids multi-line `++` parse issues)
        let gfJson := "{\"splitDepth\":" ++ toString goal'.split.num ++ ",\"assertedCount\":" ++ toString goal'.facts.size ++ ",\"ematchRounds\":" ++ toString goal'.ematch.num ++ ",\"splitTraceLen\":" ++ toString goal'.split.trace.length ++ ",\"numCandidates\":" ++ toString anchors.candidates.size ++ "}"

        let (grindChoice, _) ← GoalM.run goal' do
          let mut best : Option (SplitCandidateWithAnchor × Nat × Bool × Bool) := none
          for c in anchors.candidates do
            let status ← checkSplitStatus c.c
            if let .ready numCases isRec tryPostpone := status then
              if (← cheapCasesOnly) && numCases > 1 then
                continue
              match best with
              | none =>
                best := some (c, numCases, isRec, tryPostpone)
              | some (c', numCases', isRec', tryPostpone') =>
                let isBetter ← do
                  if tryPostpone' && !tryPostpone then pure true
                  else if tryPostpone && !tryPostpone' then pure false
                  else if numCases == 1 && !isRec && numCases' > 1 then pure true
                  else if (← getGeneration c.e) < (← getGeneration c'.e) then pure true
                  else if numCases < numCases' then pure true
                  else pure false
                if isBetter then
                  best := some (c, numCases, isRec, tryPostpone)
          return best.map (·.1.anchor)

        -- candidates JSON — build each entry as a local let, then return
        let sendExprText ← includeExprText
        let candJsons ← anchors.candidates.mapM fun c => do
          let pp ← if sendExprText then Format.pretty <$> ppExpr c.e else pure ""
          let gen := goal'.getGeneration c.e
          let (status, _) ← GoalM.run goal' (checkSplitStatus c.c)
          let tryPostpone := match status with
            | .ready _ _ tp => tp
            | _ => false
          let isGrindChoice := (grindChoice == some c.anchor)
          let j := "{\"anchor\":" ++ toString c.anchor ++
            ",\"exprText\":" ++ jsonStr pp ++
            ",\"numCases\":" ++ toString c.numCases ++
            ",\"isRec\":" ++ (if c.isRec then "true" else "false") ++
            ",\"source\":" ++ jsonStr (sourceTagStr c.c) ++
            ",\"generation\":" ++ toString gen ++
            ",\"tryPostpone\":" ++ (if tryPostpone then "true" else "false") ++
            ",\"variant\":" ++ jsonStr (variantStr c.c) ++
            ",\"isGrindChoice\":" ++ (if isGrindChoice then "true" else "false") ++ "}"
          pure j
        let candsArr := "[" ++ ",".intercalate candJsons.toList ++ "]"

        -- Query model
        let modelChoice ← queryServer gfJson candsArr
        let marginThreshold ← marginThresholdMilli
        let allowed := modelChoiceAllowed modelChoice marginThreshold
        let modelCand? :=
          if allowed then
            anchors.candidates.find? (·.anchor == modelChoice.anchor)
          else none

        -- Pick the model candidate, or fall back to native grind selection.
        match modelCand? with
        | none =>
          let reason :=
            if modelChoice.anchor == 0 then
              "no_model_choice"
            else if !allowed then
              "below_margin"
            else
              "anchor_not_found"
          appendDecisionLog "fallback" reason anchors.candidates.size marginThreshold modelChoice
          (Action.splitNext stopAtFirstFailure compress) goal' kna kp
        | some bestCand =>
          appendDecisionLog "model" "override" anchors.candidates.size marginThreshold modelChoice
          let gen    := goal'.getGeneration bestCand.e
          let genNew := if bestCand.numCases > 1 || bestCand.isRec then gen + 1 else gen
          let step :=
            Action.splitCore bestCand.c bestCand.numCases bestCand.isRec
                             stopAtFirstFailure compress >>
            Action.intros genNew >>
            Action.assertAll
          step goal' kna kp

end NeuralTactic
