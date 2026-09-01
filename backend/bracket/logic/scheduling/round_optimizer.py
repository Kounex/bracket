from decimal import Decimal
from functools import cache

from bracket.models.db.match import get_match_hash
from bracket.models.db.stage_item import PairingMode
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.utils.id_types import StageItemInputId
from bracket.utils.types import assert_some

MAX_INPUTS_FOR_EXACT_OPTIMIZATION = 20
"""
Above this number of teams the exact bitmask DP (2^N states) is too slow and the caller
should fall back to the greedy suggestion-based scheduling.
"""

_SOCIAL_FAIRNESS_WEIGHT = Decimal("1000000")
# Negative: in competitive mode the (tiny) fairness tiebreak favors teams that have played
# more matches, so leaders stay on court instead of being benched; ELO difference dominates.
_COMPETITIVE_FAIRNESS_WEIGHT = Decimal("-0.01")
_INF = Decimal("Infinity")


def get_optimal_round_pairings(
    inputs: list[StageItemInputFinal],
    times_played_per_input: dict[StageItemInputId, int],
    courts_count: int,
    previous_match_hashes: frozenset[str],
    mode: PairingMode,
) -> list[tuple[StageItemInputFinal, StageItemInputFinal]] | None:
    n = len(inputs)
    if n > MAX_INPUTS_FOR_EXACT_OPTIMIZATION:
        return None
    pairs_needed = min(courts_count, n // 2)
    if pairs_needed < 1:
        return []

    fairness_weight = (
        _SOCIAL_FAIRNESS_WEIGHT if mode is PairingMode.SOCIAL else _COMPETITIVE_FAIRNESS_WEIGHT
    )
    elos = [input_.elo for input_ in inputs]
    played = [times_played_per_input.get(assert_some(input_.id), 0) for input_ in inputs]
    input_ids = [assert_some(input_.id) for input_ in inputs]

    def pair_cost(i: int, j: int) -> Decimal:
        return fairness_weight * (played[i] + played[j]) + abs(elos[i] - elos[j])

    @cache
    def dp(avail: int, pairs_left: int) -> tuple[Decimal, tuple[tuple[int, int], ...]]:
        """Min cost to schedule `pairs_left` more matches from the teams set in `avail`."""
        if pairs_left == 0:
            return (Decimal(0), ())
        if avail.bit_count() < pairs_left * 2:
            return (_INF, ())
        i = (avail & -avail).bit_length() - 1
        rest = avail ^ (1 << i)
        best = dp(rest, pairs_left)  # team i sits out this round
        jbits = rest
        while jbits:
            j = (jbits & -jbits).bit_length() - 1
            jbits &= jbits - 1
            if get_match_hash(input_ids[i], input_ids[j]) in previous_match_hashes:
                continue
            sub_cost, sub_pairs = dp(rest ^ (1 << j), pairs_left - 1)
            candidate = (sub_cost + pair_cost(i, j), (*sub_pairs, (i, j)))
            # Tie-break on the sorted pair indices so equal-cost solutions are deterministic
            # (preferring lower-index teams playing over sitting out).
            if candidate[0] < best[0] or (
                candidate[0] == best[0] and sorted(candidate[1]) < sorted(best[1])
            ):
                best = candidate
        return best

    cost, pair_indices = dp((1 << n) - 1, pairs_needed)
    if cost >= _INF:
        return []
    return [(inputs[i], inputs[j]) for i, j in pair_indices]
