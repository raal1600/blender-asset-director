# Offline MotionBricks transition authoring — implementation record

Goal: selected native X → separately generated movement → selected native Y.
Keep both selected native intervals, their clocks and original Actions intact.
Generate through the pinned real C ABI in an isolated standalone Python worker.
Candidate creation must preserve the complete accepted timeline. Acceptance is
an explicit, stale-checked, atomic event. Review uses the same baked bytes as
candidate playback and accepted rendering. No Deep Research is launched here.

## Baseline and isolation (2026-10-06/07)

Inspected GitHub PR metadata on October 6: #31 and #30 remain open drafts.
Actual #31 head equals reference `cea64d0ebeaf09302adcf650b83b70d459b12bf9`;
#30 equals `c5b91b131db8bdc282ee39ee75988f00554f70fe`, based on
`feature/action-visual-turn-controls-20261004` at
`f2b39f2e001ebc5c0ddfa32dd08b4b9fd4c2ac07`. Both ancestry checks passed.
The existing feature working tree was clean and remains unchanged.

Implementation branch: `feature/motionbricks-authoring-20261006`, isolated
worktree `C:/Users/ramis/source/repos/blender-asset-director-motionbricks-authoring`.
Private new evidence: `C:/Users/ramis/Documents/AssetDirector-MotionBricks-Authoring-20261006`.
Existing production installations, original assets and historical evidence are
preserved. No push, merge, release or deployment is authorized by this work.
The task explicitly authorizes local model inference and bounded client/render
acceptance, superseding the generic no-inference development default.

Read AGENTS.md, CONTRIBUTING.md, CONSOLIDATION.md and the specified application,
tool and test files. The historical REPORT, delivery receipt and reproduction
recipes were inspected. Their motion/playback claims remain historical until
this implementation produces its own evidence. A source-only pass is never
substituted for a real runtime result.

## Stage gates

1. Baseline, pin/build verification, real sampling and early unseen-pair tests.
2. Versioned inputs, full dependencies, evaluated-motion analysis, contact/root
   intent preparation and actionable refusals.
3. Immutable real candidates, measured raw/corrected diversity, bounded bridge
   correction, hard validity before ranking, retained rejection diagnostics.
4. Client Generate → Inspect → Refine/Compare → Accept → Save/Reopen; history,
   restore, cancellation, stale completion, restart and downstream reconciliation.
5. Repeatable full-pipeline benchmarks, full regression and native client,
   provider, Blender, reopen, preview, render and temporal review acceptance.

The machine-readable gate is [motion-bricks-acceptance.json](motion-bricks-acceptance.json).
An unfulfilled mandatory requirement remains FAIL or specifically BLOCKED; it
cannot become unsupported just to close the task. Thresholds are fixed before
selecting candidates: seam position ≤0.001H, orientation ≤1°, root velocity
≤0.05H/s, angular velocity ≤5°/s, planted drift ≤0.01H, penetration ≤0.005H.
H is a reviewed rig reference. Planted metrics require nonempty observed contact
intervals; missing/airborne contact measurements are not zero-error passes.

## Current decisions and falsification

The original Save path immediately approves a generated checkpoint. Existing
`checkpointJob` supports other separate candidates, but a working request and
multiple immutable MotionBricks reviews need their own integration with that
transaction and existing recovery/serialization, not another application.

Pinned source `planner.cpp` skips random uniforms under argmax; changing its seed
is ineffective. Gumbel temperature is fixed at 1, with the RNG restarted per call.
Ten fresh Vulkan worker experiments confirm exact same-setting repetition and
exact output across argmax seeds. Stochastic seeds produce material raw pose
differences. Correction-surviving diversity is not yet established.

The baseline real reference and unseen idle→back pair pass continuity, original
Action preservation and fresh Blender reopen. Their contact and visual quality
are not established by that runner. These passes do not satisfy broad coverage.

Foundations repaired so far: label-based manual path defaults, the broken rig
preparation validator call, explicit loaded-DLL identity, central model timing
and context bounds, optional explicit sampling mode, retained separate input,
raw, retargeted and corrected motion artifacts, and stage timing records.
No new alternatives button is advertised before corrected diversity is verified.
