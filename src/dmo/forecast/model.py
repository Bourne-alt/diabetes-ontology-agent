"""Replaceable initialized model; no learned clinical parameters."""
import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class InitializedResponseModel:
    coefficient: float
    version = 'untrained-demo-v1'

    @classmethod
    def initialize(cls, seed: int) -> 'InitializedResponseModel':
        return cls(random.Random(seed).uniform(-0.1, 0.1))

    def predict(self, baseline: float, elapsed_days: float) -> float:
        return self.components(baseline, elapsed_days)["value"]

    def components(self, baseline: float, elapsed_days: float) -> dict:
        elapsed = max(0, elapsed_days)
        decay = math.exp(-elapsed / 14)
        response = self.coefficient * (1 - decay)
        return {"elapsed_days": elapsed, "decay": decay, "response": response,
                "multiplier": 1 + response, "value": baseline * (1 + response)}
