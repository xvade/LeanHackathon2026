import NeuralTactic

set_option maxHeartbeats 200000

example (p q : Prop) [Decidable p] [Decidable q] : (if p then q else q) = q := by
  neural_grind

example (p q r : Prop) [Decidable p] [Decidable q] [Decidable r] :
    (if p then q ∧ r else q ∧ r) → q := by
  neural_grind
