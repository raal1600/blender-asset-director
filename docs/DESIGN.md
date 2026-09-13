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

`camera-plan` authors an explicit animated camera from host-decided values and refuses to invent creative choices. Its contract lives in a portable module (`camera_plan.py`), so `job-prepare` rejects a malformed plan on ordinary Python before Blender starts; execution, keyframing and authoritative verification live in the Blender-only adapter. The screen-space solve is closed-form and roll-free: it builds the camera frame directly so the aim direction lands on the requested screen position with the local up axis level, then applies only an explicitly requested roll (un-rolling the screen offset first, so the two intents cannot drag each other). Composing a yaw about the camera's local up axis, as v0.3.0 did, injected roll of roughly `yaw * sin(pitch)` - small, but not a reviewed value. Verification targets may name an observed subject or an explicit world point. The runtime then measures the result with real projection instead of trusting the algebra: framing and roll are judged on the *evaluated* camera, so a kept constraint that defeats the authored aim fails loudly rather than silently producing a different shot.

That solve is verified against Blender's own framing on each tested version: AUTO and HORIZONTAL fits use the declared sensor width (AUTO applies it to the larger image dimension), VERTICAL uses the declared sensor height, and pixel aspect is included. A wrong rule here would silently miss every screen target, so the Blender fixture asserts solved framing per fit mode. `BVHTree.FromObject` returns geometry in the object's local space, so occlusion rays are transformed into each object's space rather than copying large evaluated meshes into world space.

Previews exist to bound CPU cost, not to replace the project. A preview job records the settings it borrows, renders, restores them, and refuses to report success unless the restored snapshot matches the original, so a preview `.blend` cannot silently become a low-quality delivery master. The job runner's own bounded thread count is part of the execution environment and is reported rather than hidden.

## Lighting and look development

Look operations follow the same split as camera authoring: portable contracts (`look_contract.py`) validate explicit values on ordinary Python so `job-prepare` rejects a malformed request before Blender starts, while `scene_ops` applies and measures. Nothing in the surface accepts code, shader graphs or preset keywords - a request is a list of named lights with named properties, or bounded world and colour-management values.

Anything version-dependent is discovered at execution time rather than assumed: view transforms, looks, display devices and light shapes are validated by applying them and reading the result back, numeric values are checked against Blender's own RNA limits, and fields such as white balance or per-light exposure are refused when the running Blender does not expose them. A rejected value surfaces Blender's own message instead of being clamped or silently ignored.

World editing is deliberately narrow. A world must present exactly one Background node whose target input is unlinked (or be a plain non-node world, which Blender 5.x no longer allows). Linked inputs and ambiguous graphs are refused with explicit reasons, because the alternative - overwriting a link or simplifying a user graph - would destroy authored work that this executor cannot see. The same principle governs lights: adapting a light changes only the properties named, and the operation fails if any other light or property moved.

Every mutation embeds a full look snapshot before and after, so a reviewer can diff lights, world state, colour management, engine and the material set without trusting the summary. Materials stay out of scope: look operations assert the material set is unchanged and fail otherwise.

## Execution and evidence

Jobs are versioned by input and implementation hash, write separate outputs, reject stale input, verify originals afterward, bound log size, and terminate on deadline or interruption. Result files separate technical execution from visual acceptance. Safe retries preserve prior failure evidence. A new host session can resume from durable receipts/reports without dumping a full conversation into the model.

Unit tests, real Blender fixtures, real retrieved-animation tests, and the live user scene are distinct gates. Neither a mock nor a compiler proves Blender compatibility. Neither a moving armature nor a small numerical foot drift proves natural motion. The final visual judgment remains explicit.
