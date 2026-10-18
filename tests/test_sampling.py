from s2t.sampling import split_per_size


def test_split_sums_to_budget_and_balances_sizes_over_spots():
    for per_spot, n in [(12, 4), (18, 4), (12, 3), (18, 3), (3, 4), (1, 4)]:
        rows = [split_per_size(per_spot, n, i) for i in range(9)]
        assert all(sum(r) == per_spot for r in rows)
        totals = [sum(r[j] for r in rows) for j in range(n)]
        assert max(totals) - min(totals) <= 1


def test_examples():
    assert split_per_size(12, 4, 0) == [3, 3, 3, 3]
    assert split_per_size(18, 4, 0) == [5, 5, 4, 4]
    assert split_per_size(18, 4, 1) == [4, 5, 5, 4]
    assert split_per_size(3, 4, 0) == [1, 1, 1, 0]
