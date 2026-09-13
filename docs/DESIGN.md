# Design and implementation boundaries

## Portable core, Blender adapter, skill

The agent interprets the creative brief and invokes a deterministic JSON CLI. The skill loads only workflow instructions initially; detailed references are separate files. The core uses Python's standard library and makes no LLM calls. Its lexical keyword planner/ranker is intentionally explainable and is not advertised as learned semantic or visual scoring.

The host retains existing MCP connections. A Blender-only module implements scene evaluation and mutation. Importing it in ordinary Python is unsupported. Headless jobs avoid blocking the active Blender UI or conflicting with another MCP client. The existing MCP is used for live discovery and saving an unsaved project to a separate working copy, not replaced by a new server.

## Storage

The source repository contains only code, docs, schemas implicit in validated dataclasses/options, tests and skill instructions. The installed skill is a receipt-managed snapshot with a bundled runtime. An external library holds immutable downloads, extracted packages, prepared dependencies, local intake, manifests, a rebuildable SQLite index, backend source, jobs, previews and reports.

Records use stable provider/source identities; clip records additionally identify the actual source hash, action, slot and owning armature. File paths are relative to the library. Job specifications bind absolute target-file identity and library location so they must be prepared again after moving machines. Fingerprints detect changed inputs; they do not certify artist intent or legal ownership.

## Acquisition

Provider-specific adapters normalize known public responses. Search caches expire after 24 hours and label stale offline responses. Acquisitions never infer success from an HTML login page. Sketchfab authorization is confined to its API origin, and ephemeral signed download URLs are not catalog records.

Downloads and expanded bytes are accounted even on failed attempts. Immutable source receipts support integrity rechecks. ZIP validation applies Windows traversal, device-name and case-collision rules on all platforms. glTF dependencies must be inside the acquired package; valid parent-relative references are allowed only within that boundary.

The initial library budget is cumulative 500 MiB compressed and 2 GiB expanded. There is no silent reset or model-driven budget escalation. A reviewed local policy change may be needed after repeated sessions; preserve accounting evidence.

## Retargeting

Mwni commit `424f08bd7e675619adf539209a1e8816c242c386` is acquired separately with pinned Git blob hashes. The adapter registers only data classes in an isolated process and invokes its rest-aware matrix transfer directly. It does not call full add-on registration, install load handlers, execute generated driver expressions or modify global Blender preferences.

Rest-pose direction/scale checks precede transfer. Missing or constrained rigs require review. New unique actions preserve existing ones. Source FPS is converted to output time; frames are baked with quaternion sign continuity. This remains a limited adapter, not a universal automatic retargeter. Real uneven contact may need artist-authored IK/corrections beyond this version.

An in-place action can repeat and receive one calibrated root controller. Embedded horizontal root travel blocks double translation. Terrain following samples only the specified evaluated mesh, rejects missing/steep/discontinuous ground, and adjusts root height. It does not plant each foot. Numerical ankle/foot metrics remain heuristic unless sole offsets are calibrated.

## Camera authoring and preview artifacts

`camera-plan` authors an explicit animated camera from host-decided values and refuses to invent creative choices. Its contract lives in a portable module (`camera_plan.py`), so `job-prepare` rejects a malformed plan on ordinary Python before Blender starts; execution, keyframing and authoritative verification live in the Blender-only adapter. The screen-space solve inverts the perspective relation exactly, and the runtime then measures the result with real projection instead of trusting the algebra. Framing is judged on the *evaluated* camera, so a kept constraint that defeats the authored aim fails loudly rather than silently producing a different shot.

That solve is verified against Blender's own framing on each tested version: AUTO and HORIZONTAL fits use the declared sensor width (AUTO applies it to the larger image dimension), VERTICAL uses the declared sensor height, and pixel aspect is included. A wrong rule here would silently miss every screen target, so the Blender fixture asserts solved framing per fit mode. `BVHTree.FromObject` returns geometry in the object's local space, so occlusion rays are transformed into each object's space rather than copying large evaluated meshes into world space.

Previews exist to bound CPU cost, not to replace the project. A preview job records the settings it borrows, renders, restores them, and refuses to report success unless the restored snapshot matches the original, so a preview `.blend` cannot silently become a low-quality delivery master. The job runner's own bounded thread count is part of the execution environment and is reported rather than hidden.

## Execution and evidence

Jobs are versioned by input and implementation hash, write separate outputs, reject stale input, verify originals afterward, bound log size, and terminate on deadline or interruption. Result files separate technical execution from visual acceptance. Safe retries preserve prior failure evidence. A new host session can resume from durable receipts/reports without dumping a full conversation into the model.

Unit tests, real Blender fixtures, real retrieved-animation tests, and the live user scene are distinct gates. Neither a mock nor a compiler proves Blender compatibility. Neither a moving armature nor a small numerical foot drift proves natural motion. The final visual judgment remains explicit.
