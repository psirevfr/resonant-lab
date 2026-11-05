import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {rmSync} from 'node:fs';
await build({absWorkingDir:process.cwd(),entryPoints:['src/audioDsp.ts','src/computeEngine.ts','src/requestDeadline.ts','src/circuitEngine.ts','src/circuitClient.ts','src/circuitProject.ts','src/circuitConnectivity.ts','src/schematicModel.ts','src/schematicLayout.ts','src/cableInteraction.ts','src/physicalLayout.ts','src/hardwareCatalog.ts','src/electronics/partModels.ts','src/musicalEvents.ts','src/instrumentLocal.ts','src/firmware/teensySketch.ts'],bundle:true,platform:'node',format:'esm',outdir:'.test-build',outExtension:{'.js':'.mjs'}});
try{const result=spawnSync(process.execPath,['--test','tests/audio.test.mjs','tests/compute-engine.test.mjs','tests/workshop.test.mjs','tests/schematic.test.mjs'],{stdio:'inherit'});process.exitCode=result.status??1}finally{rmSync('.test-build',{recursive:true,force:true})}
