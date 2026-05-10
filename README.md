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
- **LeanDojo-v2**: Integrated for broader repository-scale diversity.

These datasets provide a vast collection of theorem statements that typically do not yet have accompanying proofs. From this pool, we have successfully verified and extracted proof traces for approximately **53,000 theorems**, with the following distribution of verified successes:
- **Mathlib**: ~38,500 theorems.
- **Numina & FineLean**: ~8,164 theorems.
- **Lean Workbook**: ~4,168 theorems.
- **Herald**: ~2,211 theorems.

This collection forms the core of our training data, representing a diverse "Winning Spine" for both `grind` and `aesop` across different domains.


**Verification and Filtering:**
For `grind`, we tested each theorem to see if the tactic could autonomously close the goal. Successful cases were added to a JSONL dataset for training. This verification process was facilitated by **AXLE by axiom.ai**. 

For `aesop`, we employed a similar verification protocol but introduced a refinement step: we first attempted to solve the goal using `simp`. If `simp` failed but `aesop` subsequently succeeded, the theorem was added to our collection. This filtering ensures that our dataset prioritizes non-trivial proofs where `aesop`'s search capabilities provide unique value beyond standard simplification, reflecting its internal strategy of attempting simplification before proceeding with more complex search heuristics.

### Aesop Trace Extraction

### Grind Trace Extraction

## Training

### Aesop Training

### Grind Training

## Project Note
Given the limited timeframe of the hackathon, this project serves as a focused investigation into the scaling potential of neural-guided proof search. Our primary interest was in projecting what the results would look like in the "actual end"—leveraging the full scale of the 53,000+ theorem dataset to move toward a highly efficient, zero-exploration automated prover.
