"""Frequency-band diagnostics and a bounded white-noise texture branch."""
import numpy as np
from .schema import Block
from .blocks import process
from .identify import link
from .graph import render


def band_errors(x,y,fs):
    # Integrate magnitudes over short frames: high-band energy cannot disappear
    # merely because bass dominates the full-band squared norm.
    from .audio import stft
    f,_,a=stft(x,fs,nfft=1024,max_frames=80);_,_,b=stft(y,fs,nfft=1024,max_frames=80)
    result={};floor=max(float(np.linalg.norm(a))*.003,1e-12)
    for lo,hi,name in [(0,500,'grave'),(500,2000,'medium'),(2000,6000,'presence'),(6000,fs/2+1,'aigu')]:
        mask=(f>=lo)&(f<hi)
        result[name]=float(np.linalg.norm(a[mask]-b[mask])/max(np.linalg.norm(a[mask]),floor))
    return result


def fit_texture(base,x,objective):
    fs=base.sample_rate;n=len(x);tonal=render(base)
    onset=min((b.parameters.get('onset',0) for b in base.nodes if b.type=='modal'),default=0)
    noise=process('noise',{'amplitude':1,'seed':42},[],fs,n)
    best=(float('inf'),None)
    from .blocks import parameters
    for hp in (600,2200,6000):
        high=process('highpass',{'fc':hp,'q':.707},[noise],fs,n)
        for lp in (6000,min(18000,fs*.45)):
            if lp<=hp:continue
            filtered=process('lowpass',{'fc':lp,'q':.707},[high],fs,n)
            target=process('lowpass',{'fc':lp,'q':.707},[process('highpass',{'fc':hp,'q':.707},[x-tonal],fs,n)],fs,n)
            for tau in (.025,.12,.5):
                burst=process('envelope',{'attack':.001,'tau':tau,'onset':onset},[filtered],fs,n)
                scale=float(np.linalg.norm(target)/max(np.linalg.norm(burst),1e-12))
                for amount in (.25,.65):
                    amp=min(4,scale*amount);y=tonal+amp*burst;error=objective(y)
                    # Band score is part of the proposal only; acceptance uses
                    # original full cost and optional band constraints later.
                    score=error+.08*sum(band_errors(x,y,fs).values())
                    if score<best[0]:best=(score,(hp,lp,tau,amp))
    if best[1] is None:return None
    hp,lp,tau,amp=best[1];p=base.model_copy(deep=True)
    out=next(b.id for b in p.nodes if b.type=='output');parent=next(e.source for e in p.edges if e.target==out)
    p.edges=[e for e in p.edges if e.target!=out]
    chain=[('texture-noise','noise',{'amplitude':1,'seed':42},'Texture · bruit blanc'),('texture-hp','highpass',{'fc':hp,'q':.707},'Texture · passe-haut'),('texture-lp','lowpass',{'fc':lp,'q':.707},'Texture · passe-bas'),('texture-env','envelope',{'attack':.001,'tau':tau,'onset':onset},'Texture · enveloppe'),('texture-vca','gain',{'gain':amp},'Texture · amplification')]
    for i,(id,kind,params,label) in enumerate(chain):
        p.nodes.append(Block(id=id,type=kind,parameters=params,label=label,position={'x':i*250,'y':800},reason='Bruit blanc synthétique de graine 42, filtré et enveloppé ; amplification explicite. Ajustement sur résidu et erreurs par bandes, sans rejouer le WAV.'))
        if i:p.edges.append(link(chain[i-1][0],id))
    p.nodes.append(Block(id='texture-mix',type='sum',label='Tonal + texture'))
    p.edges.extend([link(parent,'texture-mix'),link(chain[-1][0],'texture-mix'),link('texture-mix',out)])
    p.name+=' · texture filtrée';return p


def search_texture(base,x,objective):
    """Try explicit noise branches without a redundant fixed-gain block.

    Source amplitude is its standard deviation, not a hidden amplifier. A real
    noise generator/amplifier still needs a separate electrical design.
    """
    fs=base.sample_rate;n=len(x);tonal=render(base);residual=x-tonal
    if np.linalg.norm(residual)<=max(np.linalg.norm(x),1e-12)*1e-9:return [],[]
    onset=min((b.parameters.get('onset',0) for b in base.nodes if b.type in ('modal','envelope')),default=0)
    noise=process('noise',{'amplitude':1,'seed':42},[],fs,n)
    baseline=objective(tonal)+.08*sum(band_errors(x,tonal,fs).values())
    families={}
    def trial(name,filters):
        filtered=noise;target=residual
        for kind,params in filters:
            filtered=process(kind,params,[filtered],fs,n)
            target=process(kind,params,[target],fs,n)
        for tau in (.025,.12,.5):
            burst=process('envelope',{'attack':.001,'tau':tau,'onset':onset},[filtered],fs,n)
            scale=min(4,float(np.linalg.norm(target)/max(np.linalg.norm(burst),1e-12)))
            for fraction in (.35,.7,1):
                amp=scale*fraction
                if amp<1e-9:continue
                y=tonal+amp*burst
                score=objective(y)+.08*sum(band_errors(x,y,fs).values())
                if score<baseline and (name not in families or score<families[name][0]):
                    families[name]=(score,filters,tau,amp)
    for hp in (600,2200,6000):
        if hp>=fs*.45:continue
        trial('Bruit blanc → passe-haut → enveloppe',[('highpass',{'fc':hp,'q':.707})])
        for lp in (6000,min(18000,fs*.45)):
            if lp<=hp:continue
            fc=float(np.sqrt(hp*lp));q=max(.1,fc/(lp-hp))
            trial('Bruit blanc → passe-bande → enveloppe',[('bandpass',{'fc':fc,'q':q})])
            trial('Bruit blanc → passe-haut → passe-bas → enveloppe',[('highpass',{'fc':hp,'q':.707}),('lowpass',{'fc':lp,'q':.707})])
    candidates=[];diagnostics=[]
    for name,(_,filters,tau,amp) in families.items():
        p=base.model_copy(deep=True);used={b.id for b in p.nodes};stem='residual'
        while any(k.startswith(stem+'-') for k in used):stem+='x'
        chain=[(stem+'-noise','noise',{'amplitude':amp,'seed':42},'Bruit blanc')]
        chain.extend((f'{stem}-filter-{i}',kind,params,{'highpass':'Passe-haut','lowpass':'Passe-bas','bandpass':'Passe-bande'}[kind]) for i,(kind,params) in enumerate(filters))
        chain.append((stem+'-envelope','envelope',{'attack':.001,'tau':tau,'onset':onset},'Enveloppe exponentielle / VCA'))
        for i,(nid,kind,params,label) in enumerate(chain):
            p.nodes.append(Block(id=nid,type=kind,parameters=params,label=label,position={'x':i*240,'y':800},reason='Branche de bruit résiduel réellement exécutée. Le niveau est réglé par l’amplitude explicite de la source ; aucun gain ni oscillateur dissimulé. Ne remplace pas des partiels stables sans validation du coût et des bandes.'))
            if i:p.edges.append(link(chain[i-1][0],nid))
        out=next(b.id for b in p.nodes if b.type=='output');parent=next(e.source for e in p.edges if e.target==out)
        if next(b.type for b in p.nodes if b.id==parent)=='sum':
            p.edges.append(link(chain[-1][0],parent))
        else:
            mix=stem+'-sum';p.nodes.append(Block(id=mix,type='sum',label='Somme : tonal + bruit filtré',position={'x':1200,'y':350}))
            p.edges=[e for e in p.edges if e.target!=out]
            p.edges.extend([link(parent,mix),link(chain[-1][0],mix),link(mix,out)])
        p.name=(base.name+' · bruit filtré')[:200]
        from .instrument import physical_count
        candidates.append(p);diagnostics.append({'architecture':name,'sources':sum(b.type in ('modal','oscillator','noise') for b in p.nodes),'blocks':physical_count(p),'full_rate_error':objective(render(p)),'analysis_rate':fs,'noise_seed':42})
    return candidates,diagnostics
