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

-- Compile native/model.cpp into a static library.
-- This provides the optional C++ exp08 scorer used by GRIND_NATIVE_MODEL=exp08.
target neuralModelO pkg : FilePath := do
  let oFile := pkg.buildDir / "native" / "model.o"
  let srcJob ← inputTextFile <| pkg.dir / "native" / "model.cpp"
  let leanIncDir ← getLeanIncludeDir
  buildO oFile srcJob #["-I", leanIncDir.toString, "-O2", "-std=c++17"] #[] "c++" getLeanTrace

extern_lib leanNeuralModel pkg := do
  let oJob ← neuralModelO.fetch
  buildStaticLib (pkg.staticLibDir / nameToStaticLib "leanNeuralModel") #[oJob]

@[default_target]
lean_lib NeuralTactic where
  -- libclient:       legacy Unix socket client kept for old experiments
  moreLinkArgs := #["-Lnative", "-lclient"]
