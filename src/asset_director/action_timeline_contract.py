"""Bounded native clips and planar travel; optional inspected gait calibration."""
import math
import re
from .core import fields, require
from .motion_timing import number

VERSION = 'action-timeline-v1'
STITCH_VERSION = 'native-stitch-v1'
EDIT_VERSION = 'native-motion-edit-v1'


def validate(change):
    fields(change, {'performer', 'mode', 'clips'}, {'performer', 'mode', 'clips'})
    clips = change['clips']
    require(change['mode'] == 'timeline' and isinstance(clips, list) and len(clips) <= 64,
            'INVALID_TIMELINE', 'Use at most 64 clips per performer')
    seen, end = set(), -100001
    for index, clip in enumerate(clips):
        fields(clip, {'id', 'take_id', 'start', 'frames', 'speed', 'repeat_reviewed', 'travel', 'transition', 'source_range', 'heading_deg', 'root_intent'},
               {'id', 'take_id', 'start', 'frames', 'speed', 'repeat_reviewed', 'travel'})
        require(isinstance(clip['id'], str) and re.fullmatch(r'clip_[a-zA-Z0-9_-]{1,64}', clip['id'])
                and clip['id'] not in seen, 'INVALID_TIMELINE', 'Clips need distinct stable identities')
        seen.add(clip['id'])
        require('root_intent' not in clip or clip['root_intent']=='stationary-reviewed',
                'MOTION_BRICKS_ROOT_INTENT','Only explicitly reviewed stationary intent is supported; travelling in-place clips need a derived root preparation')
        if 'source_range' in clip:
            interval = clip['source_range']
            require(isinstance(interval, list) and len(interval) == 2
                    and all(number(v, -100000, 100000) for v in interval) and interval[0] < interval[1],
                    'INVALID_SOURCE_RANGE', 'Choose an increasing observed source range')
        require('heading_deg' not in clip or number(clip['heading_deg'], -180, 180),
                'INVALID_HEADING', 'Heading is an explicit world-Z rotation from -180 to 180 degrees')
        require(isinstance(clip['take_id'], str) and re.fullmatch(r'take_[0-9a-f]{64}', clip['take_id']),
                'INVALID_TIMELINE', 'Choose an observed native take')
        require(type(clip['start']) is int and -100000 <= clip['start'] <= 100000
                and type(clip['frames']) is int and 2 <= clip['frames'] <= 3601
                and number(clip['speed'], .1, 4) and type(clip['repeat_reviewed']) is bool,
                'INVALID_TIMING', 'Use bounded integer frames and speed from 0.1 to 4')
        require(clip['start'] > end, 'TIMELINE_OVERLAP', 'Clips on one performer cannot overlap; move or shorten the clip')
        join = clip.get('transition')
        if index and abs(heading_delta(clips[index-1].get('heading_deg', 0.), clip.get('heading_deg', 0.))) > 1e-7:
            require(join is not None and join.get('mode') == 'turn', 'HEADING_TRANSITION_REQUIRED',
                    'Changing a clip heading needs an explicit turn transition')
        if join is not None:
            fields(join, {'frames', 'match_phase', 'mode', 'seed', 'profile_sha256', 'sampling', 'contacts'}, {'frames', 'match_phase'})
            if join.get('mode') == 'generated':
                require(join['match_phase'] is False and type(join.get('seed')) is int and 0 <= join['seed'] < 2**32
                        and isinstance(join.get('profile_sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', join['profile_sha256']),
                        'INVALID_TRANSITION', 'Generated repositioning needs a verified rig profile and seed, with phase matching off')
                from .motion_bricks_contract import sampling_settings, contact_plan
                sampling_settings(join.get('sampling','argmax'),join['seed'])
                contact_plan(join.get('contacts'))
            else:
                require(not any(k in join for k in ('seed','profile_sha256','sampling','contacts')), 'INVALID_TRANSITION', 'Model settings require generated mode')
            require(join.get('mode', 'blend') in {'blend', 'turn', 'generated'}, 'INVALID_TRANSITION', 'Choose a pose connection or an explicit turn preview')
            require(index > 0 and type(join['frames']) is int and 2 <= join['frames'] <= 120
                    and type(join['match_phase']) is bool,
                    'INVALID_TRANSITION', 'A connection needs a previous clip and 2 to 120 added frames')
            require(clip['start'] == end + 1 + join['frames'], 'INVALID_TRANSITION',
                    'Connected clips must follow their visible transition; move following clips together')
        end = clip['start'] + clip['frames'] - 1
        require(end <= 100000, 'INVALID_TIMING', 'Clip exceeds the frame limit')
        travel = clip['travel']
        if travel is not None:
            fields(travel, {'delta_m', 'meters_per_cycle', 'gait_id'}, {'delta_m', 'meters_per_cycle'})
            require('gait_id' not in travel or isinstance(travel['gait_id'], str)
                    and re.fullmatch(r'[a-f0-9]{64}', travel['gait_id']),
                    'INVALID_TRAVEL', 'Automatic pace needs an exact inspected gait identity')
            require(isinstance(travel['delta_m'], list) and len(travel['delta_m']) == 2
                    and all(number(v, -10000, 10000) for v in travel['delta_m'])
                    and 0 < math.hypot(*travel['delta_m']) <= 10000
                    and number(travel['meters_per_cycle'], .001, 1000),
                    'INVALID_TRAVEL', 'Set a planar distance in metres and an explicit travel pace per cycle')
    if clips:
        require(end - clips[0]['start'] <= 3600, 'RESOURCE_LIMIT', 'Timeline exceeds 3600 intervals')
    return change


def source_range(clip, take):
    interval = clip.get('source_range', take['range'])
    require(isinstance(interval, list) and len(interval) == 2 and all(number(v, -100000, 100000) for v in interval)
            and take['range'][0] <= interval[0] < interval[1] <= take['range'][1],
            'INVALID_SOURCE_RANGE', 'Trim must stay inside the observed native take')
    return interval


def heading_delta(a, b):
    raw = b-a
    value = (raw+180) % 360-180
    return 180. if value == -180 and raw > 0 else value


def timing(clip, take):
    """Integer occupancy, fractional native sampling, visible repeat/trim."""
    interval = source_range(clip, take)
    span = interval[1] - interval[0]
    require(number(span, 1e-6, 100000), 'INVALID_TIMING', 'Take has no usable duration')
    cycles = (clip['frames'] - 1) * clip['speed'] / span
    travel = clip['travel']
    trimmed = interval != take['range']
    require(not trimmed or travel is None, 'TRIM_TRAVEL_REVIEW',
            'Trimmed native clips cannot inherit full-cycle travel calibration; turn off added path movement first')
    require(not trimmed or not (clip.get('transition') or {}).get('match_phase', False), 'TRIM_PHASE_REVIEW',
            'A trimmed native segment cannot inherit full-cycle phase matching')
    if travel:
        if 'gait_id' in travel:
            gait = take.get('gait') or {}
            require(gait.get('status') == 'estimated' and gait.get('id') == travel['gait_id'],
                    'GAIT_CHANGED', 'Automatic pace changed; inspect the saved performer again')
            distance = math.hypot(*travel['delta_m'])
            yaw = math.radians(clip.get('heading_deg', 0.))
            direction = [gait['direction'][0]*math.cos(yaw)-gait['direction'][1]*math.sin(yaw),
                         gait['direction'][0]*math.sin(yaw)+gait['direction'][1]*math.cos(yaw)]
            require(abs(travel['meters_per_cycle'] - gait['meters_per_cycle']) < 1e-7
                    and math.dist([v / distance for v in travel['delta_m']], direction) < 1e-6,
                    'INVALID_TRAVEL', 'Automatic travel must use the inspected pace and direction; use reviewed manual calibration for overrides')
        cycles = math.hypot(*travel['delta_m']) / travel['meters_per_cycle']
        expected = math.ceil(cycles * span / clip['speed'] - 1e-9) + 1
        require(clip['frames'] == expected, 'INVALID_TRAVEL', 'Distance, pace and occupied frames disagree')
    require(.001 <= cycles <= 100, 'RESOURCE_LIMIT', 'Keep each clip within 100 cycles')
    # Integer presentation rounding is endpoint hold, never an implicit loop.
    if not travel and 1 < cycles <= 1 + clip['speed'] / span + 1e-9:
        cycles = 1.0
    require(not trimmed or cycles <= 1+1e-9, 'TRIM_LOOP_REVIEW',
            'Trimmed source segments are single-pass; retain the full reviewed cycle for repeats')
    require(cycles <= 1 + 1e-9 or clip['repeat_reviewed'], 'LOOP_REVIEW_REQUIRED',
            'Review this take as a repeatable cycle before repeating it')
    return {'cycles': cycles, 'end': clip['start'] + clip['frames'] - 1,
            'native_end': clip['start'] + cycles * span / clip['speed']}


def connection(previous, clip, previous_take, take):
    """Continue measured path velocities through extra time, never stretch strides.

    Units are metres per *scene frame*. Facing is not inferred from travel.
    The added displacement is explicit and also displayed by the browser.
    """
    if not clip.get('transition'):
        return None
    a, b = timing(previous, previous_take), timing(clip, take)
    duration = clip['start'] - a['native_end']
    require(0 < duration <= 122, 'INVALID_TRANSITION', 'Invalid connection interval')
    def velocity(c, t):
        return [v / (t['native_end'] - c['start']) for v in c['travel']['delta_m']] if c['travel'] else [0., 0.]
    va, vb = velocity(previous, a), velocity(clip, b)
    na, nb = math.hypot(*va), math.hypot(*vb)
    mode = clip['transition'].get('mode', 'blend')
    heading_a, heading_b = previous.get('heading_deg', 0.), clip.get('heading_deg', 0.)
    yaw = heading_delta(heading_a, heading_b)
    require(mode == 'turn' or abs(yaw) < 1e-7, 'HEADING_TRANSITION_REQUIRED',
            'A heading change needs an explicit turn transition or an authored intermediate take')
    require(abs(yaw) <= 135, 'TURN_SOURCE_REQUIRED',
            'A turn over 135 degrees needs an observed intermediate turn take or Blender editing')
    if mode == 'blend' and na > 1e-9 and nb > 1e-9:
        require(sum(x*y for x, y in zip(va, vb)) / (na*nb) >= math.cos(math.radians(135)),
                'STITCH_DIRECTION_REVIEW', 'This sharp reversal needs a turn or stop clip, or a reviewed Blender edit')
    return {'start': a['native_end'], 'end': clip['start'], 'duration_frames': duration,
            'mode': mode, 'heading_in_deg': heading_a, 'heading_out_deg': heading_b, 'turn_delta_deg': yaw,
            'velocity_in': va, 'velocity_out': vb,
            'placement_pending': mode == 'generated',
            'delta_m': [0., 0.] if mode == 'generated' else [(x+y)*duration*(.125 if mode == 'turn' else .5) for x, y in zip(va, vb)]}
