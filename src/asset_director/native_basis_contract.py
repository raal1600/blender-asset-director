"""Content comparison for preserved native defaults, independent of labels.

This is not Action selection or candidate identity. Those retain their exact
binding/audit fingerprints. Here every source's channels, slot, range and
annotations must survive; a multiset retains duplicate content bindings.
"""
from .core import digest


def source_content(sources):
    return sorted(digest({k: v for k, v in row.items() if k != 'action'})
                  for row in sources)


def equivalent_inputs(saved, observed):
    return (isinstance(saved, dict) and isinstance(observed, dict)
            and {k: v for k, v in saved.items() if k != 'sources'}
            == {k: v for k, v in observed.items() if k != 'sources'}
            and source_content(saved.get('sources', []))
            == source_content(observed.get('sources', [])))
