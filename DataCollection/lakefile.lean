import Lake
open Lake DSL

package «DataCollection» where

-- Mathlib gives access to all of its theorems for data collection.
-- Remove this require if you only need theorems from the Lean standard library.
require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "v4.30.0-rc2"

lean_lib «DataCollection» where

lean_exe «collect» where
  root := `Main
