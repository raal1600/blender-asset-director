"""Expected acceptance evidence, independent of reports produced by the runners.

This is a coverage inventory, not a substitute for executing the journeys.
Changing a checkpoint or matrix requires updating this inventory deliberately.
"""
SCHEMA = 'asset-director.ci-evidence/1'
STAGES = {
    'installation': ('installed_checkout', 'catalog_initialized', 'launcher_authenticated'),
    'onboarding': ('project_created', 'sources_verified', 'scene_audited'),
    'execution': ('foreign_binding_refused', 'cancellation_blocks', 'confirmed_render', 'idempotent_replay'),
    'production': ('camera_authored', 'look_authored', 'camera_verified', 'production_preview'),
    'recovery': ('source_drift_refused', 'session_rotated', 'restart_persisted', 'trash_restored'),
}
SCENARIOS = {
    'onboarding': ('installation', 'onboarding'),
    'execution': ('installation', 'onboarding', 'execution'),
    'production': ('installation', 'onboarding', 'execution', 'production'),
    'recovery': ('installation', 'onboarding', 'execution', 'recovery'),
    'full': tuple(STAGES),
}
BOOTSTRAP_CHECKS = (
    'offline archive SHA256', 'real bootstrap install', 'repeat install',
    'update with backup', 'saved path discovery', 'host config unchanged',
    'offline uninstall preserves library',
)
# id, script, generated report (or stdout marker), pass library, extra arguments.
BLENDER_SUITES = {
    'authoring': (
        ('studio', 'studio_fixture.py', 'studio_report.json', False, ()),
        ('camera', 'camera_fixture.py', 'camera_report.json', False, ()),
        ('look', 'look_fixture.py', 'look_report.json', False, ()),
        ('pose', 'test_pose_transfer_blender.py', '@POSE_TRANSFER_REGRESSION_PASS', False, ()),
        ('floor', 'test_floor_blender.py', '@FLOOR_CONTACT_REGRESSION_PASS', False, ()),
        ('bone-display', 'bone_display_fixture.py', 'REPORT.json', True, ()),
        ('ground-contact', 'ground_contact_fixture.py', 'ground_contact_report.json', False, ()),
    ),
    'motion': (
        ('headless', 'headless_fixture.py', 'fixture_report.json', True, ()),
        ('retarget-pipeline', 'retarget_pipeline_fixture.py', 'retarget_pipeline_report.json', True, ()),
        ('motion-foundation', 'motion_foundation_fixture.py', 'motion_foundation_report.json', True, ()),
        ('proxy-visual', 'proxy_visual_fixture.py', 'proxy_visual_report.json', True, ()),
        ('local-motion', 'local_motion_fixture.py', 'local_motion_report.json', True, ()),
        ('transfer-planning', 'transfer_planning_fixture.py', 'transfer_planning_report.json', True, ()),
        ('transfer-custom', 'transfer_planning_fixture.py', 'transfer_planning_report.json', True, ('custom',)),
    ),
    'continuity': (
        ('translation-precision', 'translation_precision_fixture.py', 'translation_precision_report.json', False, ()),
        ('fbx-anchor', 'fbx_anchor_fixture.py', 'fbx_anchor_report.json', False, ()),
        ('action-collision', 'action_collision_fixture.py', 'action_collision_report.json', False, ()),
        ('reference-identity', 'reference_identity_fixture.py', 'reference_identity_report.json', True, ()),
        ('sequence', 'sequence_fixture.py', 'sequence_report.json', True, ()),
    ),
}
BLENDER_VERSIONS = ('4.5.3', '5.0.0', '5.2.1')
NEEDED_JOBS = {
    'portable', 'installation', 'onboarding', 'execution', 'production',
    'recovery', 'studio', 'blender', 'launcher', 'showcase',
}


def checkpoints(scenario):
    return tuple(check for stage in SCENARIOS[scenario] for check in STAGES[stage])


def partitions():
    result = {}
    for scenario in SCENARIOS:
        for platform in ('linux', 'win32'):
            result[('studio', scenario, platform)] = checkpoints(scenario)
    for platform, shell in (('linux', 'sh'), ('darwin', 'sh'), ('win32', 'powershell'), ('win32', 'pwsh')):
        result[('installation', shell, platform)] = BOOTSTRAP_CHECKS
    for suite, fixtures in BLENDER_SUITES.items():
        for version in BLENDER_VERSIONS:
            result[('blender', suite, version)] = tuple(row[0] for row in fixtures)
    return result
