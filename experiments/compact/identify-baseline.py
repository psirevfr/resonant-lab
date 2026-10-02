"""Explicit candidate family selection, with measured error and complexity penalty."""
import numpy as np
from .schema import Block,Edge,Patch,Weights
from .analysis import analyze
from .graph import render
from .metrics import Objective
from .audio import spectrum

def link(source,target): return Edge(id=f'{source}-{target}',source=source,target=target)

def modal_patch(features,fs,duration,count):
    ranked=sorted(features['partials'],key=lambda p:p['amplitude']**2*p['tau'],reverse=True)[:count]
    ranked=sorted(ranked,key=lambda p:p['frequency'])
    nodes=[]; edges=[]
    for i,p in enumerate(ranked):
        id=f'mode-{i+1}'
        nodes.append(Block(id=id,type='modal',label=f'Mode {i+1}',parameters={k:p[k] for k in ('frequency','amplitude','phase','tau')}|{'attack':features['attack'],'onset':features['onset']},position={'x':30+250*(i//8),'y':30+(i%8)*115},reason=f'Pic spectral mesuré à {p["frequency"]:.3f} Hz. Décroissance estimée τ={p["tau"]:.3f} s par régression log-amplitude STFT ; phase et amplitude par projection temporelle. R² descriptif : {p["decay_r2"]}.'))
        edges.append(link(id,'sum'))
    mid=30+min(7,max(0,count-1))*57
    merge_x=330+250*((count-1)//8)
    nodes.extend([Block(id='sum',type='sum',label='Somme des modes',position={'x':merge_x,'y':mid},reason='Superposition linéaire des modes détectés.'),Block(id='gain',type='gain',label='Gain de sortie',parameters={'gain':1},position={'x':merge_x+240,'y':mid},reason='Gain unité explicite ; aucun changement de niveau caché.'),Block(id='out',type='output',label='Sortie mono',position={'x':merge_x+480,'y':mid})])
    edges.extend([link('sum','gain'),link('gain','out')])
    return Patch(name=f'{count} modes amortis',sample_rate=fs,duration=duration,nodes=nodes,edges=edges)

def noise_patch(x,fs,features):
    f,a=spectrum(x,fs); fc=float(np.clip(np.sum(f*a*a)/max(np.sum(a*a),1e-20)*2,40,fs*.45))
    tau=float(np.median([p['tau'] for p in features['partials']]))
    patch=Patch(name='Bruit filtré amorti',sample_rate=fs,duration=len(x)/fs,nodes=[
        Block(id='noise',type='noise',parameters={'amplitude':float(np.clip(np.std(x)*2,1e-6,4)),'seed':42},position={'x':0,'y':0},reason='Candidat stochastique à comparer aux modèles tonals ; graine fixe pour reproductibilité.'),
        Block(id='filter',type='lowpass',parameters={'fc':fc,'q':.70710678},position={'x':240,'y':0},reason=f'Initialisation fc = 2 × centroïde énergétique ({fc:.1f} Hz après bornage). Heuristique explicitement testée, pas une identification unique.'),
        Block(id='env',type='envelope',parameters={'attack':features['attack'],'tau':tau},position={'x':480,'y':0},reason='Attaque mesurée et médiane des constantes de décroissance.'),
        Block(id='out',type='output',position={'x':720,'y':0})],edges=[link('noise','filter'),link('filter','env'),link('env','out')])
    return patch

def complexity(patch):
    return len(patch.nodes)+.25*sum(len(n.parameters) for n in patch.nodes)

def generate(x,fs,max_partials=24,penalty=.0001,weights=None,refine_modes=True,include_impact=True,detailed=True):
    features=analyze(x,fs,max_partials); objective=Objective(x,fs,weights or Weights())
    counts=sorted(set([1,min(4,len(features['partials'])),len(features['partials'])]))
    patches=[modal_patch(features,fs,len(x)/fs,n) for n in counts]+[noise_patch(x,fs,features)]
    # A filter is retained only if a scored candidate justifies it.
    full=patches[-2]
    for fc in (2000.,6000.):
        if fc >= fs*.45: continue
        variant=full.model_copy(deep=True); variant.name+=f' + LPF {fc:g} Hz'
        variant.nodes.append(Block(id='filter',type='lowpass',parameters={'fc':fc,'q':.70710678},position={'x':570,'y':-130},reason=f'Candidat passe-bas évalué à fc={fc:g} Hz, Q=1/√2 ; retenu uniquement selon erreur + pénalité de complexité. Cette comparaison ne prouve pas la présence physique du filtre.'))
        variant.edges=[e for e in variant.edges if not (e.source=='sum' and e.target=='gain')]+[link('sum','filter'),link('filter','gain')]
        patches.append(variant)
    refinement=[]
    if refine_modes:
        from .modal_fit import refine
        from .attack_fit import calibrate_attack
        profiles=[('battements',3,.006,None)]
        if detailed:
            profiles += [('détaillés',5,.0005,None),('résonances isolées',3,.006,12)]
        for title,max_modes,local_penalty,bandwidth in profiles:
            fitted,diagnostics=refine(x,fs,features,max_partials,max_modes,local_penalty,bandwidth)
            enhanced=modal_patch(fitted,fs,len(x)/fs,len(fitted['partials']))
            enhanced.name=f'{len(fitted["partials"])} modes / {title}'
            for node in enhanced.nodes:
                if node.type=='modal':
                    node.reason=f'Mode amorti ajusté sur une trajectoire complexe. Jusqu’à {max_modes} composantes proches par groupe permettent des battements et plusieurs décroissances. Pénalité locale {local_penalty:g} par mode ; groupe conservé si SSE relative < 0,35. Isolement supplémentaire : {bandwidth or "aucun"} Hz. Les mêmes filtres d’analyse sont appliqués aux mesures et aux fonctions ajustées. Aucune onde enregistrée ni enveloppe échantillonnée n’est rejouée.'
            patches.append(enhanced)
            calibrated,attack_fit=calibrate_attack(enhanced,objective)
            calibrated.name+=' · attaque ajustée'
            patches.append(calibrated)
            refinement.append({'profile':title,'groups':diagnostics,'attack_fit':attack_fit})
    if include_impact:
        from .impact import fit_impact
        # Fit on the best tonal proposal without complexity penalty so the attack
        # does not compensate for intentionally discarded pitched components.
        tonal=min((p for p in patches if any(n.type=='modal' for n in p.nodes)),key=lambda p:objective(render(p)))
        impact=fit_impact(tonal,x,features,objective)
        if impact is not None:patches.append(impact)
    results=[]
    for patch in patches:
        errors=objective.components(render(patch)); c=complexity(patch)
        results.append({'patch':patch.model_dump(),'errors':errors,'complexity':c,'score':errors['total']+penalty*c})
    results.sort(key=lambda r:r['score'])
    return {'analysis':features,'candidates':results,'patch':results[0]['patch'],'selection':'Score = erreur pondérée + λ × (blocs + 0,25 × paramètres explicites). Familles testées : modes amortis, modes filtrés, bruit filtré amorti, modes proches affinés et impact bruité selon les options.','penalty':penalty,'refinement':refinement,'impact_tested':include_impact}
