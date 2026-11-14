"""Scientific invariants and independently calculated contract §2.5 examples."""

import math

import numpy as np
import pytest

from engine.metrics.dsr import compute_dsr, expected_max_sharpe, deflated_probability
from engine.metrics.pbo import compute_pbo
from engine.metrics.survival import compute_survival
from engine.metrics.survival import compute_survival_rate
from engine.backtest.runner import sharpe
from engine.metrics.verdict import decide_verdict


def test_expected_max_paper_example():
    """Bailey & Lopez de Prado (2014), eq. 1: N=100, variance=1 gives 2.531.

    https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf
    Paper-derived analytic value, not an invented empirical dataset.
    """
    assert expected_max_sharpe(100, 1) == pytest.approx(2.5306, abs=0.001)


def test_dsr_published_treasury_numerical_example():
    """Bailey & Lopez de Prado (2014), pp.9–10: DSR=0.9004.

    https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf
    Published inputs N=100, annual SR=2.5, annual SR variance=1/2,
    T=1250, skew=-3, Pearson kurtosis=10, 250 observations/year.
    The paper uses 250 days; production contract uses 252 for payloads.
    """
    sr0 = expected_max_sharpe(100, 0.5 / 250)
    assert sr0 == pytest.approx(0.1132, abs=0.0001)
    assert deflated_probability(2.5 / np.sqrt(250), sr0, 1250, -3, 10) == pytest.approx(
        0.9004, abs=0.001
    )


def test_pbo_published_ranking_example():
    """Bailey et al (2015), p.9: IS=(.5,1.1,.7), OOS=(.6,.7,1.3).

    https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
    IS winner index1 has OOS rank2; contract omega=2/(3+1)=.5,
    lambda=0. The complementary split also selects the median OOS rank.
    """
    base = np.array([-1, 1]) / np.sqrt(2)
    matrix = np.vstack(
        [
            base[:, None] + np.array([0.5, 1.1, 0.7])[None, :] / np.sqrt(252),
            base[:, None] + np.array([0.6, 0.7, 1.3])[None, :] / np.sqrt(252),
        ]
    )
    result = compute_pbo(matrix, 2)
    np.testing.assert_allclose(result.logits, 0, atol=1e-12)
    assert result.pbo == 1


def test_cscv_hand_worked_example():
    """Bailey et al (2015) CSCV §3, worked 4-block application.

    https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
    Each block has variant A mean +.01 and B mean -.01 with equal variance:
    all six IS winners are A; OOS rank=2, omega=2/3, logit=ln(2), PBO=0.
    This is a hand-worked application of the paper, not its unavailable raw data.
    """
    a = np.tile([0, 0.02], 16)
    matrix = np.column_stack([a, -a])
    result = compute_pbo(matrix, 4)
    assert result.n_splits == 6
    assert result.pbo == 0
    np.testing.assert_allclose(result.logits, math.log(2), atol=1e-12)


def test_pbo_full_splits_noise_and_edge():
    rng = np.random.default_rng(17)
    noise = rng.normal(0, 0.01, (1600, 16))
    assert 0.3 < compute_pbo(noise).pbo < 0.7
    edge = noise.copy()
    edge[:, 0] += 0.01
    assert compute_pbo(edge).pbo < 0.01
    result = compute_pbo(noise)
    assert result.n_splits == 12870
    assert np.isfinite(result.logits).all()
    np.testing.assert_array_equal(result.logits, compute_pbo(noise).logits)


def test_dsr_two_identical_trials_and_flat():
    rng = np.random.default_rng(4)
    r = rng.normal(0.001, 0.01, 1600)
    result = compute_dsr(np.column_stack([r, r]), 0)
    assert result.n_trials == 2
    assert result.sr0 == pytest.approx(0, abs=1e-14)
    assert result.dsr_prob > 0.95
    assert compute_dsr(np.zeros((100, 2)), 0).dsr_prob == 0.5


def test_regime_crash_excludes_trend_down_and_drawdown_starts_at_one():
    index = np.full((1, 252), np.log(0.75) / 252)
    strategy = np.full((1, 252), 0.001)
    result = compute_survival(index, strategy)
    assert result.n_windows[0] == 1
    assert result.n_windows[4] == 0
    assert result.values[0, 0] == 0  # zero variance => zero Sharpe
    assert result.values[0, 2] == 0
    negative = compute_survival(index, np.full((1, 252), -0.001))
    assert negative.values[0, 2] == pytest.approx((0.999**252) - 1)


def test_gate2_synthetic_noise_luck_and_edge_skill():
    rng = np.random.default_rng(25)
    noise = rng.normal(-0.001, 0.01, (1600, 16))
    edge = rng.normal(0, 0.01, (1600, 16))
    edge[:, 0] += 0.004
    for matrix, expected in [(noise, "luck"), (edge, "skill")]:
        selected = int(np.argmax(matrix.mean(axis=0) / matrix.std(axis=0, ddof=1)))
        path_strategy = rng.normal(matrix[:, selected].mean(), 0.01, (1000, 1600))
        path_bh = rng.normal(0, 0.01, (1000, 1600))
        survival = compute_survival_rate(sharpe(path_strategy), sharpe(path_bh))
        verdict = decide_verdict(
            compute_pbo(matrix).pbo, compute_dsr(matrix, selected).dsr_prob, survival, 1000
        )
        assert verdict.verdict == expected


def test_stable_tie_policy_is_conservative_and_integer_ranked():
    r = np.random.default_rng(23).normal(0, 0.01, 160)
    result = compute_pbo(np.tile(r[:, None], (1, 4)))
    assert result.pbo == 1
    np.testing.assert_allclose(result.logits, np.log(0.2 / 0.8))


def test_empty_regime_windows_and_invalid_inputs():
    result = compute_survival(np.zeros((2, 100)), np.zeros((2, 100)))
    assert result.n_windows.sum() == 0
    assert np.isnan(result.values).all()
    with pytest.raises(ValueError):
        compute_survival(np.zeros((2, 100)), np.zeros((1, 100)))
    with pytest.raises(ValueError):
        compute_survival_rate(np.zeros(3), np.zeros(4))


def test_verdict_threshold_boundaries():
    assert decide_verdict(0.25, 0.99, 0.9, 1000).verdict == "inconclusive"
    assert decide_verdict(0.24, 0.95, 0.6, 1000).verdict == "skill"
    assert decide_verdict(0.5, 1, 1, 1000).verdict == "luck"
    assert decide_verdict(0.1, 0.499, 0.9, 1000).verdict == "luck"


def test_invalid_metric_inputs():
    with pytest.raises(ValueError):
        compute_pbo(np.zeros((10, 2)))
    with pytest.raises(ValueError):
        compute_dsr(np.zeros((100, 1)), 0)
