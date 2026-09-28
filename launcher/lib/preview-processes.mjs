/** Read-only process ownership. Raw command lines never leave this helper. */
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const exec=promisify(execFile);
export async function previewUsers(directories){
 let rows;
 try{
  if(process.platform==='win32'){
   const ps=path.join(process.env.SystemRoot||'C:/Windows','System32/WindowsPowerShell/v1.0/powershell.exe');
   const script="@(Get-CimInstance Win32_Process | Where-Object Name -in @('blender.exe','blender-launcher.exe') | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress";
   const {stdout}=await exec(ps,['-NoProfile','-NonInteractive','-Command',script],{timeout:10000,maxBuffer:4*1024*1024,windowsHide:true});
   const data=JSON.parse(stdout||'[]');rows=Array.isArray(data)?data:[data];
  }else{
   let stdout;try{({stdout}=await exec('/bin/ps',['-C','blender','-o','pid=,args='],{timeout:10000,maxBuffer:4*1024*1024}));}catch(e){if(e.code===1&&!e.stdout)return [];throw e;}
   rows=stdout.split(/\r?\n/).filter(Boolean).map(line=>{const m=line.trim().match(/^(\d+)\s+(.*)$/);if(!m)throw Error('Unknown process');return {ProcessId:Number(m[1]),CommandLine:m[2]};});
  }
  if(rows.some(row=>typeof row.CommandLine!=='string'||!row.CommandLine.trim()))throw Error('Unknown native command line');
 }catch{throw new Error('Could not verify native preview users. Nothing was removed.');}
 const normalize=value=>String(value||'').split(String.fromCharCode(92)).join('/').toLowerCase();
 return directories.flatMap(({previewId,directory})=>rows.filter(row=>normalize(row.CommandLine).includes(normalize(directory))).map(row=>({previewId,processId:row.ProcessId})));
}
