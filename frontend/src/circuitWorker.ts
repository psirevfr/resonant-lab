import create from '@o.z/ngspice-wasm';
import {runWasm} from './circuitEngine';
self.onmessage=async e=>{try{self.postMessage({result:await runWasm(create,e.data)})}catch(error){self.postMessage({error:error instanceof Error?error.message:'Erreur de simulation locale.'})}};
