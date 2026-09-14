# Provider contracts and rights

| Provider | Search | Acquisition | Limits |
|---|---|---|---|
| Local | SQLite catalog, actual indexed clips | Explicit intake | No recursive whole-disk scan |
| Quaternius | One evidenced free Standard pack | Creator-posted OpenGameArt ZIP | Advertised 45 is not the measured clip count |
| Poly Haven | Documented asset API | 1k/2k manifests, dependencies/checksums | CC0 assets; identify application and credit API source |
| ambientCG | Documented v3 API | Low-resolution ZIP; explicit documented v2 download metadata fallback | Fail on unknown schema rather than fabricate URL |
| Sketchfab | Public official search API | Official download API with `SKETCHFAB_TOKEN` | Temporary links; credentials never forwarded to storage hosts; auth must be runtime-tested |
| Mixamo | Official site/manual or user's approved host workflow | User download, explicit intake | No assumed public automation API; do not redistribute raw library |
| BlenderKit / Poly Pizza | Existing supported host tool if actually discovered, otherwise manual | Intake authorized files | Not claimed as implemented direct API adapters |

A source may be implemented but unreachable or rate-limited. `providers` describes code paths, not proof that every source is currently available. Search responses label live, fresh-cache or stale-cache evidence. No account is necessary for the Quaternius/Poly Haven/ambientCG baseline.

Default commercial selection accepts evidenced CC0 or CC BY 3.0/4.0. Unknown/custom/NC/ND/editorial licenses require review. This is a conservative engineering policy, not a determination of all legal rights. Trademark, likeness and third-party rights are not automatically cleared by an asset copyright license. Existing user assets may be inspected without asserting a new license.

Manual intake evidence example (fill real values, never copy false claims):

```json
{"title":"Actual asset title","kind":"pack","source_url":"https://creator.example/actual-page","license_id":"UNKNOWN","license_url":"","author":"Actual creator","price":0,"tags":["animation"],"attested":false}
```

Use `attested: true` only after the user or agent actually verifies that evidence. Raw models, animations, provider API results, credentials and user scenes do not belong in this skill's public repository.

Primary references:
- https://opengameart.org/content/universal-animation-library
- https://polyhaven.com/our-api
- https://polyhaven.com/license
- https://docs.ambientcg.com/api/v3/assets/
- https://docs.ambientcg.com/license/
- https://sketchfab.com/developers/download-api/downloading-models
- https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html

## Local motion inboxes

See `local-motion-library.md` for registered read-only roots, scoped Mixamo grants,
bounded sync and preflight. Copy/index readiness, import eligibility and performance
are separate. Folder names alone never authorize import; no raw redistribution or
unofficial provider downloader is included. Other datasets still need their own
licenses and any native-format converter not already present.
