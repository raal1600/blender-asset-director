/** Actual independent loopback servers; no GUI or external process certification. */
import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import {listenPort} from '../lib/listen-port.mjs';

test('legacy default, explicit port and ephemeral staging port remain distinct',()=>{
  assert.equal(listenPort({}),48731);assert.equal(listenPort({port:0}),0);assert.equal(listenPort({port:51234}),51234);
  for(const port of [-1,65536,3.5,'0',true,{},NaN])assert.throws(()=>listenPort({port}),/integer/);
});
test('two simultaneous staging listeners do not collide or expose non-loopback sockets',async t=>{
  const servers=[http.createServer((q,r)=>r.end('stage one')),http.createServer((q,r)=>r.end('stage two'))];
  t.after(async()=>{await Promise.all(servers.map(s=>new Promise(resolve=>s.close(resolve))));});
  for(const server of servers)await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(listenPort({port:0}),'127.0.0.1',resolve);});
  assert.notEqual(servers[0].address().port,servers[1].address().port);
  for(const server of servers)assert.equal(server.address().address,'127.0.0.1');
  assert.equal(await (await fetch(`http://127.0.0.1:${servers[0].address().port}`)).text(),'stage one');
  assert.equal(await (await fetch(`http://127.0.0.1:${servers[1].address().port}`)).text(),'stage two');
});
test('source startup has one workbench and no legacy UI switch',async()=>{
  // Static contract only. Windows build and native desktop behavior are separate gates.
  const native=await fs.readFile(new URL('../tools/AssetDirectorLauncher.cs',import.meta.url),'utf8');
  const shortcut=await fs.readFile(new URL('../Start Launcher.ps1',import.meta.url),'utf8');
  const server=await fs.readFile(new URL('../server.mjs',import.meta.url),'utf8');
  assert.ok(native.includes('view.Source=new Uri(origin+"/workbench#"+token);'));
  assert.ok(shortcut.includes("$page = '/workbench#'"));assert.ok(!shortcut.includes('$Legacy'));
  assert.ok(server.includes('port:listenPort(config)'));
});
