# Resume implementation and validation

The source candidate is implemented locally; offline tests pass. Publication is blocked by GitHub app repository selection, not by a failing unit test. The new repository was not authorized in the app installation at the last inspection. Do not use an unrelated repository as a workaround.

1. Re-read the GitHub installation's selected repositories after the user authorizes `blender-asset-director`. Verify the exact target and fetch its current `main` head/tree.
2. Preserve existing LICENSE and any intervening user changes. Publish normal source files directly to `main` as authorized, without force-pushing. Do not publish caches, asset data or private build logs.
3. Run/read the CI workflow. For push-triggered runs, inspect the Actions runs collection filtered by the actual pushed head SHA; do not use a helper that only returns PR-triggered runs.
4. Fix genuine Blender/provider failures and rerun. Provider response fixtures are not substitutes for live contracts. Inspect actual downloaded action names, slots and rig roles; do not loosen a safety gate merely to turn CI green.
5. Download/review the bounded evidence artifact. Replace NOT RUN in ACCEPTANCE with exact run/commit/version and measured results only when they exist.
6. Package the skill and run installer tests on Windows. Then perform the local read-only readiness inspection of `Desert Warrior.blend`. The current cloud session has not seen that file.
7. Do not run the artistic scene mutation until the user says **Run the Desert Warrior test**.

Known areas that need real validation first: Blender 5 action-slot behavior; Mwni direct-matrix adapter on the pinned version; actual Quaternius format/bone naming; ambientCG download-metadata shape; Poly Haven dependency manifests; mixed source/target scales; naturalness of repeated in-place locomotion and walk-to-idle transitions.

Maintain the current no-paid-generation, no-local-AI and CPU-preview limits. Never fake a visual inspection from a text-only model.
