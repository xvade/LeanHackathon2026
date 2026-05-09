import GrindExtraction.Tracer

-- Run: lake env lean Main.lean 2>/dev/null | grep '^{' > data.jsonl
-- Each example produces one JSONL record with the full candidate pool at each split.

-- if-then-else Boolean theorems (2 split decisions each)
example (a b : Bool) : (if a then b else false) = (a && b)  := by grind_collect
example (a b : Bool) : (if a then true else b)  = (a || b)  := by grind_collect
example (a b : Bool) : (if a then b else true)  = (!a || b) := by grind_collect
example (a b : Bool) : (if a then false else b) = (!a && b) := by grind_collect

-- Bool commutativity (1 split decision each)
example (p q : Bool) : (p || q) = (q || p) := by grind_collect
example (p q : Bool) : (p && q) = (q && p) := by grind_collect

-- if-then-else swap (1 split decision)
example (a b c : Bool) : (if a then b else c) = (if !a then c else b) := by grind_collect

def main : IO Unit := pure ()
