# Resume validation

GitHub authorization is fixed and the implementation is published on `main`. Do not ask for another repository-permission change.

Latest tested code: `f5e6c6991f4d1df1f2f9881daf62b61562ec2f66`.
Run: https://github.com/raal1600/blender-asset-director/actions/runs/34719768696

## Passed gates

- 69 unit tests plus installer checks on Linux/Python 3.11 and 3.13 and Windows/Python 3.11.
- Real Blender 4.5.3 and 5.0.0 import/rig/action/retarget/FPS/NLA/controller/save fixtures.
- Live Poly Haven HDRI search/download/import and ambientCG material search/download/import in Blender 5.0.0.

## Current blocker

The runner cannot connect to `opengameart.org` to acquire the creator-posted Quaternius Standard animation pack. The bounded, public-IP-validated connection attempts return `CONNECTION_FAILED`. The request did not reach HTTP authentication or archive parsing. The actual source animation index/retarget test is consequently BLOCKED; overall CI correctly remains failed.

1. Fetch current `main` and read current CI evidence before editing; do not assume the historical commit is still latest.
2. Diagnose the named provider connectivity without weakening TLS, origin validation, or private-address rejection. Verify a supported creator-provided alternative acquisition route if needed. Do not scrape private APIs or use unaudited mirrors.
3. Explicit local intake of an authorized creator download is also supported. Record its actual source/license/hash; do not present manual acquisition as automated success.
4. Once the real pack is available, run actual indexing and record clip names, owners, slots and duration. Then execute `tools/real_motion_test.py` through the acceptance flow. Fix genuine Blender/data incompatibilities rather than treating synthetic fixtures as sufficient.
5. Update ACCEPTANCE and BUILD_TESTS with actual measured outcomes. Refresh SOURCE_MANIFEST after source changes. Never turn an unavailable required live gate into a green skip.
6. Only then hand off full end-to-end readiness. Controlled local installation/read-only checks may proceed sooner with the blocker clearly disclosed.
7. The actual Windows Codex/DeepSeek/Blender MCP connection and `Desert Warrior.blend` still need local acceptance. Do not mutate the original file. Gate B requires the user to say **Run the Desert Warrior test**.

Preserve direct-main authorization without force-pushing. Keep assets, credentials and user logs outside the public repository. No paid generation, local AI inference or heavy GPU render. No unsupported claims that a text-only model visually inspected frames.
