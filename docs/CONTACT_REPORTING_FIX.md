# Contact-reporting regression found during consolidation

The contact measurement reducer emits `SAMPLED_PENETRATION` or
`NO_SAMPLED_PENETRATION`. The sequence-level summary previously compared that
value with `PENETRATION_DETECTED`, an unused label. A penetrating batch could
therefore receive the misleading aggregate `REVIEW_MEASURED_EXTREMA` even though
its numerical measurements and per-batch warning remained available.

`contact_status.sequence_status` now shares the actual vocabulary and refuses
unknown, missing or unexpectedly supplied measurement batches. Clear measured
batches still return `REVIEW_MEASURED_EXTREMA`, not artistic or continuous-contact
acceptance. Requested contact checks cannot pass with no measured batches.

Portable tests use the real contact reducer, including a negative-clearance
sample. The normal three-version Blender sequence fixture also checks a
read-only diagnostic with a deliberately raised floor: its actual penetrating
mesh samples must retain the aggregate warning without modifying the sequence.
The private acceptance pipeline independently compares aggregate, batch labels
and measured extrema, and fails on sampled penetration or inconsistent evidence.

This reporting correction does not change animation channels, grounded motion,
contact tolerances or license/review records. Historical results remain associated
with their original revisions; do not rewrite old evidence to imply a rerun.
