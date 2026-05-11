import Lake
open System Lake DSL

package NeuralTactic where
  version := v!"0.1.0"
  keywords := #["math"]
  leanOptions := #[
    ⟨`pp.unicode.fun, true⟩,
    ⟨`relaxedAutoImplicit, false⟩,
    ⟨`weak.linter.mathlibStandardSet, true⟩,
    ⟨`maxSynthPendingDepth, 3⟩,
  ]

require mathlib from git "https://github.com/leanprover-community/mathlib4" @ "v4.30.0-rc2"

@[default_target]
lean_lib NeuralTactic
