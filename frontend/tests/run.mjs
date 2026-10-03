import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {rmSync} from 'node:fs';
await build({entryPoints:['src/audioDsp.ts'],bundle:true,platform:'node',format:'esm',outfile:'.test-build/audioDsp.mjs'});
try{const result=spawnSync(process.execPath,['--test','tests/audio.test.mjs'],{stdio:'inherit'});process.exitCode=result.status??1}finally{rmSync('.test-build',{recursive:true,force:true})}
