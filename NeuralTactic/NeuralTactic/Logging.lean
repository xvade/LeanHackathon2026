import Lean
import Lean.Elab.Tactic.Grind

open Lean Meta Elab Tactic

namespace NeuralTactic

/-- Append a JSONL line to GRIND_LOG if the env var is set. -/
def writeGrindLog (line : String) : IO Unit := do
  let env ← IO.getEnv "GRIND_LOG"
  match env with
  | some path => IO.FS.withFile path IO.FS.Mode.append fun h => h.putStrLn line
  | none => pure ()

-- Note: The `neural_grind_collect` tactic is intentionally left out to avoid
-- introducing a hard dependency on the GrindExtraction package at build time.
-- In practice, this module provides `writeGrindLog` for other tactics to call.

end NeuralTactic
