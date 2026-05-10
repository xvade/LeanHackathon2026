# NeuralTactic

This directory contains the Lean 4 implementation of the neural split policy for `grind`.

- `NeuralTactic/SplitPolicy.lean`: Core logic for intercepting `grind` splits and querying the neural model.
- `native/`: C++ inference server implementation.
- `Tactic.lean`: Entry point for the `neural_grind` tactic.
