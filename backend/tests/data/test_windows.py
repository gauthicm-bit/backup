import numpy as np
import pytest

from engine.data.windows import return_windows


def test_windows_preserve_time_order_and_are_independent():
    values = np.arange(5, dtype=float)
    windows = return_windows(values, 3)
    np.testing.assert_array_equal(windows, [[0, 1, 2], [1, 2, 3], [2, 3, 4]])
    windows[0, 0] = 100
    assert values[0] == 0


def test_window_too_long_rejected():
    with pytest.raises(ValueError):
        return_windows(np.arange(5), 10)
