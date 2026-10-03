export type Parameters = Record<string, number>;
export interface Block {id:string; type:string; label:string; parameters:Parameters; position:{x:number;y:number}; reason:string}
export interface Edge {id:string;source:string;target:string}
export interface Patch {version:1;name:string;sample_rate:number;duration:number;nodes:Block[];edges:Edge[]}
export interface Parameter {default:number;minimum:number;maximum:number;unit:string;label:string}
export interface Definition {label:string;category:string;inputs:number;parameters:Record<string,Parameter>;equation:string;description:string;lti:boolean}
export type Catalog = Record<string,Definition>;
export interface SignalView {time:number[];wave:number[];envelope_time:number[];envelope:number[];frequency:number[];spectrum:number[];spectrogram:{time:number[];frequency:number[];db:number[][]};peak:number;rms:number;duration:number}
export interface AudioData {id:string;metadata:{name:string;sample_rate:number;channels:number;duration:number;subtype:string;peak:number;rms:number;frames:number};view:SignalView}
export type Weights = {time:number;spectral:number;spectrogram:number;envelope:number;attack:number};
export type Errors = Weights & {total:number};
export interface RenderResult {id:string;view:SignalView;reference:SignalView|null;difference:SignalView|null;errors:Errors|null;clipping:boolean;sample_rate:number}
export interface Analysis {f0:number|null;partials:{frequency:number;amplitude:number;phase:number;tau:number;decay_r2:number|null;harmonic?:number}[];onset:number;attack:number;inharmonicity:null|{B:number;f0_ideal:number;rmse_hz:number;count:number;method:string};envelope:{time:number[];amplitude:number[]};autocorrelation:{lag:number[];value:number[]};warnings:string[];method:string}
export interface Bode {frequency:number[];magnitude:number[];phase:number[];description:string}
export interface Transfer extends Partial<Bode> {lti:boolean;equation:string;digital?:string;order?:number;stable?:boolean;dc_gain?:number;poles?:{real:number;imag:number;multiplicity?:number}[];zeros?:{real:number;imag:number}[];impulse_time?:number[];impulse?:number[];description:string}
export interface Candidate {patch:Patch;errors:Errors;complexity:number;score:number;generators?:number;parameter_count?:number;modules?:number;rejection_reasons?:string[];bands?:Record<string,number>;pareto?:boolean;within_tolerance?:boolean;reference?:boolean}
export interface Generation {analysis:Analysis;patch:Patch;candidates:Candidate[];selection:string;penalty:number}
export interface Optimization {patch:Patch;initial:number;final:number;history:number[];evaluations:number;converged:boolean;message:string;parameters:string[]}
export interface Job {status:string;progress:{initial?:number;current?:number;best?:number;evaluations?:number;budget?:number;history?:number[];parameters?:string[]};result?:Optimization;error?:string}

export interface CompactResult {patch:Patch;original:Patch;candidates:Candidate[];baseline:number;limit:number;tolerance:number;final:number;original_blocks:number;final_blocks:number;original_generators:number;final_generators:number;reverted:boolean;utilities:{block_id:string;label:string;error_increase_without:number}[];selection:string;shaping_tested:boolean;protect_texture?:boolean;reference_bands?:Record<string,number>;final_bands?:Record<string,number>;processing_diagnostics?:{architecture:string;full_rate_error:number;blocks:number;sources:number;analysis_rate:number}[]}
