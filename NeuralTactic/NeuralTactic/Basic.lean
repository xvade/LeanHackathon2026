import NeuralTactic.SplitPolicy
import NeuralTactic.Tactic

-- The example we overfitted on.
-- Collected with DataCollection, trained with scripts/train.py.
-- The learned rule (prefer ite splits) makes neural_grind succeed here.
example (a b : Bool) : (if a then b else false) = (a && b) := by neural_grind
