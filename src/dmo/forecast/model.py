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
        return baseline * (1 + self.coefficient * (1 - math.exp(-max(0, elapsed_days) / 14)))
