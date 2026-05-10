# GrindExtraction

This directory contains the Lean 4 instrumentation used to extract training data from `grind`.

- `GrindExtraction/Tracer.lean`: Tactic that runs `grind` and logs every split decision to JSON.
- `Main.lean`: CLI wrapper for batch extraction.
