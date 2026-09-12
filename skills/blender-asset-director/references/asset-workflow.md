# Shared asset and motion workflow

This service is reusable across scene types. It does not dictate a hero, terrain, era, camera, motion or duration.

1. Inspect actual supplied scene resources and preserve originals/unsaved work. Record identities, usable materials, existing motion and unknowns. Run detailed rig inspection only for skeletal work.
2. Receive explicit gaps from the host-authored production contract. Search scene resources and the local catalog first, then supported external providers. Do not source what already meets the brief.
3. Run `providers` and read `providers.md`. Poly Haven covers models/materials/HDRIs; ambientCG primarily materials. Sketchfab downloads require authentication. `seed` describes one real Quaternius Standard pack, not an invented animation catalog. `seed --download` is explicit acquisition. Mixamo/BlenderKit/Poly Pizza need a discovered supported host tool or manual intake.
4. Select a bounded shortlist. Licensing, zero price, permission and supported formats are gates; metadata scores are not visual-quality estimates. Unknown/custom rights remain review-required. Account access or a viewable webpage does not prove a free download.
5. Acquire with existing receipts, checksums, size limits and dependency guards. Credentials remain private, restricted to intended API origins. Do not execute downloaded scripts, weaken TLS/host restrictions or raise budgets silently. Raw assets remain outside the source repository.
6. Index actual motion files with `job-prepare index`, `job-run`, `index-collect`. Record real action slots, owning objects, FPS and source hashes. Packs are not clip records until inspected. Never manufacture names or rig compatibility.
7. Performance selects suitable source motion before retargeting. Use the pinned Mwni adapter only for supported skeletal work; object/mechanical animation needs appropriate scoped transforms, not a human motion library. Preserve attachments and existing actions. Flat-ground validation precedes terrain following.
8. Numerical checks and preview evidence remain distinct. Root-height following is not foot IK; static translation is not gait. Text-only reviewers cannot judge images. Missing or unreachable motion sources remain blockers.
9. Report actual candidates, provenance, selected assets, modifications, file paths and unresolved issues. Never call a scene accepted because a fixture passed.

See `jobs.md` for original commands, `studio-contracts.md` for new scene-independent planning/camera/light jobs, and `motion.md` for specific retargeting gates. Existing example filenames are optional benchmarks, not default production inputs.
