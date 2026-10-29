from pathlib import Path
import pytest
from identity_match_loss import (run_funnel, default_steps, fewer_handoffs, final_reach,
    choose_match_type, layered_retention, validate_file, AcxiomStyleRecord, EpsilonStyleRecord, Step)

DATA = Path(__file__).parent.parent / "data"

def test_baseline_reach_is_32_percent():
    assert final_reach(1000, default_steps()) == 320

def test_fewer_handoffs_beats_better_match_rate():
    base = final_reach(1000, default_steps())
    better = default_steps(); better[0] = Step("ID vendor match", 0.80)
    fewer = fewer_handoffs(default_steps(), "Onboarding")
    assert final_reach(1000, better) < final_reach(1000, fewer)
    assert final_reach(1000, better) > base

def test_probabilistic_raises_match_rate():
    assert final_reach(1000, default_steps("probabilistic")) > final_reach(1000, default_steps("deterministic"))

def test_objective_switch():
    assert choose_match_type("reach") == ["probabilistic"]
    assert choose_match_type("conversion") == ["deterministic"]
    assert choose_match_type("regulated") == ["deterministic"]
    assert "deterministic" in choose_match_type("reach", layered=True)

def test_layered_between_the_two():
    assert 0.70 < layered_retention() < 0.85

def test_bad_retention_rejected():
    with pytest.raises(ValueError):
        run_funnel(100, [Step("x", 1.5)])

def test_unknown_step_rejected():
    with pytest.raises(ValueError):
        fewer_handoffs(default_steps(), "nope")

def test_acxiom_contract_flags_bad_rows():
    valid, flagged = validate_file(DATA / "acxiom_style.csv", AcxiomStyleRecord)
    assert len(valid) == 12 and len(flagged) == 1

def test_epsilon_contract_flags_optout_and_count():
    valid, flagged = validate_file(DATA / "epsilon_style.csv", EpsilonStyleRecord)
    assert len(valid) == 12 and len(flagged) == 2
