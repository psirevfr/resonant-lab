"""Versioned, bounded patch format. Parameters are defined by the DSP registry."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class Block(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=80)
    type: str
    label: str = Field(default='', max_length=160)
    parameters: dict[str, float] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=lambda: {'x': 0, 'y': 0})
    reason: str = Field(default='', max_length=4000)

class Edge(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    id: str
    source: str
    target: str

class Patch(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    version: Literal[1] = 1
    name: str = Field(default='Sans titre', max_length=200)
    sample_rate: Literal[44100, 48000, 96000] = 44100
    duration: float = Field(default=3, ge=0.05, le=60)
    nodes: list[Block] = Field(min_length=1, max_length=128)
    edges: list[Edge] = Field(default_factory=list, max_length=512)

class Weights(BaseModel):
    time: float = Field(default=0.1, ge=0, le=100)
    spectral: float = Field(default=0.25, ge=0, le=100)
    spectrogram: float = Field(default=0.5, ge=0, le=100)
    envelope: float = Field(default=0.15, ge=0, le=100)
    attack: float = Field(default=0.25, ge=0, le=100)
    @model_validator(mode='after')
    def nonzero(self):
        if sum(self.model_dump().values()) == 0:
            raise ValueError('Au moins un poids doit être non nul.')
        return self

class RenderRequest(BaseModel):
    patch: Patch
    audio_id: str | None = None
    weights: Weights = Field(default_factory=Weights)
    start: float = Field(default=0, ge=0)

class AnalyzeRequest(BaseModel):
    audio_id: str
    start: float = Field(default=0, ge=0)
    duration: float = Field(default=3, ge=0.05, le=12)
    max_partials: int = Field(default=24, ge=1, le=24)

class GenerateRequest(AnalyzeRequest):
    refine_modes: bool = True
    detailed: bool = True
    include_impact: bool = True
    complexity_penalty: float = Field(default=0.0001, ge=0, le=1)
    weights: Weights = Field(default_factory=Weights)

class OptimizeRequest(RenderRequest):
    method: Literal['Powell', 'L-BFGS-B', 'differential_evolution'] = 'Powell'
    max_iterations: int = Field(default=15, ge=1, le=60)
    parameter_ids: list[str] = Field(default_factory=list, max_length=24)

class CompactRequest(RenderRequest):
    tolerance: float = Field(default=.2, ge=0, le=1, allow_inf_nan=False)
    test_shaping: bool = True
    protect_texture: bool = False

class InstrumentRequest(BaseModel):
    patch: Patch
    note: int = Field(default=69,ge=21,le=108)
    reference_note: int = Field(default=69,ge=21,le=108)
    velocity: int = Field(default=127,ge=0,le=127)
    gate: float = Field(default=60,ge=0,le=60,allow_inf_nan=False)
    track_filters: bool = True
