import NeuralTactic.SplitPolicy
import NeuralTactic.Tactic

-- Sanity-check example: neural_grind should close this trivially.
example (a b : Bool) : (if a then b else false) = (a && b) := by neural_grind
