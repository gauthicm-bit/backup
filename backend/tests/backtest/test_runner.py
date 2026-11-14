"""No look-ahead and exact cost timing, contract §2.4."""

import numpy as np
import pytest

from engine.backtest.runner import _positions, run_backtest
from engine.backtest.templates import TEMPLATES, expand_grid
from engine.common import Cancelled


def test_ma_signal_and_cost_alignment():
    close = np.array([10.0, 11.0, 12.0, 9.0, 8.0, 13.0])
    r = np.log(close[1:] / close[:-1])
    result = run_backtest(
        10.0,
        r,
        np.tile(r, (3, 1)),
        "ma_crossover",
        [{"fast": 2, "slow": 3}, {"fast": 2, "slow": 4}],
        10,
    )
    np.testing.assert_array_equal(result.position_real_selected[:2], [0, 0])
    for v, params in enumerate(result.variants):
        pos = np.zeros(len(close))
        for t in range(int(params["slow"]) - 1, len(close)):
            pos[t] = np.mean(close[t - int(params["fast"]) + 1 : t + 1]) > np.mean(
                close[t - int(params["slow"]) + 1 : t + 1]
            )
        prev = np.r_[0.0, pos[:-1]]
        expected = pos[:-1] * np.expm1(r) - 0.001 * np.abs(pos[:-1] - prev[:-1])
        np.testing.assert_allclose(result.strat_ret_real[:, v], expected)
    assert result.sharpe_paths.shape == (3, 2)
    assert result.strat_ret_paths_selected.shape == (3, 5)
    np.testing.assert_allclose(
        result.strat_ret_paths_selected[0], result.strat_ret_real[:, result.selected]
    )


def test_future_changes_do_not_change_past_returns():
    r = np.random.default_rng(5).normal(0, 0.01, 100)
    variants = [{"fast": 2, "slow": 10}, {"fast": 3, "slow": 12}]
    first = run_backtest(100.0, r, r[None, :], "ma_crossover", variants, 5)
    changed = r.copy()
    changed[70:] = 0.1
    second = run_backtest(100.0, changed, changed[None, :], "ma_crossover", variants, 5)
    np.testing.assert_array_equal(first.strat_ret_real[:70], second.strat_ret_real[:70])


@pytest.mark.parametrize("template_id", list(TEMPLATES))
def test_all_templates_shapes_determinism_and_no_lookahead(template_id):
    spec = TEMPLATES[template_id]
    variants = expand_grid(template_id, {p.name: p.default_values for p in spec.params})
    rng = np.random.default_rng(22)
    r = rng.normal(0.0005, 0.02, 800)
    paths = rng.normal(0.0005, 0.02, (4, 800))
    result = run_backtest(100, r, paths, template_id, variants, 5)
    assert result.strat_ret_real.shape == (800, len(variants))
    assert result.sharpe_paths.shape == (4, len(variants))
    assert np.isfinite(result.sharpe_paths).all()
    assert set(result.position_real_selected) <= {0, 1}
    changed = r.copy()
    changed[600:] += 0.03
    future = run_backtest(100, changed, paths, template_id, variants, 5)
    np.testing.assert_array_equal(result.strat_ret_real[:600], future.strat_ret_real[:600])
    np.testing.assert_array_equal(
        result.sharpe_paths, run_backtest(100, r, paths, template_id, variants, 5).sharpe_paths
    )


def test_stateful_strategy_signals_on_hand_built_prices():
    prices = np.array([[10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 14.0, 10.0, 8.0, 9.0, 10.0, 12.0]])
    breakout = _positions(prices, "breakout", {"entry_lookback": 3, "exit_lookback": 2})
    np.testing.assert_array_equal(breakout[0], [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1])
    rsi = _positions(prices, "rsi_mean_reversion", {"period": 2, "entry": 30, "exit": 70})
    assert rsi[0, 2] == 0
    assert rsi[0, 8] == 1
    assert rsi[0, -1] == 0
    momentum = _positions(prices, "momentum", {"lookback": 3, "threshold": 0})
    assert momentum[0, 3] == 1
    assert momentum[0, 8] == 0


def test_cancellation_propagates_and_long_warmup_is_flat():
    r = np.full(50, 0.001)
    variants = [{"fast": 2, "slow": 100}, {"fast": 3, "slow": 200}]
    result = run_backtest(100, r, r[None, :], "ma_crossover", variants, 5)
    assert not result.strat_ret_real.any()

    def cancelled(_):
        raise Cancelled()

    with pytest.raises(Cancelled):
        run_backtest(100, r, r[None, :], "ma_crossover", variants, 5, cancelled)


@pytest.mark.parametrize(
    "r,paths,cost",
    [
        (np.zeros(2), np.zeros((1, 3)), 5),
        (np.array([np.nan, 0]), np.zeros((1, 2)), 5),
        (np.zeros(2), np.zeros((1, 2)), 101),
    ],
)
def test_invalid_runner_inputs(r, paths, cost):
    with pytest.raises(ValueError):
        run_backtest(100, r, paths, "ma_crossover", [{"fast": 2, "slow": 10}], cost)
