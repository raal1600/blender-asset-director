"""Aggregate the actual contact-diagnostics vocabulary without hiding warnings."""
from .core import require


def sequence_status(batches, requested):
    if not requested:
        require(not batches, 'CONTACT_STATUS_INVALID', 'Unrequested measurements cannot be silently discarded')
        return 'NOT_MEASURED'
    require(isinstance(batches, list) and bool(batches), 'CONTACT_SAMPLES_REQUIRED', 'Requested contact measurement produced no batches')
    valid = {'SAMPLED_PENETRATION', 'NO_SAMPLED_PENETRATION'}
    require(all(isinstance(batch, dict) and batch.get('status') in valid for batch in batches),
            'CONTACT_STATUS_INVALID', 'Unknown or absent measured contact status')
    return ('SAMPLED_PENETRATION' if any(batch['status'] == 'SAMPLED_PENETRATION' for batch in batches)
            else 'REVIEW_MEASURED_EXTREMA')
