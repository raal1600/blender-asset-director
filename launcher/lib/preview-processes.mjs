/** Read-only process ownership. Raw command lines never leave this helper. */
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const exec=promisify(execFile);
export async function previewUsers(directories,{run=exec,platform=process.platform}={}){
 let rows,reason='QUERY_FAILED';
 try{
  if(platform==='win32'){
   const ps=path.join(process.env.SystemRoot||'C:/Windows','System32/WindowsPowerShell/v1.0/powershell.exe');
   const filter=JSON.stringify("Name='blender.exe' OR Name='blender-launcher.exe'");
   const script='@(Get-CimInstance Win32_Process -Filter '+filter+' -ErrorAction Stop | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress';
   const {stdout}=await run(ps,['-NoProfile','-NonInteractive','-Command',script],{timeout:30000,maxBuffer:4*1024*1024,windowsHide:true});
   reason='INVALID_PROCESS_RESPONSE';
   const data=JSON.parse(stdout.trim()||'[]');rows=Array.isArray(data)?data:[data];
  }else{
   let stdout;try{({stdout}=await run('/bin/ps',['-C','blender','-o','pid=,args='],{timeout:30000,maxBuffer:4*1024*1024}));}catch(e){if(e.code===1&&!e.stdout)return [];throw e;}
   rows=stdout.split(/\r?\n/).filter(Boolean).map(line=>{const m=line.trim().match(/^(\d+)\s+(.*)$/);if(!m)throw Error('Unknown process');return {ProcessId:Number(m[1]),CommandLine:m[2]};});
  }
  reason='UNREADABLE_PROCESS';
  if(rows.some(row=>!Number.isInteger(row?.ProcessId)||row.ProcessId<=0||typeof row.CommandLine!=='string'||!row.CommandLine.trim()))throw Error('Unknown native process');
 }catch(error){throw Object.assign(new Error('Could not verify native preview users ('+(error.killed?'QUERY_TIMEOUT':reason)+'). Nothing was removed; retry after inspecting Blender.'),{status:409,code:'NATIVE_PREVIEW_STATE_UNKNOWN'});}
 const normalize=value=>String(value||'').split(String.fromCharCode(92)).join('/').toLowerCase();
 return directories.flatMap(({previewId,directory})=>rows.filter(row=>normalize(row.CommandLine).includes(normalize(directory))).map(row=>({previewId,processId:row.ProcessId})));
}
