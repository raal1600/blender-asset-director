# Explicit shot render devices

In Render, refresh readiness, select a detected device, choose shot dimensions
and samples, then confirm the named device and render bounds. CPU is the default
and remains compatible with historical readiness and job options. Old readiness
without device observations needs refreshing before GPU selection is available.

The first GPU backend is NVIDIA OptiX. CUDA, HIP, Metal, multi-GPU and automatic
device selection are not implemented. Availability depends on the installed
Blender build, GPU and driver. Director never installs drivers or changes global
Blender preferences. Device names are escaped in the UI.

GPU authorization binds the exact observed backend and device ID into the job.
Preparation rejects unknown devices before acquiring a writer; execution probes
again and enables only that GPU, not hybrid CPU rendering. A missing or failing
GPU fails the job and retains evidence. There is no automatic CPU retry: choose
CPU and authorize a separate render if desired.

When the source enables denoising, GPU mode uses OptiX denoising, explicitly
disclosed in the confirmation. Disabled denoising stays disabled. CPU mode uses
the source's CPU denoiser, with GPU denoising off; a source requiring OptiX
denoising is refused in CPU mode until the user chooses GPU or reviews the source.
These worker-local changes are never saved into the source checkpoint.

Existing limits remain: 360 frames per shot, even dimensions up to 1920x1080,
1-128 samples, two billion pixel-samples, and the launcher 900-second deadline.
The worker's CPU thread count remains two. FFmpeg H.264 encoding and Final film
limits are unchanged. Preview jobs and the embedded viewer are separate.

Render receipts record backend, exact device, denoiser, Blender version and no
fallback. These are configured-device plus successful-frame evidence, not GPU
utilization telemetry or a universal performance guarantee. New movies still
need their own visual/human review; old approvals are not transferred.

## Validation

Portable Python and Node tests cover selection, compatibility, refusal, identity,
escaped UI and worker configuration. Existing real CPU fixtures remain required.
Run the additional real device fixture only with explicit bounded GPU approval:

```sh
blender --background --factory-startup --disable-autoexec --threads 2 \
  --python-exit-code 11 --python tools/render_device_fixture.py -- /new/test/path OPTIX
```

It generates its own source and catalog, checks missing-device refusal, renders
a two-frame 320x180 smoke test and 48 frames at 1280x720 with eight samples, and
verifies hashes and the unchanged source. It requires exactly one observed GPU;
missing hardware fails rather than producing a CPU-labelled GPU pass. Use CPU
instead of OPTIX for the smaller CPU regression. Hosted CPU CI is not proof of
native GPU, desktop or human creative acceptance. Keep machine-specific reports
private and record the exact tested source/build separately.
