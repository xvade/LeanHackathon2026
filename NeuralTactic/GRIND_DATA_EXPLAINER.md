# Neural Grind Data Explainer

The following is an abbreviated real record from the dataset. It represents a proof of a theorem about function composition and preimages. Long internal `grindState` entries are shortened for readability.

```json
{
  "theoremName": "PFun.preimage_comp",
  "goalPP": "(f.comp g).preimage s = g.preimage (f.preimage s)",
  "solved": true,
  "splitDecisions": [
    {
      "step": 0,
      "goalFeatures": {
        "assertedCount": 12,
        "ematchRounds": 2,
        "numCandidates": 1,
        "splitDepth": 0,
        "splitTraceLen": 3
      },
      "pool": [
        {
          "anchor": "17081817004834584148",
          "exprText": "∃ a ∈ g w, w_1 ∈ f a",
          "generation": 4,
          "isRec": false,
          "numCases": 1,
          "source": "ematch",
          "tryPostpone": false,
          "variant": "default",
          "isGrindChoice": true
        }
      ],
      "chosenAnchor": "17081817004834584148",
      "statePP": [
        "α : Type u_1",
        "β : Type u_2",
        "γ : Type u_3",
        "f : β →. γ",
        "g : α →. β",
        "s : Set γ",
        "h : ¬(f.comp g).preimage s = g.preimage (f.preimage s)",
        "w : α",
        "h_1 : (w ∈ (f.comp g).preimage s) = (w ∉ g.preimage (f.preimage s))",
        "left : w ∈ (f.comp g).preimage s",
        "right : w ∉ g.preimage (f.preimage s)",
        "w_1 : γ",
        "left_1 : w_1 ∈ s",
        "right_1 : w_1 ∈ f.comp g w",
        "⊢ False"
      ],
      "grindState": [
        "¬(f.comp g).preimage s = g.preimage (f.preimage s)",
        "((f.comp g).preimage s = g.preimage (f.preimage s)) = False",
        "∃ x, (x ∈ (f.comp g).preimage s) = (x ∉ g.preimage (f.preimage s))",
        "..."
      ]
    }
  ]
}
```

---

## 2. Field-by-Field Breakdown

### Top-Level Metadata
*   **`theoremName`**: The unique identifier of the theorem (e.g., its Mathlib path).
*   **`goalPP`**: The "Pretty-Printed" version of the original goal we are trying to prove.
*   **`solved`**: A boolean indicating if native `grind` was able to finish this proof. We only train on `true` cases.
*   **`splitDecisions`**: An array of every time the tactic had to make a split choice.

### The Decision Object
Each decision in `splitDecisions` is a snapshot of the tactic state at a specific branching point.

#### A. Goal Features (The "Sensors")
These are numerical summaries of the current proof state:
*   **`assertedCount`**: How many total math facts the robot knows right now.
*   **`ematchRounds`**: How many times the robot has tried to "guess" new facts from existing theorems.
*   **`numCandidates`**: How many possible branches are available to choose from.
*   **`splitDepth`**: How many layers of nested "if/then" guesses we are currently inside.

#### B. The Candidate Pool (The "Menu")
This is the list of branches the robot is looking at.
*   **`exprText`**: The human-readable math term we are branching on (e.g., "Is $x$ in set $s$ or set $t$?").
*   **`numCases`**: How many sub-paths this branch creates. A value of `2` means an "If/Else" split.
*   **`variant`**: The *type* of branch. 
    *   `default`: Structural math (like an `if` or `match`).
    *   `imp`: A logical implication.
    *   `arg`: A branch created by two things being equal.
*   **`isGrindChoice`**: **CRITICAL.** This tells the model if the native, hand-written Lean logic would have picked this candidate.
*   **`tryPostpone`**: A safety flag. If `true`, the native engine thinks this branch is "distracting" and wants to wait.
*   **`anchor`**: A large unique number that identifies this specific math expression across different steps.

#### C. Environmental Context
*   **`statePP`**: The literal text of the "Infoview" in Lean (local variables and the current goal). This is what a human uses to prove the theorem.
*   **`grindState`**: The internal log of the robot's "E-graph"—every fact it has derived so far.

---

## 3. The Conceptual Story
To explain this project to others, use the **Maze Analogy**:

1.  **The Proof is a Maze**: Proving a theorem is like finding a path through a giant, branching maze to an exit called "The Proof."
2.  **The Expert (Native Grind)**: Lean's built-in `grind` tactic knows how to navigate the maze using a set of rules (heuristics). However, it can spend time exploring branches that do not directly contribute to the final proof.
3.  **The Data (Exploration vs. Winning Path)**: Our tool watches the expert navigate. We record every turn it makes. Crucially, we then **Prune** the data—we delete all the turns that led to dead ends and only keep the "Winning Spine."
4.  **The Model (The Shortcut Predictor)**: We train a tiny Neural Network to look at 32 "sensors" (our features) and predict only those winning turns.
## 4. Model Input/Output: How the Neural Network Thinks

To train the model, we present it with **Pool-Target Pairs**.

### The Input (The 32-Dimensional Vector)
Every time Lean considers a candidate branch, it "senses" the environment and the candidate itself, producing **32 precise numbers**:

| Index | Feature | Description |
| --- | --- | --- |
| **0-1** | `numCases`, `isRec` | Basic shape: How many subgoals? Is it recursive? |
| **2-10** | **Source (One-Hot)** | The origin of the branch: `ematch`, `ext`, `mbtc`, `beta`, `forallProp`, `existsProp`, `input`, `inj`, or `guard`. |
| **11** | `generation` | Age of the candidate (lower = older/original term). |
| **12-16** | **Proof Context** | Global counters: `splitDepth`, `assertedCount`, `ematchRounds`, `splitTraceLen`, `numCandidates`. |
| **17-23** | **Pool Relative** | How this candidate compares to others: Rank by cases, Rank by generation, Is it the minimum?, Fraction of pool that are "Input" types. |
| **24-26** | **State Density** | Hidden counters for internal E-graph events (Assertions, Eq-Classes, etc.). |
| **27** | `tryPostpone` | **Heuristic Flag**: Does Lean think this is a risky/late-stage branch? |
| **28-30** | **Variant (One-Hot)** | The category of the branch: `default`, `imp` (implication), or `arg` (congruence). |
| **31** | `isGrindChoice` | **Expert Bit**: Would the original human-written logic have picked this? |

### The Output (The Score)
The model outputs a single decimal number (a **Score**) for every candidate. 
*   **During Training**: We use **Cross-Entropy Loss**. We tell the model: "Here are 5 candidates. Candidate #3 was on the winning proof path. Adjust your weights so #3 gets the highest score and the others get low scores."
*   **During Inference**: The Lean tactic sends all candidates to the C++ server. The server scores them all, and the tactic picks the one with the **highest score**.

### The Training Objective: "Efficiency Weighting"
Not all proofs are equal. We multiply the model's "learning" by a weight:
*   **Formula**: $W = 1 / \sqrt{\text{total\_splits}}$
*   **Logic**: If a proof is solved in 2 steps, the model is told to pay **10x more attention** to those decisions than a proof that took 200 steps. This ensures the model learns the "Fast" way to prove things.

## 5. Scale and Size: Small Model, Big Data

One of the project's core strengths is its extreme efficiency.

### Model Parameters
The neural network is a 3-layer Multi-Layer Perceptron (MLP):
*   **Total Parameters**: **~74,500**
*   **Binary Size**: **291 KB**
*   **Inference Time**: **< 1ms** (Running in a native C++ server).

### Data Volume
The collection pipeline is designed to scale to a large theorem corpus:
*   **Target Lean Problems**: **~53,000** verified theorems.
*   **Source Diversity**: Mathlib, Competition Problems (Workbook), IMO-style problems (Numina).
*   **Total Decisions**: Estimated **~65,000** exploration branches, which are pruned down to **~50,000** "Winning Shortcut" steps for training.
