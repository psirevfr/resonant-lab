"""Shared CPU-only entry point for the server worker and Python/WebAssembly worker."""
import time
from threading import Event
import numpy as np
from .schema import GenerateRequest,OptimizeRequest,CompactRequest

ALGORITHM_VERSION='shared-python-v1'
MODELS={'generate':GenerateRequest,'optimize':OptimizeRequest,'compact':CompactRequest}


def validate_input(kind,request,x,fs):
    if not isinstance(kind,str) or kind not in MODELS:raise ValueError('Type de calcul inconnu.')
    r=MODELS[kind].model_validate(request)
    x=np.asarray(x,dtype=np.float64)
    if fs not in (44100,48000,96000) or x.ndim!=1 or len(x)<32 or x.nbytes>10_000_000 or not np.isfinite(x).all():
        raise ValueError('Sélection mono finie requise, taille maximale 10 Mo.')
    duration=r.duration if kind=='generate' else r.patch.duration
    # Generation historically uses the actual excerpt length after source-frame
    # rounding and resample_poly. Do not pad/crop it to a different waveform.
    compatible=(abs(len(x)/fs-duration)<=1/8000+1/fs) if kind=='generate' else len(x)==round(duration*fs)
    if duration>12 or not compatible:raise ValueError('Durée ou fréquence de la référence incompatible.')
    if kind!='generate' and r.patch.sample_rate!=fs:raise ValueError('Fréquence du modèle incompatible.')
    if kind=='optimize':
        from .optimization import validate_request
        validate_request(r)
    if kind=='compact':
        from .compact import validate_simplification
        validate_simplification(r.patch,r.tolerance)
    return r,x


def compute(kind,request,x,fs,progress=lambda _:None,cancel=None):
    begun=time.perf_counter();r,x=validate_input(kind,request,x,fs);validated=time.perf_counter()
    if kind=='generate':
        from .identify import generate
        result=generate(x,fs,r.max_partials,r.complexity_penalty,r.weights,r.refine_modes,r.include_impact,r.detailed)
    elif kind=='optimize':
        from .optimization import run_optimization
        result=run_optimization(r,x,progress,cancel or Event())
    else:
        from .compact import simplify
        result=simplify(r.patch,x,r.weights,r.tolerance,r.test_shaping,r.protect_texture)
    # Same JSON contract; additional performance metadata is independent of objective.
    result['compute_metrics']={'algorithm_version':ALGORITHM_VERSION,'validation_ms':(validated-begun)*1000,'algorithm_ms':(time.perf_counter()-validated)*1000}
    return result
