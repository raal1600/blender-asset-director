# Candidate validation on your Windows studio

## Keep the current studio intact

Extract the complete verified candidate folder, then run `Setup.cmd` or supply
explicit paths to `Setup.ps1`. Setup can read executable paths from an existing
studio you select. It does not copy private assets, change credentials, update
Blender preferences, install a new MCP provider, or overwrite that studio. Choose
a **new** directory. FFmpeg and FFprobe are required for this film MVP; neither
is downloaded during setup. The candidate uses a separate local catalog and an
OS-assigned loopback port. The desktop executable is unsigned.

`CANDIDATE.json` lists the exact source/host commit and all payload hashes.
Verification rejects mixed source/host builds, missing, tampered, escaped or
unlisted files. This establishes package integrity, not an independent publisher
signature. Keep the archive checksum and CI run link from the delivery handoff.

## A modest real acceptance production

Use inputs you have rights to use. Intake **copies** and retained source-use
records into the new catalog using the existing harness intake/provider policies;
never bypass native licensing checks by editing a record. Keep package textures
and other dependencies together. Do not repoint the candidate at an existing
production catalog just to avoid this step.

Create a production and three scenes. In World, select a real acquired model or
prepared Blender collection. Inspect its member/collection and import it. Verify
that it becomes a candidate with observed object identities, not merely a selected
source. Keep building; open its dedicated Blender task and change placement.
Use the top-bar **Save checkpoint & return**, collect the saved candidate, inspect
it and keep it. Confirm that the original package and prior checkpoint are intact.

In Action, select a performer and inspect a real motion take through Blender or
the existing Performance specialist. A retarget needs source/target inspection
and the exact transfer-plan review. Do not infer suitability from a filename.
Verify actual temporal playback, timing, rig deformation and contacts. Save a
new checkpoint, collect and review it in the same scene. A static scene may use
an explicitly reviewed static performance; it must not claim motion transfer.

In Shots, create actual cameras in Blender, save the checkpoint and inspect it.
Save two named shots referencing observed cameras and valid ranges in that same
world. Lighting uses the selected shot camera; global light changes can affect
other shots and must be reviewed. Generate actual camera-specific preview frames.
They are disposable previews, not delivery masters or evidence of smooth motion.

In Render, inspect readiness and explicitly authorize each short shot render.
Play its actual movie before approving. In Final film, arrange approved renders,
encode a new cut, play it, and separately approve the whole film. Preserve its
manifest and movie hash. Repeat for all three scenes before final review.

Revise one scene or shot. Confirm its prior film remains available but outdated,
that current delivery refuses stale inputs, and that replacing/rebuilding those
inputs creates a new reviewable cut rather than overwriting the approved file.

## Interruptions and external systems

Keep an unrelated Blender window with unsaved test edits open. A task must not
replace that file. Close the launcher during a task, choose Keep running in tray,
then reopen it; verify the task and session resume. Save and collect the task,
close while idle, and reopen; checkpoints and pending reviews must persist.

A stale heartbeat is not a live connection. Follow explicit task recovery only
after stopping the identified writer; do not delete lock directories manually.
The project semaphore covers mediated harness paths, not arbitrary external code.

For Codex, use your existing authorized session and provider. Sign in yourself
when required; no credentials belong in source or screenshots. Inspect the saved
scene-specific startup context, ask for a bounded proposal, decline one required
approval and confirm no job executes, then approve an appropriate real job and
review its separate output. Model/provider costs remain your session's costs.
Public CI does not execute authenticated models or grant asset rights.

## Retain acceptance evidence

Keep a private record of candidate source commit, build/archive checksum, OS,
Blender/Node/Python/encoder versions, input identities, job/checkpoint receipts,
render/cut hashes, actual review decisions, observed failures and recovery. Record
what passed and what was not tried; do not check all boxes merely to enable a
release. New creative work never inherits an earlier recording's approval.

Production acceptance requires successful public exact-source gates, the private
input workflow at the same public revision where applicable, and this real local
and human review. A green scripted fixture is useful but is not that final signoff.
The candidate package and public PR do not automatically replace the live studio.
