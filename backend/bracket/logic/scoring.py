from fastapi import HTTPException
from starlette import status

from bracket.models.db.match_set import MatchSetBody
from bracket.models.db.sport import SportConfig


def derive_set_wins(sets: list[MatchSetBody]) -> tuple[int, int]:
    """Count how many sets each side has won."""
    wins1 = 0
    wins2 = 0
    for s in sets:
        if s.score1 > s.score2:
            wins1 += 1
        elif s.score2 > s.score1:
            wins2 += 1
    return wins1, wins2


def get_max_score_for_set(set_index: int, num_sets: int, sport_config: SportConfig) -> int | None:
    """Return the max allowed score for a given set.

    Priority: max_score (absolute hard cap) > computed cap from target + deuce margin.
    For the last possible set, points_last_set is used as the target instead of points_per_set.
    """
    if sport_config.max_score is not None:
        return sport_config.max_score

    is_last_set = set_index == num_sets - 1
    base = (
        sport_config.points_last_set
        if is_last_set and sport_config.points_last_set is not None
        else sport_config.points_per_set
    )
    if base is None:
        return None

    # Without an explicit max_score cap, the effective ceiling accounts for
    # deuce/advantage rules: e.g. target 6 with min_diff 2 means 7 is reachable.
    if sport_config.min_point_difference is not None and sport_config.min_point_difference > 1:
        return base + sport_config.min_point_difference - 1

    return base


def validate_sets(sets: list[MatchSetBody], sport_config: SportConfig) -> None:
    """Validate set data against sport configuration rules."""
    sets_to_win = (sport_config.num_sets // 2) + 1

    if len(sets) > sport_config.num_sets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many sets: maximum is {sport_config.num_sets}",
        )

    for s in sets:
        if s.score1 < 0 or s.score2 < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Set {s.set_number}: scores cannot be negative",
            )

        cap = get_max_score_for_set(s.set_number - 1, sport_config.num_sets, sport_config)
        if cap is not None:
            for label, score in [("score1", s.score1), ("score2", s.score2)]:
                if score > cap:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Set {s.set_number}: {label} ({score}) exceeds maximum of {cap}",
                    )

    set_numbers = [s.set_number for s in sets]
    if len(set_numbers) != len(set(set_numbers)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate set numbers",
        )

    wins1, wins2 = derive_set_wins(sets)

    if wins1 > sets_to_win or wins2 > sets_to_win:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"A side cannot win more than {sets_to_win} sets in best-of-{sport_config.num_sets}"
            ),
        )
