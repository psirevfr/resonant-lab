import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {rmSync} from 'node:fs';
await build({absWorkingDir:process.cwd(),entryPoints:['src/audioDsp.ts','src/computeEngine.ts','src/requestDeadline.ts'],bundle:true,platform:'node',format:'esm',outdir:'.test-build',outExtension:{'.js':'.mjs'}});
try{const result=spawnSync(process.execPath,['--test','tests/audio.test.mjs','tests/compute-engine.test.mjs'],{stdio:'inherit'});process.exitCode=result.status??1}finally{rmSync('.test-build',{recursive:true,force:true})}
