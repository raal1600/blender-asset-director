"""Blender-only original character/action playback, not retargeting or gait editing."""
import math
from pathlib import Path
import bpy
from .core import require
from . import blender_ops as ops
from .motion_morph import inclusive_scene_end
from .motion_timing import number


def import_native(lib, asset):
    require(bpy.app.background and not bpy.data.objects,'SOURCE_ONLY_OPERATION','Native pairing requires an empty isolated scene')
    meta=asset.metadata; f=meta.get('file')
    require(f and meta.get('action') and meta.get('source_object') and meta.get('fps'),
            'INDEX_REQUIRED','Use an indexed clip, not a guessed action name')
    require(f in asset.local_files,'INDEX_SOURCE_MISMATCH','Clip source is outside the asset')
    fps=meta['fps']; require(number(fps,1,240),'INVALID_TIMING','Invalid indexed FPS')
    sc=bpy.context.scene;sc.render.fps=int(fps);sc.render.fps_base=int(fps)/fps
    path=lib.verify_file(f)
    require(path.suffix.lower() in {'.fbx','.bvh','.glb','.gltf'},'FORMAT_UNSUPPORTED','Native pairing needs an interchange animation')
    created=ops.import_file(path,path.parent,frame_fps=fps)
    candidates=[b for b in ops.clip_bindings(created)[0] if b[0].name==meta['source_object'] and b[1].name==meta['action']
                and (b[2].identifier if b[2] else None)==meta.get('slot')]
    require(len(candidates)==1,'ACTION_AMBIGUOUS','Imported character/action/slot differs from index')
    obj,action,slot,start,end,evidence=candidates[0]
    require(abs(sc.render.fps/sc.render.fps_base-fps)<1e-5 and abs(start-meta['frame_start'])<1e-4
            and abs(end-meta['frame_end'])<1e-4,'SOURCE_TIMEBASE_MISMATCH','Reimport changed observed timing')
    ops.assign(obj,action,slot.identifier if slot else None)
    for track in obj.animation_data.nla_tracks:track.mute=True
    sc.frame_start=math.floor(start);sc.frame_end,exact=inclusive_scene_end(start,(end-start)/fps,fps)
    sc.frame_set(sc.frame_start)
    return {'source':asset.id,'source_object':obj.name,'action':action.name,'slot':slot.identifier if slot else None,
            'ownership_evidence':evidence,'fps':fps,'frame_range':[start,end],'duration_seconds':(end-start)/fps,
            'scene_frame_range':[sc.frame_start,sc.frame_end],'final_key_frame':exact,
            'objects':[o.name for o in created],'rig':ops.rig_report(obj),'retargeted':False,'motion_edited':False,
            'loop_behavior':'NOT_ESTABLISHED','performance':'PENDING_CONTINUOUS_REVIEW'}
