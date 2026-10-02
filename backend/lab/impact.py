"""Measured transient-noise candidates. No residual waveform is stored or replayed."""
import numpy as np
from .schema import Block,Patch
from .blocks import process,parameters
from .graph import render
from .identify import link

def fit_impact(base: Patch,x,features,objective):
    fs=base.sample_rate; n=len(x); tonal=render(base); residual=x-tonal
    onset=max(0,features['onset']-.002)
    first=round(onset*fs); end=min(n,first+round(.12*fs))
    if end-first<32:return None
    residual_rms=float(np.sqrt(np.mean(residual[first:end]**2)))
    if residual_rms<1e-7:return None
    noise=process('noise',{'amplitude':1,'seed':42},[],fs,n)
    highpass={'fc':80.,'q':2**-.5}
    high=process('highpass',highpass,[noise],fs,n)
    best=None
    # The same draw is used for all candidates: no stochastic cherry-picking.
    for cutoff in (800.,2500.,7000.,14000.):
        if cutoff>=fs*.47:continue
        low=process('lowpass',{'fc':cutoff,'q':2**-.5},[high],fs,n)
        for tau in (.008,.025,.07,.15):
            env={'attack':.0007,'tau':tau,'onset':onset}
            burst=process('envelope',env,[low],fs,n)
            scale=residual_rms/max(float(np.sqrt(np.mean(burst[first:end]**2))),1e-12)
            for amount in (.25,.5,.75,1.):
                amplitude=float(min(4,scale*amount))
                error=objective(tonal+amplitude*burst)
                if best is None or error<best[0]:best=(error,cutoff,tau,amplitude)
    if best is None:return None
    error,cutoff,tau,amplitude=best
    patch=base.model_copy(deep=True);patch.name+=' + impact'
    old_output=next(n for n in patch.nodes if n.type=='output')
    source=next(e.source for e in patch.edges if e.target==old_output.id)
    patch.edges=[e for e in patch.edges if e.target!=old_output.id]
    y=max(n.position.get('y',0) for n in patch.nodes)+160
    mix_x=max(1020,max(n.position.get('x',0) for n in patch.nodes)+240)
    reason=f'Bruit d’impact candidat ajusté sur le résidu du modèle tonal. Recherche fc∈{{800,2500,7000,14000}} Hz et τ∈{{8,25,70,150}} ms ; amplitude mise à l’échelle du RMS résiduel sur 120 ms, puis testée à 25/50/75/100 %. Graine 42 inchangée. Ce bruit ne prétend pas identifier une collision marteau-corde exacte. Coût mesuré {error:.6f}.'
    patch.nodes.extend([
        Block(id='impact-noise',type='noise',label='Impact · bruit blanc',parameters={'amplitude':amplitude,'seed':42},position={'x':30,'y':y},reason=reason),
        Block(id='impact-hp',type='highpass',label='Impact · coupe-bas',parameters=highpass,position={'x':280,'y':y},reason='Coupe-bas à 80 Hz dans cette famille de candidats : retire la composante très basse fréquence du bruit. Hypothèse de modèle explicite.'),
        Block(id='impact-lp',type='lowpass',label='Impact · couleur',parameters={'fc':cutoff,'q':2**-.5},position={'x':520,'y':y},reason=reason),
        Block(id='impact-env',type='envelope',label='Impact · enveloppe',parameters={'attack':.0007,'tau':tau,'onset':onset},position={'x':760,'y':y},reason=reason),
        Block(id='impact-sum',type='sum',label='Modes + impact',position={'x':mix_x,'y':y-160},reason='Somme explicite des modes déterministes et du bruit transitoire. Aucune copie du WAV dans le graphe.')])
    old_output.position={'x':mix_x+250,'y':y-160}
    patch.edges.extend([link('impact-noise','impact-hp'),link('impact-hp','impact-lp'),link('impact-lp','impact-env'),link(source,'impact-sum'),link('impact-env','impact-sum'),link('impact-sum',old_output.id)])
    return patch
