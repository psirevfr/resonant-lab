import type {Analysis,Patch} from '../types';

export interface FirmwareModel {
  code:string;
  prompt:string;
  partialCount:number;
  referenceMidi:number;
  limitations:string[];
}

type Mode={frequency:number;amplitude:number;tau:number;phase:number};

const f=(value:number)=>Number.isFinite(value)?Number(value).toPrecision(9)+'f':'0.0f';

function modelModes(patch:Patch,analysis:Analysis|null):Mode[]{
 if(analysis?.partials.length){
  return analysis.partials.slice(0,24).filter(p=>Number.isFinite(p.frequency)&&p.frequency>0&&Number.isFinite(p.amplitude)&&Number.isFinite(p.tau)&&p.tau>0).map(p=>({frequency:p.frequency,amplitude:Math.abs(p.amplitude),tau:p.tau,phase:Number.isFinite(p.phase)?p.phase:0}));
 }
 return patch.nodes.filter(n=>n.type==='oscillator'&&Number.isFinite(n.parameters.frequency)&&n.parameters.frequency>0).slice(0,24).map(n=>({frequency:n.parameters.frequency,amplitude:Math.abs(n.parameters.amplitude??.2),tau:Math.max(.001,n.parameters.tau??1),phase:n.parameters.phase??0}));
}

export function buildTeensySketch(patch:Patch,analysis:Analysis|null):FirmwareModel{
 const modes=modelModes(patch,analysis);
 const safeModes=modes.length?modes:[{frequency:0,amplitude:0,tau:1,phase:0}];
 const f0=analysis?.f0&&Number.isFinite(analysis.f0)&&analysis.f0>0?analysis.f0:modes[0]?.frequency??440;
 const referenceMidi=Math.max(21,Math.min(108,Math.round(69+12*Math.log2(f0/440))));
 const attack=analysis&&Number.isFinite(analysis.attack)?Math.max(0,analysis.attack):patch.nodes.find(n=>n.type==='envelope'||n.type==='adsr')?.parameters.attack??.005;
 const releaseBlock=patch.nodes.find(n=>n.type==='adsr');
 const release=releaseBlock?.parameters.release;
 const releaseSeconds=Number.isFinite(release)&&release!>0?release!:.2;
 const patchTypes=new Set(patch.nodes.map(n=>n.type));
 const limitations:string[]=[];
 if(!analysis)limitations.push('Pas de résultat d’analyse : les sinusoïdes viennent seulement des oscillateurs du patch.');
 if(patch.sample_rate!==44100)limitations.push('Le moteur Teensy Audio sort à 44,1 kHz; la fréquence d’échantillonnage du patch ('+patch.sample_rate+' Hz) n’est pas conservée.');
 if(!releaseBlock||!Number.isFinite(release)||release!<=0)limitations.push('Aucun relâchement MIDI n’a été identifié; le sketch utilise une décroissance de secours de 200 ms après Note Off.');
 if(['noise','impulse'].some(t=>patchTypes.has(t)))limitations.push('Le bruit et les impacts ne sont pas traduits par ce prototype de banque sinusoïdale.');
 if(['saturation','asymmetric_saturation','lowpass','highpass','bandpass','notch','peak_eq','lowpass1','resonator','delay','multiply','gain'].some(t=>patchTypes.has(t)))limitations.push('Les effets, filtres et routages du patch ne sont pas encore portés comme traitements embarqués indépendants.');
 limitations.push('La transposition MIDI applique un rapport tempéré à tous les modes; la dispersion inharmonique propre à chaque note n’est pas mesurée.');
 limitations.push('Sortie Teensy Audio en 16 bits / 44,1 kHz; comparer le signal matériel avant de parler d’équivalence au moteur Float64 du navigateur.');

 const partials=safeModes.map(m=>'{ '+f(m.frequency)+', '+f(m.amplitude)+', '+f(m.tau)+', '+f(m.phase/(Math.PI*2))+' }').join(',\n  ');
 const code=[
 '// Resonant Lab — esquisse Arduino pour Teensy 4.1',
 '// Une banque logicielle additive remplace les générateurs matériels séparés.',
 '// Cible : Arduino IDE + Teensyduino, Teensy 4.1, Audio Shield Rev D/D2, USB MIDI Host.',
 '// Ce prototype ne porte pas encore les filtres, saturations ni le bruit du patch.',
 '#include <Audio.h>',
 '#include <USBHost_t36.h>',
 '#include <math.h>',
 '',
 'static const uint32_t kSampleRate = 44100;',
 'static const uint16_t kTableSize = 1024;',
 'static const uint8_t kVoiceCount = 8;',
 'static const uint8_t kPartialCount = '+safeModes.length+';',
 'static const uint8_t kReferenceMidi = '+referenceMidi+';',
 'static const float kAttackSeconds = '+f(attack)+';',
 'static const float kReleaseSeconds = '+f(releaseSeconds)+';',
 'static const float kPartialData[][4] = {',
 '  // fréquence Hz, amplitude relative, tau de décroissance s, phase en cycles',
 '  '+partials,
 '};',
 '',
 'float sineTable[kTableSize];',
 'USBHost usbHost;',
 'MIDIDevice_BigBuffer usbMidi(usbHost);',
 '',
 'class ResonantAdditiveBank : public AudioStream {',
 '  struct Voice { bool active=false; bool released=false; uint8_t note=0; uint32_t age=0; float velocity=0; float pitch=1; float attack=0; float release=1; float phase[kPartialCount]{}; float decay[kPartialCount]{}; };',
 '  Voice voices[kVoiceCount]; float decayStep[kPartialCount]; uint32_t serial=0; float releaseStep=1; float norm=1;',
 'public:',
 '  ResonantAdditiveBank() : AudioStream(0, nullptr) {}',
 '  void begin() {',
 '    for (uint16_t i=0;i<kTableSize;i++) sineTable[i]=sinf(6.28318530718f*(float)i/(float)kTableSize);',
 '    float sum=0; for(uint8_t p=0;p<kPartialCount;p++) sum+=fabsf(kPartialData[p][1]);',
 '    norm=sum>0 ? 0.82f/sum : 0.0f;',
 '    for(uint8_t p=0;p<kPartialCount;p++){const float tau=fmaxf(kPartialData[p][2],0.0001f);decayStep[p]=expf(-1.0f/(tau*(float)kSampleRate));}',
 '    const float r=fmaxf(kReleaseSeconds,0.005f); releaseStep=expf(-1.0f/(r*(float)kSampleRate));',
 '  }',
 '  void noteOn(uint8_t note,uint8_t velocity) {',
 '    Voice *v=nullptr; for(uint8_t i=0;i<kVoiceCount;i++) if(voices[i].active&&voices[i].note==note){v=&voices[i];break;}',
 '    if(!v) for(uint8_t i=0;i<kVoiceCount;i++) if(!voices[i].active){v=&voices[i];break;}',
 '    if(!v){v=&voices[0];for(uint8_t i=1;i<kVoiceCount;i++) if(voices[i].age<v->age) v=&voices[i];}',
 '    v->active=true;v->released=false;v->note=note;v->age=++serial;v->pitch=powf(2.0f,((int)note-(int)kReferenceMidi)/12.0f);v->velocity=powf((float)velocity/127.0f,1.5f);v->attack=0;v->release=1;',
 '    for(uint8_t p=0;p<kPartialCount;p++){v->phase[p]=kPartialData[p][3];v->phase[p]-=floorf(v->phase[p]);v->decay[p]=1.0f;}',
 '  }',
 '  void noteOff(uint8_t note) { for(uint8_t i=0;i<kVoiceCount;i++) if(voices[i].active&&voices[i].note==note) voices[i].released=true; }',
 '  void update() override {',
 '    audio_block_t *block=allocate(); if(!block)return;',
 '    const float attackStep=kAttackSeconds>0 ? 1.0f/(kAttackSeconds*(float)kSampleRate) : 1.0f;',
 '    for(uint16_t n=0;n<AUDIO_BLOCK_SAMPLES;n++){',
 '      float mix=0.0f;uint8_t activeVoices=0;',
 '      for(uint8_t vIndex=0;vIndex<kVoiceCount;vIndex++){Voice &v=voices[vIndex];if(!v.active)continue;',
 '        if(v.released){v.release*=releaseStep;if(v.release<0.0001f){v.active=false;continue;}}else if(v.attack<1.0f){v.attack=fminf(1.0f,v.attack+attackStep);}',
 '        activeVoices++;',
 '        for(uint8_t p=0;p<kPartialCount;p++){const float hz=kPartialData[p][0]*v.pitch;if(hz<=0.0f||hz>=0.49f*(float)kSampleRate)continue;',
 '          const float x=v.phase[p]*(float)kTableSize;const uint16_t i=(uint16_t)x;const float frac=x-(float)i;',
 '          const float s=sineTable[i]*(1.0f-frac)+sineTable[(i+1)&(kTableSize-1)]*frac;',
 '          mix+=s*kPartialData[p][1]*v.decay[p]*v.attack*v.release*v.velocity*norm;',
 '          v.phase[p]+=hz/(float)kSampleRate;if(v.phase[p]>=1.0f)v.phase[p]-=1.0f;',
 '          v.decay[p]*=decayStep[p];',
 '        }',
 '      }',
 '      if(activeVoices)mix/=(float)activeVoices;mix=fmaxf(-0.98f,fminf(0.98f,mix));block->data[n]=(int16_t)lrintf(mix*32767.0f);',
 '    }',
 '    transmit(block);release(block);',
 '  }',
 '};',
 '',
 'ResonantAdditiveBank synth;',
 'AudioControlSGTL5000 audioControl;',
 'AudioOutputI2S i2sOut;',
 'AudioConnection leftLink(synth,0,i2sOut,0);',
 'AudioConnection rightLink(synth,0,i2sOut,1);',
 '',
 'void onNoteOn(byte channel,byte note,byte velocity);',
 'void onNoteOff(byte channel,byte note,byte velocity);',
 'void onNoteOn(byte channel,byte note,byte velocity){(void)channel;if(!velocity){onNoteOff(channel,note,0);return;}AudioNoInterrupts();synth.noteOn(note,velocity);AudioInterrupts();}',
 'void onNoteOff(byte channel,byte note,byte velocity){(void)channel;(void)velocity;AudioNoInterrupts();synth.noteOff(note);AudioInterrupts();}',
 '',
 'void setup(){',
 '  AudioMemory(16);',
 '  synth.begin();',
 '  audioControl.enable();',
 '  audioControl.volume(0.30f); // niveau casque prudent au premier branchement',
 '  usbHost.begin();',
 '  usbMidi.setHandleNoteOn(onNoteOn);',
 '  usbMidi.setHandleNoteOff(onNoteOff);',
 '}',
 'void loop(){usbHost.Task();usbMidi.read();}',
 ''
 ].join('\n');
 const measured=analysis?.partials.length?analysis.partials.slice(0,safeModes.length).map((p,i)=>`${i+1}. ${p.frequency.toFixed(2)} Hz · A ${p.amplitude.toFixed(4)} · τ ${p.tau.toFixed(3)} s`).join('\n'):'Aucune mesure disponible; le sketch reprend les oscillateurs présents dans le patch.';
 const prompt='Construis un synthétiseur mono à partir de ce firmware Arduino existant. Garde le matériel minimal : Teensy 4.1 programmée avec Arduino IDE/Teensyduino, Audio Shield Rev D ou D2 (SGTL5000) empilé sur la Teensy, une breadboard, les connexions indispensables et un clavier MIDI USB sur le port Host. Le shield regroupe codec audio et prise casque/ligne : ne rajoute pas de DAC ni de breakout jack séparé. N’ajoute pas de générateur matériel par partiel : les sinusoïdes sont additionnées dans le firmware. L’I²S et le contrôle I²C passent par les headers empilés (DIN 7, BCLK 21, LRCLK 20, MCLK 23, SDA/SCL 18/19); sépare clairement le câble USB Host et le câble USB de programmation. Montre le montage 3D, le schéma, le brochage et la nomenclature. Ne prétends pas que la simulation valide le son tant que ce sketch n’est pas compilé et testé sur le matériel.\n\nPatch : '+patch.name+'\nNote de référence MIDI estimée : '+referenceMidi+'\nÉchantillonnage du patch d’origine : '+patch.sample_rate+' Hz\nPartiels employés : '+safeModes.length+'\n'+measured+'\n\nGarde en évidence les limites suivantes : Audio Library Teensy à 16 bits/44,1 kHz, filtres/saturations/bruit du patch non encore portés et transposition égale des fréquences des partiels.';
 return {code,prompt,partialCount:modes.length,referenceMidi,limitations};
}
