import test from 'node:test';
import assert from 'node:assert/strict';
import {productionRow,archiveTarget,archiveConfirmation} from '../public/workbench-studio.mjs';
const esc=v=>String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
test('production list exposes separate open and recoverable archive actions for the exact row',()=>{
  const calls=[],project={id:'prj_one',name:'World <one>',brief:'A & B',workbench:{scenes:[{}]}};
  const b=(label,action,data)=>{calls.push({label,action,data});return '<button>'+esc(label)+'</button>';};
  const html=productionRow({project,esc,b});
  assert.match(html,/data-production-id="prj_one"/);
  assert.match(html,/World &lt;one&gt;/);assert.match(html,/A &amp; B/);
  assert.match(html,/1 workbench scenes/);assert.ok(!html.includes('World <one>'));
  assert.deepEqual(calls.map(c=>[c.action,c.data.id]),[['project','prj_one'],['archive-production','prj_one']]);
  assert.ok(!calls.some(c=>/delete/i.test(c.label)));
});
test('archive target uses the chosen list row and its displayed revision, never another open production',()=>{
  const current={id:'prj_open',revision:4},chosen={id:'prj_chosen',revision:9};
  assert.equal(archiveTarget({projects:[current,chosen],current,id:chosen.id}),chosen);
  assert.equal(archiveTarget({projects:[current,chosen],current}),current);
  for(const id of ['missing','',null])assert.throws(()=>archiveTarget({projects:[current],current,id}),/no longer listed/);
  assert.throws(()=>archiveTarget({projects:[],current:null}),/no longer listed/);
  assert.equal(chosen.revision,9);
});
test('archive confirmation names the production and explains preservation and restoration',()=>{
  const text=archiveConfirmation({name:'Test production'});
  assert.match(text,/Archive "Test production"/);
  assert.match(text,/scenes, renders and history/);assert.match(text,/Shared library assets stay in place/);
  assert.match(text,/Restore it from Archived productions/);assert.match(text,/not permanent deletion/);
});
