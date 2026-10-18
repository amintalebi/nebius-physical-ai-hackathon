"""Episode budgets for scripted sim collection (scripts/collect_grid.py)."""

from __future__ import annotations


def split_per_size(per_spot: int, n_sizes: int, spot_index: int) -> list[int]:
    """Split one spot's episode budget over the cube sizes.

    Each size gets per_spot // n_sizes; the remainder goes to sizes chosen by rotating with the spot
    index, so over the 9 spots every size ends up with (almost) the same total. 18 over 4 sizes ->
    [5, 5, 4, 4] at spot 0, [4, 5, 5, 4] at spot 1, ...
    """
    base, extra = divmod(per_spot, n_sizes)
    return [base + (1 if (j - spot_index) % n_sizes < extra else 0) for j in range(n_sizes)]
