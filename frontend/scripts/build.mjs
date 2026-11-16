// Scope esbuild scratch files to this build on Windows; never change OS ACLs.
import {mkdir,mkdtemp,rm} from 'node:fs/promises';
import {resolve,join} from 'node:path';
let scratch;
try {
 if(process.platform==='win32'){
  const cache=resolve('node_modules/.cache');await mkdir(cache,{recursive:true});
  scratch=await mkdtemp(join(cache,'companion-esbuild-'));
  process.env.TMP=scratch;process.env.TEMP=scratch;process.env.TMPDIR=scratch;
 }
 const {build}=await import('vite');await build();
} catch(error){console.error(error);process.exitCode=1;} finally {
 // Only the unique directory created by this invocation is ever removed.
 if(scratch)await rm(scratch,{recursive:true,force:true});
}
