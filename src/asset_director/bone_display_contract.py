"""Explicit, portable contracts for armature display review."""
from .core import fields, require
from .transfer_contract import name, names
from .motion_assets import sha

AUDIT_FIELDS = {'target_object'}
DISPLAY_FIELDS = {'target_object', 'target_fingerprint', 'display_type',
                  'show_custom_shapes', 'show_in_front', 'visible_bones', 'hide_widget_objects'}


def validate(operation, options):
    if operation == 'bone-display-audit':
        fields(options, AUDIT_FIELDS, AUDIT_FIELDS)
    else:
        fields(options, DISPLAY_FIELDS, DISPLAY_FIELDS-{'visible_bones', 'hide_widget_objects'})
        sha(options['target_fingerprint'])
        require(options['display_type'] in ('OCTAHEDRAL', 'STICK'), 'INVALID_SCHEMA', 'Choose pointed or stick bone display')
        for key in ('show_custom_shapes', 'show_in_front'):
            require(type(options[key]) is bool, 'INVALID_SCHEMA', 'Display toggles must be boolean')
        if 'visible_bones' in options: names(options['visible_bones'], maximum=4096)
        if 'hide_widget_objects' in options: names(options['hide_widget_objects'], maximum=256)
    name(options['target_object'])
