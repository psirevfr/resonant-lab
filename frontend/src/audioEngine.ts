// frontend/src/audioEngine.ts

export async function renderPatchClientSide(patch: any) {
    const sampleRate = patch.sample_rate || 44100;
    const duration = patch.duration || 3.0;
    const numSamples = Math.round(duration * sampleRate);
    
    // Création d'un buffer audio en RAM du navigateur
    const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate });
    const buffer = audioCtx.createBuffer(1, numSamples, sampleRate);
    const channelData = buffer.getChannelData(0);

    // Simulation du signal (boucle mathématique sur les nœuds du patch)
    for (let i = 0; i < numSamples; i++) {
        const t = i / sampleRate;
        let sample = 0;
        
        if (patch.nodes) {
            patch.nodes.forEach((node: any) => {
                // Remplacement de la logique serveur : on calcule les sinusoïdes/modes ici
                const freq = node.parameters?.frequency || (node.parameters?.f || 440);
                const gain = node.parameters?.gain || (node.parameters?.a || 0.1);
                const decay = node.parameters?.decay || (node.parameters?.tau || 1.0);
                
                // Exemple de synthèse basique (à adapter si tu as des formules plus complexes)
                sample += gain * Math.exp(-t / decay) * Math.sin(2 * Math.PI * freq * t);
            });
        }
        channelData[i] = sample; // Remplissage de l'échantillon
    }

    return bufferToWavBlob(buffer);
}

// Fonction de conversion standard en fichier WAV (Float32 / Int16)
function bufferToWavBlob(buffer: AudioBuffer): Blob {
    const numOfChan = buffer.numberOfChannels;
    const length = buffer.length * numOfChan * 2 + 44;
    const out = new DataView(new ArrayBuffer(length));
    let channels = [];
    let sampleRate = buffer.sampleRate;
    let offset = 0;
    let pos = 0;

    function writeString(str: string) {
        for (let i = 0; i < str.length; i++) {
            out.setUint8(pos++, str.charCodeAt(i));
        }
    }

    writeString('RIFF');
    out.setUint32(pos, length - 8, true); pos += 4;
    writeString('WAVE');
    writeString('fmt ');
    out.setUint32(pos, 16, true); pos += 4;
    out.setUint16(pos, 1, true); pos += 2;
    out.setUint16(pos, numOfChan, true); pos += 2;
    out.setUint32(pos, sampleRate, true); pos += 4;
    out.setUint32(pos, sampleRate * 2 * numOfChan, true); pos += 4;
    out.setUint16(pos, numOfChan * 2, true); pos += 2;
    out.setUint16(pos, 16, true); pos += 2;
    writeString('data');
    out.setUint32(pos, length - pos - 4, true); pos += 4;

    for (let i = 0; i < buffer.numberOfChannels; i++) {
        channels.push(buffer.getChannelData(i));
    }

    while (pos < length) {
        for (let i = 0; i < numOfChan; i++) {
            let sample = Math.max(-1, Math.min(1, channels[i][offset]));
            sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0;
            out.setInt16(pos, sample, true);
            pos += 2;
        }
        offset++;
    }

    return new Blob([out.buffer], { type: 'audio/wav' });
}