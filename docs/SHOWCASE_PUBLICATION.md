# Showcase repair and publication handoff — September 16, 2026

## Completion gate: complete native media must be present

The showcase PR is **not publication acceptance** until its media, browser and
normal CI gates pass. The previous Base64 file contained only 6,888 characters;
it was not the complete recording. Removing its expected hash and testing for a
minimum size did not repair it. The new workflow deliberately refuses missing,
truncated or changed media before downloading Blender or rendering 480 frames.

The maintainer authorized the latest real recording and its poster for public
showcase use. That permission does not include source FBXs, `.blend` projects,
private reports or future recordings. The exact native files are defined in
[`showcase/approved-media.json`](../showcase/approved-media.json):

| Repository destination | Bytes | SHA256 |
|---|---:|---|
| `showcase/media/latest-demo.mp4` | 1,701,127 | `6c8f43ed25b712f36dadfd0c2ccb0c2fc8a494c53b60d1baead56b7c64268fe7` |
| `showcase/media/latest-demo-poster.jpg` | 49,496 | `baae065af5d94b0eec7286a978f17010c7c93eb1db552c74da0b9889be844392` |

The MP4 is 960 × 800, H.264/yuv420p, 120 frames at 30 FPS for four seconds.
The poster is a 720 × 600 JPEG. This is the complete **recording excerpt**, not
the full 38.5-second sequence. Do not substitute another encode and copy its hash
into the approval. Never place a signed private-artifact download URL or the full
private artifact ZIP in public source, logs or Pages.

The attempted connector transfer did not store the complete media. A maintainer
must upload only the two native files to these paths on the existing showcase PR
branch using GitHub's normal file upload or Git. The source repair itself does
not claim that upload succeeded. Do not merge while `MISSING_APPROVED_MEDIA` is
reported. No release, tag or workstation installation change is needed.

## Verification

With FFmpeg/ffprobe installed, run:

```sh
python tools/run_checks.py --offline
python tools/verify_showcase_media.py --report build/showcase-media-report.json
```

The verifier checks exact byte counts and both SHA256 values, counts decoded
frames with ffprobe, and fully decodes with ffmpeg's strict error handling.
`--identity-only` is a fast preflight and reports `IDENTITY_PASS`, not full
acceptance. CI requires the subsequent complete verification too.

The site builder checks again before staging, copies only the approved media,
keeps the synthetic site at `/technical-validation/`, retains a root `.nojekyll`,
and checks the exact output allowlist. Browser tests use the same branded Chrome
installed by the workflow. They check the **served** file hashes, actual playback
after a user gesture, desktop/mobile dimensions, speed control, HTTP/JavaScript
errors and the separate technical lab. Both reports and screenshots are retained
under `transition-lab-browser-evidence`; media failures are retained under
`showcase-media-verification`. Reports identify the Actions run and source commit.

## Failed checks that led to this repair

On commit `bb6d537027a55b4811fde405483b0645724ed03d`, Pages push run
`35046216031` and PR run `35046218061` both failed at `len(payload) > 100000`.
Their dependent validation/deployment jobs accounted for four skips. They were
not four independent test failures. Push runs now target main only; PRs run one
validation pipeline, and superseded PR runs may be cancelled. Full synthetic
validation remains required; a missing video fails before that expensive work.

The Blender 5.0.0 job in CI run `35046218116` passed its fixtures but failed the
Quaternius live download with `CONNECTION_FAILED`. The acceptance tool now makes
at most three attempts for explicitly classified acquisition transport errors,
recording **every** attempt in `live_acceptance.json`. It never retries or ignores
authorization, license, hash, schema, Blender execution or QA failures. Exhausted
transport failures still fail CI and leave real-motion acceptance blocked.

Portable regression tests are not real media/Blender acceptance. Local checks
are labelled local. The PR conversation and Actions retain the eventual tested
commit/run pairs; no queued run, older main run or absent artifact is a pass.
Main deployment and live-site verification are required after a tested merge.
