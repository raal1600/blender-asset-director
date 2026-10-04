import test from 'node:test';
import assert from 'node:assert/strict';
import {actionPathPoints} from '../public/viewer-3d.mjs';
test('selected path framing preserves world metre conversion and leaves the draft unchanged',()=>{
 const p={origin_m:[1,2,3],delta_m:[-5,20],meters_per_unit:.5},before=structuredClone(p);
 assert.deepEqual(actionPathPoints(p),[[2,6,-4],[-8,6,-44]]);assert.deepEqual(p,before);
});
test('ordinary viewers and incomplete draft geometry add no path framing points',()=>{
 for(const p of [null,undefined,{}, {origin_m:[0,0,0],delta_m:[1,2],meters_per_unit:0},
  {origin_m:[0,0,NaN],delta_m:[1,2],meters_per_unit:1}])assert.deepEqual(actionPathPoints(p),[]);
});
