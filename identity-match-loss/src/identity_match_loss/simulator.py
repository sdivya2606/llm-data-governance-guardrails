"""Match-loss funnel simulator. Synthetic, illustrative rates only."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MatchType = Literal["deterministic", "probabilistic"]
Objective = Literal["reach", "conversion", "regulated"]

# Illustrative per-step retention and precision. Not real vendor performance.
MATCH_PROFILES = {
    "deterministic": {"retention": 0.70, "precision": 0.97},
    "probabilistic": {"retention": 0.85, "precision": 0.80},
}
OBJECTIVE_MIN_PRECISION = {"reach": 0.70, "conversion": 0.90, "regulated": 0.95}


@dataclass
class Step:
    name: str
    retention: float  # share of the previous step that survives
    reason: str = ""


@dataclass
class Scenario:
    name: str
    steps: list[Step] = field(default_factory=list)


def default_steps(match_type: MatchType = "deterministic") -> list[Step]:
    r = MATCH_PROFILES[match_type]["retention"]
    return [
        Step("ID vendor match", r, "Only people in the vendor's graph can match."),
        Step("Onboarding", 55 / 70, "IDs must translate to formats platforms accept; opt-outs removed."),
        Step("Platform match", 40 / 55, "Platforms only recognize IDs they have seen; syncs are periodic."),
        Step("Reached", 32 / 40, "Must be online and win a bid; frequency and budget caps."),
    ]


def run_funnel(seed_size: int, steps: list[Step]) -> list[tuple[str, int]]:
    """Return (step name, people remaining) including the starting seed."""
    out = [("Seed", seed_size)]
    n = float(seed_size)
    for s in steps:
        if not 0 <= s.retention <= 1:
            raise ValueError(f"retention for {s.name} must be in [0, 1]")
        n *= s.retention
        out.append((s.name, round(n)))
    return out


def fewer_handoffs(steps: list[Step], drop: str) -> list[Step]:
    """Remove one handoff, e.g. the onboarding step, to model a direct connection."""
    kept = [s for s in steps if s.name != drop]
    if len(kept) == len(steps):
        raise ValueError(f"no step named {drop!r}")
    return kept


def choose_match_type(objective: Objective, layered: bool = False) -> list[MatchType]:
    """Pick match type(s) for the objective.

    reach -> probabilistic fills out audience size.
    conversion/regulated -> deterministic where precision matters.
    layered -> deterministic first, probabilistic fills the remainder (reach only).
    """
    need = OBJECTIVE_MIN_PRECISION[objective]
    ok = [m for m, p in MATCH_PROFILES.items() if p["precision"] >= need]
    if objective == "reach":
        return ["deterministic", "probabilistic"] if layered else ["probabilistic"]
    if not ok:
        raise ValueError("no match type meets the precision floor")
    return ok


def layered_retention() -> float:
    """Deterministic first; probabilistic recovers part of the remainder.

    Illustrative: probabilistic recovers half of the people deterministic missed.
    """
    d = MATCH_PROFILES["deterministic"]["retention"]
    p = MATCH_PROFILES["probabilistic"]["retention"]
    return d + (p - d) * 0.5


def final_reach(seed_size: int, steps: list[Step]) -> int:
    return run_funnel(seed_size, steps)[-1][1]
