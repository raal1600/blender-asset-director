# Transition validation and troubleshooting

The accepted provider is deterministic native interpolation. The optional pinned
MotionBricks provider produces explicitly unaccepted G1 candidates: real CPU and
Vulkan inference works, but the measured raw seam quality fails the preset
acceptance thresholds. See [provider evidence](MOTION_BRICKS_CAPABILITY_AUDIT.md),
[data contract](TRANSITION_DATA_CONTRACT.md), [native scope](NATIVE_TRANSITION_CONTRACT.md)
and [authored contacts](AUTHORED_CONTACTS.md).

## Reproduce acceptance

Use Python 3.11+, Node 20, the repository's supported Blender versions, and a new
absolute output directory outside the checkout. The ordinary checks remain:

```sh
python tools/run_checks.py --offline
cd launcher
node --test
```

Run the real Blender subsystem, including continuity, authored contacts and
fresh-process GLB parity (replace paths and version for the actual executable):

```sh
python tools/ci/run_blender_suite.py --suite motion --blender /path/to/blender --version 5.2.1 --evidence /new/evidence/motion
```

The full local transition runner records sampled process-tree RAM, device-wide
VRAM, repeated evaluated poses, reopened .blend files, actual client GLB
interpolation and rendered frame sequences. FFmpeg is optional for the numerical
run and required for the complete installed browser journey:

```sh
python tools/run_transition_acceptance.py --blender /path/to/blender --output /new/evidence/transitions --ffmpeg /path/to/ffmpeg --repeat 2 --device-memory-budget-mib 9216
```

Add `--playwright /absolute/path/to/playwright/index.mjs`, `--chrome /path/to/chrome`,
`--ffprobe /path/to/ffprobe` and `--codex /path/to/codex` for the actual installed
client journey and queued/running cancellation. Playwright 1.55.0 and its FFmpeg
recording helper are the tested pin. Use the existing installation conventions;
`tools/create_workbench_studio.py` makes an independent studio with its own
library and copied runtime. The runner starts its normal launcher entry point.
It does not replace the user's production installation.

`ACCEPTANCE.json` records the source commit, dirty flag, source digest, each
executed check and explicit unverified scopes. `SCOPED_PASS` is deliberately not
full acceptance. A missing GPU, native desktop or provider run never becomes a
passing hardware/provider claim. Resource values are sampled maxima; GPU usage
is device-wide, including the display and other processes. Observed descendant
release is monitoring evidence, not an OS process-containment guarantee. Real
job cancellation separately asserts that its exact Blender PID has exited.

Run optional real-provider proofs with the explicit versioned setup/configuration
in the provider audit. No model is bundled in Git. CPU and Vulkan are distinct
configurations; AUTO or CPU tests do not prove Vulkan hardware acceptance.

## Expected artifacts

- `continuity/` and `contacts/`: generated CC0 source/result .blend files, native
  Action hashes, fixed thresholds, same-timestamp boundary derivatives and stance
  samples. An empty contact mask is refused.
- `fresh-*/`: generation-bound saved-file hash, fresh Blender evaluation, actual
  application `accepted.glb`, `GLB-RESULTS.json`, rendered boundary frames and,
  with FFmpeg, a playback movie.
- `repeat-*` and `contacts-repeat/`: independently generated samples compared
  numerically, rather than comparing nondeterministic .blend serialization bytes.
- `client/`: UI recording/screenshots, request and console failures, source and
  checkpoint identities, backend restart and render/movie playback checks.
- `cancellation/`: visible queued/running cancellation, native receipts, absence
  of a newly accepted checkpoint, editable draft and exact worker exit checks.
- Per-command logs/resource JSON, including failure evidence. Existing output
  directories are refused to prevent accidental reuse of old passing reports.

The native Windows EXE has a separate repository gate in
`tools/native_desktop_fixture.py` and `tools/package_workbench_candidate.py`.
A successful browser run does not waive that gate. Windows must permit foreground
access before its UI automation sends input. The local session denied it; no
foreground safety guard was bypassed. Hosted exact-commit evidence is recorded
separately from local checks.

## Troubleshooting

A stale preview should resolve after a new accepted Save: checkpoint identity
includes source bindings, native defaults, timing, generated channel hashes and
worker implementation. Do not reuse an old GLB or edit acceptance receipts.
Quarter-frame export preserves evaluated subframes and restores all temporary
scene settings even if export fails. Unsupported/clamped time remapping fails
explicitly rather than changing the saved scene.

For a refused rig, inspect the displayed blocker. The native path needs native
transform channels on the same verified performer; constraints/drivers require
a separately reviewed bake. Cross-rig names are not proof of compatible rest
geometry. Retargeting remains the application's separate reviewed operation.

For foot cleanup, author the explicit chain/rest mapping and nonempty planted
intervals. Invalid, moving, unreachable or incompatible planted boundaries are
refused. Unannotated clips may still interpolate, but their contact quality is
clearly unverified. A contact diagnostic is not universal gait approval.

Cancel Save preserves the current accepted checkpoint and editable draft.
A cancellation arriving after accepted publication is reported as too late;
it cannot retroactively relabel an accepted artifact. Interrupted jobs retain
an explicit non-success receipt and use the existing recovery/retry flow.
