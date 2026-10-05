"""Create root-travel Action copies from explicit, reviewed sole contacts.

An offline Blender preparation step for in-place clips. Never edits native bone
curves, source Actions, timing, current timeline or rest/skin geometry. Contact
intervals and vertex identities are supplied explicitly, never guessed from names.
"""
import json
import math
import bpy
from mathutils import Vector
from .core import require, digest
from . import action_layer as layer, motion_stitch_math as sm, sequence_math as qm
from .motion_stitch import Sampler
from .motion_bricks_retarget import load_profile
from .motion_bricks_feet import Soles


def prepare(obj, options):
    require(bpy.context.scene.unit_settings.scale_length==1. and not layer.reason(obj) and not any(p.constraints for p in obj.pose.bones),
            'ROOT_CONTACT_RIG', 'Root preparation requires unconstrained native animation in scene metres')
    profile = load_profile(obj)
    require(isinstance(options, dict) and set(options) == {'schema','profile_sha256','clips'} and
            options['schema'] == 'root-contact-preparation-v1' and options['profile_sha256'] == digest(profile),
            'ROOT_CONTACT_PROFILE', 'Root contacts must identify the exact reviewed anatomical mapping')
    clips = options['clips']
    require(isinstance(clips,list) and 1 <= len(clips) <= 8, 'ROOT_CONTACT_LIMIT', 'Prepare 1 to 8 explicit source clips')
    reader = Sampler(obj); soles = None; created = []; reports = []; tracks = []; original_timeline = obj.get('bad_action_timeline_v1')
    parent = obj.parent.matrix_world @ obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
    inverse = parent.to_3x3().inverted()
    try:
        soles = Soles(obj, reader.clone, profile['roles'])
        for clip in clips:
            require(isinstance(clip,dict) and set(clip) == {'action','source_sha256','name','placement_delta_m','contacts'},
                    'ROOT_CONTACT_INPUT', 'Specify source identity, a new Action name, placement and reviewed contacts')
            require(isinstance(clip['name'],str) and 1 <= len(clip['name']) <= 60 and clip['name'] not in bpy.data.actions,
                    'ROOT_CONTACT_NAME', 'Choose a distinct new Action name')
            bindings = [(a,s) for a,s in layer.bindings(obj) if a.name == clip['action']]
            require(len(bindings) == 1, 'ROOT_CONTACT_SOURCE', 'Choose one unambiguous source Action/slot on this rig')
            action, slot = bindings[0]
            require(digest(layer.channels(action)) == clip['source_sha256'], 'ROOT_CONTACT_SOURCE', 'Source Action changed after contact review')
            start, end = layer.ops.action_range(action,slot); span = end-start
            require(0 < span <= 300, 'ROOT_CONTACT_LIMIT', 'Prepare positive clips no longer than 300 frames')
            travel = clip['placement_delta_m']
            require(isinstance(travel,list) and len(travel)==2 and all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=100 for v in travel),
                    'ROOT_CONTACT_INPUT', 'Placement must be two finite world-metre displacements')
            contacts = clip['contacts']
            require(isinstance(contacts,list) and 1 <= len(contacts) <= 32, 'ROOT_CONTACT_INPUT', 'Supply nonempty reviewed core stance intervals')
            previous = start
            for item in contacts:
                require(isinstance(item,dict) and set(item)=={'side','start','end','mesh','vertex'} and item['side'] in ('left','right') and
                        all(type(item[k]) in (int,float) and math.isfinite(item[k]) for k in ('start','end')) and
                        previous <= item['start'] < item['end'] <= end,
                        'ROOT_CONTACT_INPUT', 'Core stance intervals must be ordered and non-overlapping within the source range')
                require(item['mesh'] in soles.source_objects and type(item['vertex']) is int,
                        'ROOT_CONTACT_VERTEX', 'Specify an observed sole vertex on the bound skin')
                skin = soles.source_objects[item['mesh']]; i = item['vertex']
                require(0 <= i < len(skin.data.vertices), 'ROOT_CONTACT_VERTEX', 'Sole vertex is out of range')
                names = [profile['roles'][item['side']+'_'+part] for part in ('foot','toe')]
                groups = {skin.vertex_groups[n].index for n in names if n in skin.vertex_groups}
                require(sum(g.weight for g in skin.data.vertices[i].groups if g.group in groups)>.8,
                        'ROOT_CONTACT_VERTEX', 'The reviewed vertex must be dominated by its mapped foot/toe')
                previous = item['end']
            require(abs(contacts[0]['start']-start)<1e-6 and abs(contacts[-1]['end']-end)<1e-6,
                    'ROOT_CONTACT_INPUT', 'Contact preparation requires reviewed support at both source endpoints')
            motion = ({'speed':1.}, {'range':[start,end]}, action,slot,{})
            cache = {}
            def sample(frame):
                key = round(frame,9)
                if key not in cache:
                    reader.read(motion,frame-start,endpoint=abs(frame-end)<1e-8)
                    points = {(c['mesh'],c['vertex']):soles.landmark(c['mesh'],c['vertex']) for c in contacts}
                    cache[key] = {'location':reader.clone.location.copy(), 'points':points, 'min':min(soles.heights().values())}
                return cache[key]
            stances = []
            for item in contacts:
                middle = (item['start']+item['end'])/2
                anchor = sample(middle)['points'][(item['mesh'],item['vertex'])]+Vector((*travel,0))*(middle-start)/span
                stances.append((item,anchor))
            def offset(frame, stance):
                item,anchor = stance
                return anchor-sample(frame)['points'][(item['mesh'],item['vertex'])]
            def planar(frame):
                for stance in stances:
                    if stance[0]['start'] <= frame <= stance[0]['end']: return offset(frame,stance)
                for left,right in zip(stances,stances[1:]):
                    a,b = left[0]['end'],right[0]['start']
                    if a < frame < b:
                        h = min(1/64,(left[0]['end']-left[0]['start'])/4,(right[0]['end']-right[0]['start'])/4)
                        pa,pb = offset(a,left),offset(b,right)
                        va = (offset(a+h,left)-offset(a-h,left))/(2*h)
                        vb = (offset(b+h,right)-offset(b-h,right))/(2*h)
                        return Vector(qm.hermite(list(pa),list(pb),list(va),list(vb),b-a,(frame-a)/(b-a)))
                raise ValueError('Contact preparation range changed')
            count = math.ceil(span*8); rows = []
            for i in range(count+1):
                frame = start+span*i/count; delta = planar(frame); row = sample(frame)
                delta.z = profile['ground_z']+.001-row['min']
                rows.append((frame,row['location']+inverse@delta))
            copy = action.copy(); copy.name = clip['name']; created.append(copy)
            clone = reader.clone; ad = clone.animation_data_create(); ad.action = copy; ad.use_nla = False
            if slot is not None: ad.action_slot = next(s for s in copy.slots if s.identifier == slot.identifier)
            for curve in layer.ops.curves(copy,ad.action_slot):
                if curve.data_path == 'location': curve.keyframe_points.clear()
            for frame,location in rows:
                clone.location = location; clone.keyframe_insert('location',frame=frame)
            for curve in layer.ops.curves(copy,ad.action_slot):
                if curve.data_path == 'location': sm.smooth_keys(curve)
            report = {'source':action.name,'source_sha256':clip['source_sha256'],'result':copy.name,
                      'contacts':contacts,'placement_delta_m':travel,'ground_z_m':profile['ground_z'],
                      'provenance':'explicitly reviewed sole vertices and core stance intervals; not inferred source annotations',
                      'bone_curves':'UNCHANGED','timing':'UNCHANGED','quality':'REQUIRES_REOPEN_CONTACT_AND_VISUAL_VALIDATION'}
            copy['bad_root_contact_preparation_v1'] = json.dumps(report,sort_keys=True)
            reports.append((report,copy,ad.action_slot,start,end))
        for report,copy,slot,start,end in reports:
            track = layer.add_strip(obj,copy,slot,'Prepared root path '+copy.name,start,[start,end],1.)
            track.mute = True; tracks.append(track)
        from .native_motion_basis import extend_prepared_sources
        extend_prepared_sources(obj,reader.native_basis,[(row[1],row[2]) for row in reports])
        return [r[0] for r in reports]
    except Exception:
        reader.clone.animation_data_clear()
        for track in tracks: obj.animation_data.nla_tracks.remove(track)
        for action in created: bpy.data.actions.remove(action,do_unlink=True)
        if original_timeline is not None: obj['bad_action_timeline_v1']=original_timeline
        raise
    finally:
        if soles: soles.close()
        reader.close()
