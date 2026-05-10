# LeanHackathon 2026: Neural Automated Proof Search

This project focuses on enhancing Lean 4's automated tactics, specifically `grind` and `aesop`, through neural-guided proof search and efficiency-aware data collection.

## Extraction

### Data Extraction
Our data collection process followed two primary strategies to capture a diverse range of mathematical contexts and theorem styles.

**Mathlib Data Collection:**
We collected data from Mathlib by systematically extracting theorems and their environmental contexts. This was achieved by parsing import statements, namespaces, and open statements to reconstruct the precise mathematical state. We utilized a custom tactic to execute `grind` and `aesop` across these theorems, extracting the goal states and proof traces to build a comprehensive map of Mathlib's successful automated proofs.

**External Dataset Integration:**
The second strategy involved leveraging several large-scale Lean datasets, collectively providing a vast search space for theorem automation:
- **NuminaMath Lean**: 104,155 competition-style theorems.
- **Lean Workbook**: 57,231 formal statements.
- **Herald**: 580,000 NL-FL statement pairs.
- **FineLeanCorpus**: 509,358 formalization entries.
- **LeanDojo-v2**: 120,000 statements

These datasets provide a vast collection of theorem statements that typically do not yet have accompanying proofs. From this pool, we have successfully verified and extracted proof traces for approximately **53,000 theorems** that work with either grind or aesop.

This collection forms the core of our training data, representing a diverse "Winning Spine" for both `grind` and `aesop` across different domains.


**Verification and Filtering:**
For `grind`, we tested each theorem to see if the tactic could autonomously close the goal. Successful cases were added to a JSONL dataset for training. This verification process was facilitated by **AXLE by axiom.ai**. 

For `aesop`, we employed a similar verification protocol but introduced a refinement step: we first attempted to solve the goal using `simp`. If `simp` failed but `aesop` subsequently succeeded, the theorem was added to our collection. This filtering ensures that our dataset prioritizes non-trivial proofs where `aesop`'s search capabilities provide unique value beyond standard simplification, reflecting its internal strategy of attempting simplification before proceeding with more complex search heuristics.

### Aesop Trace Extraction


### Grind Trace Extraction
We instrumented the `grind` tactic to capture the internal state and decision-making process at every "split" (branching point) during proof search. This instrumentation allows us to record the precisely timed "snapshots" of the prover's state.

**The Trace Data:**
For every successful proof, we extract a JSON trace containing:
- **Goal Features**: Numerical summaries such as `assertedCount` (total known facts), `ematchRounds`, and `splitDepth`.
- **Candidate Pool**: The full set of available branching options (e.g., case splits on an `if-then-else` or an implication), including their origins (`ematch`, `ext`, `input`, etc.).
- **Environmental Context**: A "Pretty-Printed" version of the local context and the internal state of the E-graph (the robot's "brain").
- **Winning Spine**: We prune these traces to retain only the "Winning Spine"—the sequence of successful decisions that directly led to the proof, discarding any exploratory dead ends.

## Training

### Aesop Training


### Grind Training
To leverage the extracted trace data, we trained a lightweight neural model designed to predict the optimal next step in a `grind` proof search.

**Model Architecture:**
- **Type**: A 3-layer Multi-Layer Perceptron (MLP).
- **Size**: ~74,500 parameters
- **Input**: A 32-dimensional feature vector encoding the goal state, the specific candidate branch, and its relationship to the rest of the candidate pool.
- **Inference**: Optimized for speed, the model runs in a native C++ server with an inference time of **< 1ms**, enabling its use directly within the Lean tactic loop.

**Training Strategy:**
- **Objective**: The model is trained using Cross-Entropy Loss to maximize the score of the "Winning Spine" candidate within its original pool of alternatives.
- **Efficiency Weighting**: We apply a weighting formula ($W = 1 / \sqrt{\text{total\_splits}}$) to the training loss. This incentivizes the model to prioritize decisions from shorter, more efficient proofs, effectively learning "shortcuts" over the native heuristic's often exhaustive search.
- **Evaluation**: We maintain a stable benchmark of 75 problems (balanced across Mathlib, Workbook, and Numina) that are strictly excluded from the training set to measure the model's generalization and split-reduction capabilities.


## Project Note
This project serves as a focused investigation into the scaling potential of neural-guided proof search. Our primary interest was in projecting what the results would look like in the "actual end"—leveraging the full scale of the 53,000+ theorem dataset to move toward a highly efficient, zero-exploration automated prover.
