/-
`NeuralTactic.LoggingV2` — JSONL logging for `neural_collect`.

Writes one JSON record per proof to the file at `$GRIND_LOG`:

  { "proofId": <uint64>,
    "outcome": "success"|"failure",
    "steps": [
      { "step": <n>,
        "goalFeatures": { "splitDepth": <n>, "assertedCount": <n>,
                          "ematchRounds": <n>, "splitTraceLen": <n>,
                          "numCandidates": <n> },
        "candidates":   [{ "anchor": <uint64>, "exprText": <str>,
                           "numCases": <n>, "isRec": <bool>,
                           "source": <str> }, ...],
        "chosenAnchor": <uint64>
      }, …
    ]
  }
-/
import Lean

namespace NeuralTactic

-- ---------------------------------------------------------------------------
-- JSON helpers
-- ---------------------------------------------------------------------------

def jsonEscapeStr (s : String) : String :=
  s.foldl (fun acc c =>
    match c with
    | '"'  => acc ++ "\\\""
    | '\\' => acc ++ "\\\\"
    | '\n' => acc ++ "\\n"
    | '\r' => acc ++ "\\r"
    | '\t' => acc ++ "\\t"
    | c    => acc.push c
  ) ""

def jsonStr (s : String) : String := "\"" ++ jsonEscapeStr s ++ "\""

-- ---------------------------------------------------------------------------
-- Per-proof mutable log (global IO.Ref — process-local, sequential proofs)
-- ---------------------------------------------------------------------------

initialize proofStepsV2 : IO.Ref (Array String) ← IO.mkRef #[]
initialize stepIdxV2    : IO.Ref Nat            ← IO.mkRef 0

/-- Reset the step log at the start of each proof. -/
def initProofLogV2 : IO Unit := do
  proofStepsV2.set #[]
  stepIdxV2.set 0

/-- Allocate and return the next step index. -/
def nextStepIdxV2 : IO Nat := do
  let idx ← stepIdxV2.get
  stepIdxV2.set (idx + 1)
  return idx

/-- Append one formatted step JSON object to the proof log. -/
def appendStepV2 (stepJson : String) : IO Unit :=
  proofStepsV2.modify (·.push stepJson)

/--
Write the accumulated steps as one JSONL record to `$GRIND_LOG`.
No-ops when `GRIND_LOG` is unset or when no steps were recorded.
-/
def flushProofLogV2 (proofId : UInt64) (outcome : String) : IO Unit := do
  let some logPath ← IO.getEnv "GRIND_LOG" | return
  let steps ← proofStepsV2.get
  if steps.isEmpty then return
  let stepsArr := "[" ++ ",".intercalate steps.toList ++ "]"
  let record :=
    "{\"proofId\":"  ++ toString proofId  ++
    ",\"outcome\":"  ++ jsonStr outcome    ++
    ",\"steps\":"    ++ stepsArr          ++ "}\n"
  let h ← IO.FS.Handle.mk logPath .append
  h.putStr record

end NeuralTactic
