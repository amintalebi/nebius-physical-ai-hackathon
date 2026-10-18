import pytest

from s2t.stats import cohen_kappa, p_at_least_k_of_3, wilson_interval


def test_wilson_contains_point_estimate_and_is_wide_for_small_n():
    lo, hi = wilson_interval(2, 3)
    assert lo < 2 / 3 < hi
    assert hi - lo > 0.5  # 3 trials tell you very little: the point of logging many more


def test_wilson_edges():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = wilson_interval(18, 18)
    assert hi == pytest.approx(1.0) and lo > 0.8


def test_p_at_least():
    assert p_at_least_k_of_3(1.0, 3) == pytest.approx(1.0)
    assert p_at_least_k_of_3(0.5, 2) == pytest.approx(0.5)


def test_kappa():
    assert cohen_kappa([True, False, True, False], [True, False, True, False]) == pytest.approx(1.0)
    assert cohen_kappa([True, True, False, False], [True, False, True, False]) == pytest.approx(0.0)
