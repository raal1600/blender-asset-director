# Third-party sources and attribution

The repository's existing MIT license is preserved for original toolkit code. It is not a license for downloaded assets or external retargeting software.

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
