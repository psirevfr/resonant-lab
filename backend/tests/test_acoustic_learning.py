import numpy as np
import pytest

from lab.adaptive import adaptive_reward, envelope_candidate, select_strategy, sound_profile
from lab.blocks import adsr_envelope
from lab.compute import AnalysisCache, compute
from lab.graph import render
from lab.metrics import Objective
from lab.schema import Weights


def test_profiles_and_past_rewards_change_the_experimental_strategy():
    def features(envelope):
        return {'onset': 0, 'envelope': {'time': np.linspace(0, 1, 100), 'amplitude': envelope}}

    assert sound_profile(features(np.exp(-np.linspace(0, 30, 100))), 1) == 'transient'
    assert sound_profile(features(np.ones(100)), 1) == 'sustained'
    assert sound_profile(features(np.exp(-np.linspace(0, 3, 100))), 1) == 'decaying'
    assert select_strategy('sustained', {}) == 'adsr'
    history = {'sustained': {'adsr': {'count': 10, 'reward': 0}, 'decay': {'count': 10, 'reward': 9}}}
    assert select_strategy('sustained', history) == 'decay'
    assert select_strategy('transient', {'transient': {'decay': {'count': 5, 'reward': float('nan')}}}) == 'decay'


def test_learning_never_accepts_more_modules_or_worse_attack_or_bands():
    baseline = {'modules': 6, 'errors': {'total': .4, 'attack': .2}, 'bands': {'bass': .3}}
    candidate = {'modules': 5, 'errors': {'total': .3, 'attack': .2}, 'bands': {'bass': .3}}
    assert adaptive_reward(baseline, candidate) > 0
    assert adaptive_reward(baseline, {**candidate, 'modules': 7}) == 0
    assert adaptive_reward(baseline, {**candidate, 'errors': {**candidate['errors'], 'attack': .21}}) == 0
    assert adaptive_reward(baseline, {**candidate, 'bands': {'bass': .4}}) == 0


def test_analysis_cache_is_reused_only_for_the_exact_analysis(monkeypatch):
    from lab import analysis, identify

    calls = []
    def analyze(x, fs, max_partials):
        calls.append((x[0], fs, max_partials))
        return {'f0': 440.}
    monkeypatch.setattr(analysis, 'analyze', analyze)
    monkeypatch.setattr(identify, 'generate', lambda *args, features, **kwargs: {'analysis': features})
    cache = AnalysisCache()
    r = {'audio_id': 'test', 'duration': .05, 'max_partials': 2}
    x = np.ones(2205)
    compute('analyze', r, x, 44100, cache=cache)
    same = compute('generate', r, x.copy(), 44100, cache=cache)
    assert same['analysis'] == {'f0': 440.}
    assert same['compute_metrics']['analysis_cache_hit']
    assert not compute('analyze', {**r, 'max_partials': 1}, x, 44100, cache=cache)['compute_metrics']['analysis_cache_hit']
    x[0] = 0
    assert not compute('analyze', {**r, 'max_partials': 1}, x, 44100, cache=cache)['compute_metrics']['analysis_cache_hit']
    assert len(calls) == 3


def test_shared_adsr_candidate_can_fit_a_held_note_with_release():
    fs = 44100
    t = np.arange(round(.6*fs))/fs
    params = (.04, .07, .7, .45, .12)
    x = .3*adsr_envelope(t, *params, fs)*np.sin(2*np.pi*330*t+.2)
    objective = Objective(x, fs, Weights())
    features = {'onset': 0, 'attack': .013, 'partials': [{'frequency': 330, 'amplitude': .3}]}
    patch = envelope_candidate(x, fs, features, objective, 'adsr', 3)
    assert [node.type for node in patch.nodes] == ['oscillator','adsr','output']
    assert objective(render(patch)) < .05
    assert patch.nodes[1].parameters['gate'] == pytest.approx(params[3], abs=.015)
