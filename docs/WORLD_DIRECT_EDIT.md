# World direct editing: bounded Save foundation

This is an incremental implementation of the layered-editor plan. The native
worker and authenticated Save boundary exist; viewer picking/gizmos, browser
draft/undo controls, explicit preparation of older scenes and full browser E2E
integration are still outstanding. This is not a completed interactive editor.

`world-transform` is an isolated mutation on an exact saved `.blend` input. Its
versioned options contain 1–64 distinct observed instance IDs with the expected
and requested row-major Blender-coordinate 4x4 control matrices. It refuses
nonfinite/unbounded values, shear, reflected or nonuniform scale, stale matrices,
ambiguous/missing identities, foreign descendants, linked/shared objects and
constrained/driven ownership. It validates every target before moving any of them.
Only the unanimated instance controls change; native rig channels stay intact.

The worker saves a separate `result.blend`, reopens it with scripts disabled,
checks the requested matrices and retained local hierarchy/animation/unrelated
state, then emits the actual scene audit. Failed results are never published as
current checkpoints. `world-placement-audit` is a read-only companion operation.

`POST /api/workbench/world-save` uses the existing authentication and serialized
command surface. It binds project revision, scene, exact checkpoint ID/hash,
versioned matrix batch and a request UUID. The same request returns its retained
receipt; reusing that UUID for another request refuses. Project source-use and
byte checks plus the shared writer lease gate execution. Manual tasks cannot race
with Save. Sources and baseline are rechecked before publishing the verified
output as a new current **unapproved** checkpoint. Saving is not World completion,
render approval or a replacement for source rights. Previous files are retained.

## Regression coverage

Portable contract tests and launcher synthetic persistence tests cover schema,
bounds, source-use refusal, writer exclusion, stale/foreign identities, exact
result binding, failure retention and idempotency. The generated real Blender
fixture exercises two keyed rigs and a multi-root static asset through isolated
job preparation, execution, Save/reopen and frame evaluation:

```text
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/world_layers_fixture.py -- <new-world-fixture>
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/world_transform_fixture.py -- <world-fixture>/placed.blend <new-transform-output>
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/world_append_fixture.py -- <new-append-output>
```

Collection append differs from glTF import: linking a collection leaves transforms
unevaluated until the view layer updates. World preparation now evaluates that
baseline before checking identity-parent preservation. The preservation guard is
not weakened. The append fixture uses the same generated animated collection as
the installed-studio journey and tests two independent imports plus original
byte preservation. The journey also reports failed retained jobs immediately
instead of hiding the worker error behind an eventual generic add timeout.

These tests run through the existing embedded-viewer suite; workflow names and
historical evidence are unchanged. Synthetic confirmations are not human review.
Native desktop gestures, complete interactive browser Save/recovery, private
licensed inputs and packaged/live deployment remain separate acceptance gates.
