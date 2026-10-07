# Third-party sources and attribution

The repository's existing MIT license is preserved for original toolkit code. It is not a license for downloaded assets or external retargeting software.

## Optional pinned MotionBricks installation

The setup tool retains exact notices beside each new isolated configuration,
in `<configuration-stem>.licenses`, with hashes in the installation receipt.
No native library, model weight or private animation is distributed in Git.

| Component | Reviewed revision / license | Packaging obligation recorded from the retained text |
|---|---|---|
| motion-bricks.cpp | `ee0cf5d9035f639ed0787f390fb1ce05d6a4c463`, Apache-2.0 | Preserve the license and applicable notices; identify modifications when redistributing modified material. |
| GGML | `8c63e70982c95ceb862e3a1073a2c1beef75d60a`, MIT | Include its copyright and permission notice. |
| MotionBricks G1 weights | `LocalAI-io/MotionBricks-G1-GGML@cc2a47603dbc203a4f18f35dd06ed3611833f506`, NVIDIA Open Model License | Include the agreement and NVIDIA attribution on redistribution; the conversion grants no additional rights. The retained agreement also includes use conditions and references NVIDIA Trustworthy AI terms. |

The pinned source's `scripts/hf/MotionBricks-G1-GGML/UPSTREAM_LICENSE`
separates Apache-2.0 source code from the weight license. Its `NOTICE` identifies
`NVlabs/GR00T-WholeBodyControl@a0732b642c0333077e127a2f56ab0014c196bca4`.
Do not describe the weights as MIT or Apache solely because the application or
backend uses those licenses. This inventory does not replace the agreements.

The local Windows build also retains the LLVM-MinGW runtime notices. A packaged
native build must include notices for the actual compiler runtime/Vulkan
components it ships; the generic setup tool does not infer those from a DLL
filename. The workstation's existing build was reused without dependency upgrades.

The browser renderer uses Three.js 0.186.0 under MIT, with exact file hashes in
`launcher/public/vendor/three/VENDOR.json` and its adjacent license. Windows
WebView2 components retain `launcher/WEBVIEW2-LICENSE.txt` and
`launcher/WEBVIEW2-NOTICE.txt`. Blender and FFmpeg are configured external
executables, not relicensed by this repository. Private asset rights remain
separate from every code and model license above.

## Mwni Animation Retargeting

- Source: https://github.com/Mwni/blender-animation-retargeting
- Reviewed commit: `424f08bd7e675619adf539209a1e8816c242c386`
- Upstream declaration: `GPL-3.0-or-later` in its Blender extension manifest.
- Acquisition: optional explicit `backend-install`; files remain in the user's external library, not this source distribution.
- The adapter references upstream mapping/matrix functions. It does not relicense, strip notices from or claim authorship of that code. Distributing a combined installation may carry additional upstream license obligations; preserve and review the applicable terms.

## Asset sources

- Quaternius: creator-posted Universal Animation Library **Standard** (45 advertised motions), CC0: https://opengameart.org/content/universal-animation-library . Actual downloaded clip names/count are measured at runtime. The larger Source edition must not be represented as the free package.
- Poly Haven: assets from https://polyhaven.com ; CC0 terms https://polyhaven.com/license ; API identification/credit rules https://polyhaven.com/our-api . This application identifies itself as BlenderAssetDirector and credits Poly Haven here and in manifests.
- ambientCG: https://ambientcg.com ; terms https://docs.ambientcg.com/license/ ; documented API https://docs.ambientcg.com/api/ . Actual assets are not bundled.
- Sketchfab: https://sketchfab.com/developers/download-api/downloading-models . Each model retains its own license; authenticated download is not blanket commercial clearance.
- Adobe Mixamo: https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html . Manual acquisition/intake only unless a supported host integration is separately verified; no raw animation-library redistribution.

## Protocol and Blender references

- Codex skills: https://developers.openai.com/codex/skills
- Blender animation Python API changes: https://developer.blender.org/docs/release_notes/5.0/python_api/
- Blender actions: https://docs.blender.org/manual/en/latest/animation/actions.html
- Blender command-line arguments: https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html

No third-party skill package was copied wholesale. Original workflow guidance combines documented provider contracts, source-reviewed backend behavior and explicit validation requirements.
